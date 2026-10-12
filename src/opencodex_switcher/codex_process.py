from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psutil  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class CodexProcessStatus:
    executable: Path | None
    running_pids: tuple[int, ...]

    @property
    def running(self) -> bool:
        return bool(self.running_pids)


@dataclass(frozen=True, slots=True)
class CloseRequestResult:
    matched_pids: tuple[int, ...]
    notified_windows: int


class CodexProcessManager:
    def validate_executable(self, path: Path) -> Path:
        executable = Path(path).expanduser()
        if not executable.is_absolute():
            executable = executable.resolve()
        if not executable.exists() or not executable.is_file():
            raise ValueError("Codex 程序路径不存在或不是文件。")
        if executable.suffix.lower() != ".exe":
            raise ValueError("Codex 路径必须指向可精确追踪的 .exe 文件。")
        return executable.resolve()

    def detect_executable(self) -> Path | None:
        for process in psutil.process_iter(["name", "exe"]):
            try:
                name = str(process.info.get("name") or "").lower()
                executable = process.info.get("exe")
                if name in {"codex", "codex.exe"} and executable:
                    candidate = Path(str(executable))
                    if candidate.exists():
                        return candidate.resolve()
            except (psutil.Error, OSError):
                continue

        on_path = shutil.which("codex")
        if on_path and Path(on_path).suffix.lower() == ".exe":
            return Path(on_path).resolve()

        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("ProgramFiles", ""))
        candidates = (
            local_app_data / "Programs" / "Codex" / "Codex.exe",
            local_app_data / "Codex" / "Codex.exe",
            program_files / "Codex" / "Codex.exe",
        )
        return next((path.resolve() for path in candidates if path.is_file()), None)

    def status(self, path: Path | None) -> CodexProcessStatus:
        if path is None:
            return CodexProcessStatus(None, ())
        try:
            executable = self.validate_executable(path)
        except ValueError:
            return CodexProcessStatus(Path(path), ())
        pids = tuple(process.pid for process in self._matching_processes(executable))
        return CodexProcessStatus(executable, pids)

    def start(self, path: Path) -> None:
        executable = self.validate_executable(path)
        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        subprocess.Popen(
            [str(executable)],
            cwd=executable.parent,
            close_fds=True,
            creationflags=creation_flags,
        )

    def request_close(self, path: Path) -> CloseRequestResult:
        executable = self.validate_executable(path)
        pids = tuple(process.pid for process in self._matching_processes(executable))
        if not pids:
            return CloseRequestResult((), 0)
        if sys.platform != "win32":
            for pid in pids:
                try:
                    psutil.Process(pid).terminate()
                except psutil.Error:
                    continue
            return CloseRequestResult(pids, 0)
        return CloseRequestResult(pids, self._post_windows_close(set(pids)))

    def force_close(self, path: Path) -> tuple[int, ...]:
        executable = self.validate_executable(path)
        terminated: list[int] = []
        for process in self._matching_processes(executable):
            try:
                process.kill()
                terminated.append(process.pid)
            except psutil.Error:
                continue
        return tuple(terminated)

    def _matching_processes(self, executable: Path) -> list[psutil.Process]:
        expected = os.path.normcase(str(executable.resolve()))
        matches: list[psutil.Process] = []
        for process in psutil.process_iter(["pid", "exe"]):
            try:
                process_executable = process.info.get("exe")
                if not process_executable:
                    continue
                actual = os.path.normcase(str(Path(str(process_executable)).resolve()))
                if actual == expected:
                    matches.append(process)
            except (psutil.Error, OSError):
                continue
        return matches

    @staticmethod
    def _post_windows_close(pids: set[int]) -> int:
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        notified = 0

        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
        )

        @callback_type
        def callback(hwnd: int, _: int) -> bool:
            nonlocal notified
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if process_id.value in pids:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                notified += 1
            return True

        user32.EnumWindows(callback, 0)
        return notified
