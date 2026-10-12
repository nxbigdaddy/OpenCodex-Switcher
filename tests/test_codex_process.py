from __future__ import annotations

from pathlib import Path

import pytest

import opencodex_switcher.codex_process as process_module
from opencodex_switcher.codex_process import CodexProcessManager


class FakeProcess:
    def __init__(self, pid: int, executable: Path, name: str = "Codex.exe") -> None:
        self.pid = pid
        self.info = {"pid": pid, "exe": str(executable), "name": name}
        self.killed = False

    def kill(self) -> None:
        self.killed = True


def test_detect_status_close_and_force_only_match_exact_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "Codex.exe"
    other_executable = tmp_path / "Other" / "Codex.exe"
    executable.write_bytes(b"")
    other_executable.parent.mkdir()
    other_executable.write_bytes(b"")
    matched = FakeProcess(100, executable)
    other = FakeProcess(200, other_executable)
    processes = [matched, other]
    monkeypatch.setattr(process_module.psutil, "process_iter", lambda attrs: processes)

    manager = CodexProcessManager()
    monkeypatch.setattr(manager, "_post_windows_close", lambda pids: len(pids))

    assert manager.detect_executable() == executable.resolve()
    status = manager.status(executable)
    assert status.running
    assert status.running_pids == (100,)

    close_result = manager.request_close(executable)
    assert close_result.matched_pids == (100,)
    assert close_result.notified_windows == 1

    assert manager.force_close(executable) == (100,)
    assert matched.killed
    assert not other.killed


def test_start_uses_selected_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "Codex.exe"
    executable.write_bytes(b"")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(args: list[str], **kwargs: object) -> object:
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(process_module.subprocess, "Popen", fake_popen)
    CodexProcessManager().start(executable)

    assert calls[0][0] == [str(executable.resolve())]
    assert calls[0][1]["cwd"] == executable.parent.resolve()


def test_validate_requires_existing_exe(tmp_path: Path) -> None:
    command_file = tmp_path / "codex.cmd"
    command_file.write_text("@echo off", encoding="utf-8")
    manager = CodexProcessManager()

    with pytest.raises(ValueError, match="exe"):
        manager.validate_executable(command_file)
    with pytest.raises(ValueError, match="不存在"):
        manager.validate_executable(tmp_path / "Missing.exe")
