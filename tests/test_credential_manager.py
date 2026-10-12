from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from opencodex_switcher.credential_manager import (
    CredentialManager,
    EnvironmentScope,
)


@dataclass
class MemoryRegistry:
    values: dict[tuple[EnvironmentScope, str], str] = field(default_factory=dict)

    def get(self, scope: EnvironmentScope, name: str) -> str | None:
        return self.values.get((scope, name))

    def set(self, scope: EnvironmentScope, name: str, value: str) -> None:
        self.values[(scope, name)] = value

    def delete(self, scope: EnvironmentScope, name: str) -> bool:
        return self.values.pop((scope, name), None) is not None


def make_manager(registry: MemoryRegistry) -> CredentialManager:
    return CredentialManager(registry, broadcast_changes=False)


def test_environment_scope_precedence_and_delete(monkeypatch) -> None:
    registry = MemoryRegistry()
    manager = make_manager(registry)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    manager.save_environment("system", "OPENAI_MODEL", "system-model")
    assert manager.read_environment("system", "OPENAI_MODEL").value == "system-model"
    assert manager.get_key("OPENAI_MODEL") == "system-model"

    manager.save_environment("user", "OPENAI_MODEL", "user-model")
    assert manager.get_key("OPENAI_MODEL") == "user-model"

    assert manager.delete_environment("user", "OPENAI_MODEL") is True
    assert manager.get_key("OPENAI_MODEL") == "system-model"
    assert manager.delete_environment("system", "OPENAI_MODEL") is True
    assert manager.get_key("OPENAI_MODEL") == ""
    assert manager.delete_environment("system", "OPENAI_MODEL") is False


def test_read_reports_missing_variable() -> None:
    manager = make_manager(MemoryRegistry())

    variable = manager.read_environment("user", "OPENAI_BASE_URL")

    assert variable.exists is False
    assert variable.value == ""


@pytest.mark.parametrize("name", ["", "BAD NAME", "9INVALID", "A=B"])
def test_invalid_environment_names_are_rejected(name: str) -> None:
    manager = make_manager(MemoryRegistry())

    with pytest.raises(ValueError, match="变量名"):
        manager.read_environment("user", name)


def test_empty_value_requires_explicit_delete() -> None:
    manager = make_manager(MemoryRegistry())

    with pytest.raises(ValueError, match="删除按钮"):
        manager.save_environment("user", "OPENAI_BASE_URL", "")


def test_save_api_key_strips_outer_whitespace(monkeypatch) -> None:
    registry = MemoryRegistry()
    manager = make_manager(registry)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    manager.save_user_environment("OPENAI_API_KEY", "  secret-value  ")

    assert registry.get("user", "OPENAI_API_KEY") == "secret-value"
    assert manager.get_key("OPENAI_API_KEY") == "secret-value"
