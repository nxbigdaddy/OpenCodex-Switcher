from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit

from opencodex_switcher.backup_manager import BackupManager
from opencodex_switcher.config_manager import (
    ConcurrentModificationError,
    ConfigManager,
)
from opencodex_switcher.models import ModelProfile, ProviderProfile


INITIAL_CONFIG = """# keep this comment
model = "old-model"
model_provider = "old_provider"

[model_providers.old_provider]
name = "Old Provider"
base_url = "https://old.example/v1"
env_key = "OLD_API_KEY"
wire_api = "responses"

[mcp_servers.demo]
url = "https://mcp.example.test"
"""


def make_manager(tmp_path: Path) -> tuple[ConfigManager, BackupManager, Path]:
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(INITIAL_CONFIG, encoding="utf-8")
    backups = BackupManager(tmp_path / "backups")
    return ConfigManager(config_path, backups), backups, config_path


def selection() -> tuple[ProviderProfile, ModelProfile]:
    provider = ProviderProfile(
        provider_id="domestic_proxy",
        name="Domestic Proxy",
        base_url="https://proxy.example.test/v1/",
        env_key="DOMESTIC_API_KEY",
        headers={"X-Client": "codex"},
    )
    model = ModelProfile("Coder", "coder-model", "high", 128000)
    return provider, model


def test_read_and_apply_preserves_unrelated_config(tmp_path: Path) -> None:
    manager, backups, config_path = make_manager(tmp_path)
    before = manager.read()
    assert before.model == "old-model"
    assert before.provider_name == "Old Provider"
    assert before.base_url == "https://old.example/v1"

    provider, model = selection()
    rendered, diff = manager.render_selection(provider, model)
    assert "domestic_proxy" in diff
    assert "DOMESTIC_API_KEY" in rendered
    assert "# keep this comment" in rendered
    assert "mcp_servers.demo" in rendered

    written = manager.apply_selection(provider, model, expected_digest=before.digest)
    assert written.model == "coder-model"
    assert written.model_provider == "domestic_proxy"
    assert written.base_url == "https://proxy.example.test/v1"
    assert written.env_key == "DOMESTIC_API_KEY"
    assert len(backups.list()) == 1

    raw = config_path.read_text(encoding="utf-8")
    document = tomlkit.parse(raw)
    assert document["mcp_servers"]["demo"]["url"] == "https://mcp.example.test"
    assert "secret-value" not in raw


def test_concurrent_change_blocks_apply(tmp_path: Path) -> None:
    manager, backups, config_path = make_manager(tmp_path)
    snapshot = manager.read()
    config_path.write_text(
        INITIAL_CONFIG + "\n# externally changed\n", encoding="utf-8"
    )
    provider, model = selection()

    with pytest.raises(ConcurrentModificationError):
        manager.apply_selection(provider, model, expected_digest=snapshot.digest)

    assert "externally changed" in config_path.read_text(encoding="utf-8")
    assert backups.list() == []


def test_invalid_selection_does_not_write(tmp_path: Path) -> None:
    manager, backups, config_path = make_manager(tmp_path)
    original = config_path.read_text(encoding="utf-8")
    provider = ProviderProfile("openai", "Reserved", "not-a-url")
    model = ModelProfile("", "")

    with pytest.raises(ValueError):
        manager.apply_selection(provider, model)

    assert config_path.read_text(encoding="utf-8") == original
    assert backups.list() == []


def test_builtin_openai_selection_does_not_create_custom_provider(
    tmp_path: Path,
) -> None:
    manager, _, _ = make_manager(tmp_path)
    provider = ProviderProfile("openai", "OpenAI", "", "OPENAI_API_KEY", builtin=True)
    model = ModelProfile("OpenAI model", "gpt-example", "medium")

    rendered, _ = manager.render_selection(provider, model)
    document = tomlkit.parse(rendered)

    assert document["model_provider"] == "openai"
    assert document["model"] == "gpt-example"
    assert "openai" not in document["model_providers"]


def test_basic_editor_updates_key_fields_and_preserves_other_sections(
    tmp_path: Path,
) -> None:
    manager, _, _ = make_manager(tmp_path)

    rendered = manager.render_basic_edit(
        INITIAL_CONFIG,
        model="new-coder",
        provider_id="new_proxy",
        reasoning_effort="xhigh",
        context_window=256000,
        provider_name="New Proxy",
        base_url="https://new.example.test/v1/",
        env_key="NEW_PROXY_API_KEY",
    )
    document = tomlkit.parse(rendered)

    assert document["model"] == "new-coder"
    assert document["model_provider"] == "new_proxy"
    assert document["model_reasoning_effort"] == "xhigh"
    assert document["model_context_window"] == 256000
    assert document["model_providers"]["new_proxy"]["base_url"] == (
        "https://new.example.test/v1"
    )
    assert document["model_providers"]["new_proxy"]["wire_api"] == "responses"
    assert document["mcp_servers"]["demo"]["url"] == "https://mcp.example.test"
    assert "# keep this comment" in rendered


def test_raw_editor_validates_backs_up_and_blocks_stale_submit(tmp_path: Path) -> None:
    manager, backups, config_path = make_manager(tmp_path)
    snapshot = manager.read()
    edited = INITIAL_CONFIG.replace('model = "old-model"', 'model = "raw-edited"')
    preview_snapshot, diff = manager.render_raw_diff(edited)
    assert preview_snapshot.digest == snapshot.digest
    assert "raw-edited" in diff

    written = manager.apply_raw_text(edited, expected_digest=snapshot.digest)
    assert written.model == "raw-edited"
    assert len(backups.list()) == 1

    stale_digest = written.digest
    config_path.write_text(edited + "\n# outside edit\n", encoding="utf-8")
    with pytest.raises(ConcurrentModificationError):
        manager.apply_raw_text(edited, expected_digest=stale_digest)
    assert "outside edit" in config_path.read_text(encoding="utf-8")


def test_raw_editor_rejects_invalid_toml_without_writing(tmp_path: Path) -> None:
    manager, backups, config_path = make_manager(tmp_path)
    original = config_path.read_text(encoding="utf-8")

    with pytest.raises(Exception):
        manager.apply_raw_text('model = "unterminated')

    assert config_path.read_text(encoding="utf-8") == original
    assert backups.list() == []


def test_restore_valid_backup_and_backup_current_file(tmp_path: Path) -> None:
    manager, backups, config_path = make_manager(tmp_path)
    original_backup = backups.create(config_path)
    assert original_backup is not None
    config_path.write_text('model = "changed"\n', encoding="utf-8")

    backups.restore(original_backup.path, config_path)

    assert config_path.read_text(encoding="utf-8") == INITIAL_CONFIG
    assert len(backups.list()) == 2
