from __future__ import annotations

import json
from pathlib import Path

from opencodex_switcher.settings_store import AppSettings, SettingsStore


def test_settings_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "app-settings.json"
    store = SettingsStore(path)
    assert store.load() == AppSettings()

    executable = tmp_path / "Codex.exe"
    executable.write_bytes(b"")
    saved = store.save_codex_executable(executable)

    assert saved.codex_executable == str(executable.resolve())
    assert store.load().codex_executable == str(executable.resolve())
    assert json.loads(path.read_text(encoding="utf-8"))["codex_executable"] == str(
        executable.resolve()
    )


def test_settings_store_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "app-settings.json"
    path.write_text("[]", encoding="utf-8")

    try:
        SettingsStore(path).load()
    except ValueError as exc:
        assert "格式无效" in str(exc)
    else:
        raise AssertionError("Expected invalid settings to raise ValueError")
