from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from .config_manager import ConfigManager
from .credential_manager import CredentialManager
from .paths import AppPaths


@dataclass(frozen=True, slots=True)
class DiagnosticItem:
    name: str
    level: str
    message: str


class DiagnosticsService:
    def __init__(
        self,
        paths: AppPaths,
        config_manager: ConfigManager,
        credential_manager: CredentialManager,
    ):
        self.paths = paths
        self.config_manager = config_manager
        self.credential_manager = credential_manager

    def run(self, project_dir: Path | None = None) -> list[DiagnosticItem]:
        result: list[DiagnosticItem] = []
        codex_executable = shutil.which("codex")
        if codex_executable:
            result.append(DiagnosticItem("Codex CLI", "ok", codex_executable))
            try:
                completed = subprocess.run(
                    [codex_executable, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                version = (completed.stdout or completed.stderr).strip()
                result.append(
                    DiagnosticItem(
                        "Codex 版本",
                        "ok" if completed.returncode == 0 else "warning",
                        version or "无法读取版本。",
                    )
                )
            except (OSError, subprocess.SubprocessError) as exc:
                result.append(DiagnosticItem("Codex 版本", "warning", str(exc)))
        else:
            result.append(
                DiagnosticItem("Codex CLI", "warning", "PATH 中没有找到 codex。")
            )

        try:
            snapshot = self.config_manager.read()
        except Exception as exc:
            result.append(DiagnosticItem("用户配置", "error", f"解析失败：{exc}"))
            return result

        result.append(
            DiagnosticItem(
                "用户配置",
                "ok" if snapshot.exists else "warning",
                str(snapshot.path) if snapshot.exists else "配置文件尚不存在。",
            )
        )
        result.append(
            DiagnosticItem(
                "当前选择",
                "ok" if snapshot.model else "warning",
                f"{snapshot.model_provider} / {snapshot.model or '未设置模型'}",
            )
        )
        if snapshot.env_key:
            has_key = self.credential_manager.has_key(snapshot.env_key)
            result.append(
                DiagnosticItem(
                    "API Key 环境变量",
                    "ok" if has_key else "warning",
                    f"{snapshot.env_key}：{'已设置' if has_key else '未在当前进程中找到'}",
                )
            )

        profiles = list(self.paths.codex_home.glob("*.config.toml"))
        result.append(
            DiagnosticItem(
                "Profile 文件",
                "info",
                f"找到 {len(profiles)} 个。" if profiles else "未找到 Profile 文件。",
            )
        )
        project_dir = Path(project_dir or Path.cwd())
        project_config = self._find_project_config(project_dir)
        if project_config:
            try:
                project_doc = tomlkit.parse(project_config.read_text(encoding="utf-8"))
                ignored_keys = [
                    key
                    for key in ("model_provider", "model_providers")
                    if key in project_doc
                ]
                if ignored_keys:
                    result.append(
                        DiagnosticItem(
                            "项目配置",
                            "warning",
                            f"{project_config} 包含用户级提供商字段：{', '.join(ignored_keys)}。",
                        )
                    )
                elif (
                    project_doc.get("model")
                    and str(project_doc.get("model")) != snapshot.model
                ):
                    result.append(
                        DiagnosticItem(
                            "项目模型覆盖",
                            "warning",
                            f"项目模型为 {project_doc.get('model')}，可能覆盖用户默认模型。",
                        )
                    )
                else:
                    result.append(
                        DiagnosticItem("项目配置", "info", str(project_config))
                    )
            except Exception as exc:
                result.append(DiagnosticItem("项目配置", "error", f"解析失败：{exc}"))
        return result

    @staticmethod
    def _find_project_config(start: Path) -> Path | None:
        current = start.resolve()
        while True:
            candidate = current / ".codex" / "config.toml"
            if candidate.exists():
                return candidate
            if current.parent == current:
                return None
            current = current.parent
