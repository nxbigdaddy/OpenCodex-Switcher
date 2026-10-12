from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import tomlkit

from .models import BackupInfo


class BackupManager:
    def __init__(self, backup_dir: Path):
        self.backup_dir = Path(backup_dir)

    def create(self, source: Path) -> BackupInfo | None:
        source = Path(source)
        if not source.exists():
            return None
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        destination = self.backup_dir / f"config_{now:%Y%m%d_%H%M%S_%f}.toml"
        shutil.copy2(source, destination)
        return BackupInfo(destination, now, destination.stat().st_size)

    def list(self) -> list[BackupInfo]:
        if not self.backup_dir.exists():
            return []
        result: list[BackupInfo] = []
        for path in self.backup_dir.glob("config_*.toml"):
            stat = path.stat()
            result.append(
                BackupInfo(
                    path=path,
                    created_at=datetime.fromtimestamp(stat.st_mtime),
                    size=stat.st_size,
                )
            )
        return sorted(result, key=lambda item: item.created_at, reverse=True)

    def restore(self, backup_path: Path, destination: Path) -> None:
        backup_path = Path(backup_path).resolve()
        backup_root = self.backup_dir.resolve()
        if backup_root not in backup_path.parents:
            raise ValueError("只能恢复应用备份目录内的配置文件。")
        raw_text = backup_path.read_text(encoding="utf-8")
        tomlkit.parse(raw_text)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.create(destination)

        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(raw_text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, destination)
        finally:
            temp_path.unlink(missing_ok=True)
