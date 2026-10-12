from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    codex_home: Path
    config_file: Path
    app_data: Path
    provider_file: Path
    settings_file: Path
    backup_dir: Path
    log_dir: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        user_home = Path(os.environ.get("USERPROFILE") or Path.home())
        codex_home = Path(os.environ.get("CODEX_HOME") or user_home / ".codex")
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA") or user_home / "AppData" / "Local"
        )
        app_data = local_app_data / "OpenCodexSwitcher"
        return cls(
            codex_home=codex_home,
            config_file=codex_home / "config.toml",
            app_data=app_data,
            provider_file=app_data / "providers.json",
            settings_file=app_data / "app-settings.json",
            backup_dir=app_data / "backups",
            log_dir=app_data / "logs",
        )

    def ensure_app_directories(self) -> None:
        self.app_data.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
