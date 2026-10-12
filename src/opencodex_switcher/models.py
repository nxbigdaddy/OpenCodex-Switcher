from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


ALLOWED_REASONING_EFFORTS = ("", "minimal", "low", "medium", "high", "xhigh")


@dataclass(slots=True)
class ModelProfile:
    name: str
    model_id: str
    reasoning_effort: str = "medium"
    context_window: int | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ModelProfile":
        context_window = value.get("context_window")
        return cls(
            name=str(value.get("name", "")).strip(),
            model_id=str(value.get("model_id", "")).strip(),
            reasoning_effort=str(value.get("reasoning_effort", "medium")).strip(),
            context_window=int(context_window) if context_window else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProviderProfile:
    provider_id: str
    name: str
    base_url: str
    env_key: str = ""
    wire_api: str = "responses"
    headers: dict[str, str] = field(default_factory=dict)
    models: list[ModelProfile] = field(default_factory=list)
    notes: str = ""
    compatibility: str = "unverified"
    builtin: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderProfile":
        return cls(
            provider_id=str(value.get("provider_id", "")).strip(),
            name=str(value.get("name", "")).strip(),
            base_url=str(value.get("base_url", "")).strip(),
            env_key=str(value.get("env_key", "")).strip(),
            wire_api=str(value.get("wire_api", "responses")).strip() or "responses",
            headers={str(k): str(v) for k, v in value.get("headers", {}).items()},
            models=[ModelProfile.from_dict(item) for item in value.get("models", [])],
            notes=str(value.get("notes", "")),
            compatibility=str(value.get("compatibility", "unverified")),
            builtin=bool(value.get("builtin", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["models"] = [model.to_dict() for model in self.models]
        return result


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    path: Path
    exists: bool
    raw_text: str
    digest: str
    model: str
    model_provider: str
    reasoning_effort: str
    provider_name: str
    base_url: str
    env_key: str
    modified_at: datetime | None


@dataclass(frozen=True, slots=True)
class BackupInfo:
    path: Path
    created_at: datetime
    size: int


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    message: str
    elapsed_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ConnectionReport:
    provider_id: str
    model_id: str
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(item.ok for item in self.checks)
