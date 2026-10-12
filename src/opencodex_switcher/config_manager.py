from __future__ import annotations

import difflib
import hashlib
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import tomlkit
from tomlkit.items import Table

from .backup_manager import BackupManager
from .models import ConfigSnapshot, ModelProfile, ProviderProfile


PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
RESERVED_PROVIDER_IDS = {"openai", "ollama", "lmstudio"}


class ConcurrentModificationError(RuntimeError):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_text(value: object, default: str = "") -> str:
    return str(value) if value is not None else default


class ConfigManager:
    def __init__(self, config_path: Path, backup_manager: BackupManager):
        self.config_path = Path(config_path)
        self.backup_manager = backup_manager

    def read(self) -> ConfigSnapshot:
        exists = self.config_path.exists()
        raw_text = self.config_path.read_text(encoding="utf-8") if exists else ""
        document = tomlkit.parse(raw_text) if raw_text.strip() else tomlkit.document()
        provider_id = _as_text(document.get("model_provider"), "openai")
        providers = document.get("model_providers")
        provider_table: Table | None = None
        if isinstance(providers, Table):
            candidate = providers.get(provider_id)
            if isinstance(candidate, Table):
                provider_table = candidate

        modified_at = (
            datetime.fromtimestamp(self.config_path.stat().st_mtime) if exists else None
        )
        is_openai_builtin = provider_id == "openai" and provider_table is None
        return ConfigSnapshot(
            path=self.config_path,
            exists=exists,
            raw_text=raw_text,
            digest=_digest(raw_text),
            model=_as_text(document.get("model")),
            model_provider=provider_id,
            reasoning_effort=_as_text(document.get("model_reasoning_effort")),
            provider_name=(
                _as_text(provider_table.get("name"))
                if provider_table
                else ("OpenAI" if is_openai_builtin else "")
            ),
            base_url=(
                _as_text(provider_table.get("base_url"))
                if provider_table
                else ("https://api.openai.com/v1" if is_openai_builtin else "")
            ),
            env_key=(
                _as_text(provider_table.get("env_key"))
                if provider_table
                else ("OPENAI_API_KEY" if is_openai_builtin else "")
            ),
            modified_at=modified_at,
        )

    def validate_selection(
        self, provider: ProviderProfile, model: ModelProfile
    ) -> list[str]:
        errors: list[str] = []
        if not PROVIDER_ID_PATTERN.fullmatch(provider.provider_id):
            errors.append("Provider ID 只能包含字母、数字、下划线和连字符。")
        if (
            provider.provider_id.lower() in RESERVED_PROVIDER_IDS
            and not provider.builtin
        ):
            errors.append(
                "openai、ollama 和 lmstudio 是 Codex 保留 ID，请使用其他 Provider ID。"
            )
        if not provider.name:
            errors.append("服务商名称不能为空。")
        if not provider.builtin:
            parsed_url = urlparse(provider.base_url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                errors.append("Base URL 必须是有效的 http 或 https 地址。")
        if provider.wire_api != "responses":
            errors.append("当前 Codex 自定义服务商只支持 responses 协议。")
        if not model.model_id:
            errors.append("Model ID 不能为空。")
        if model.reasoning_effort not in {
            "",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
        }:
            errors.append("推理强度取值无效。")
        return errors

    def render_selection(
        self, provider: ProviderProfile, model: ModelProfile
    ) -> tuple[str, str]:
        errors = self.validate_selection(provider, model)
        if errors:
            raise ValueError("\n".join(errors))
        snapshot = self.read()
        document = (
            tomlkit.parse(snapshot.raw_text)
            if snapshot.raw_text.strip()
            else tomlkit.document()
        )

        document["model"] = model.model_id
        document["model_provider"] = provider.provider_id
        if model.reasoning_effort:
            document["model_reasoning_effort"] = model.reasoning_effort
        else:
            document.pop("model_reasoning_effort", None)
        if model.context_window:
            document["model_context_window"] = model.context_window
        else:
            document.pop("model_context_window", None)

        if not provider.builtin:
            providers = document.get("model_providers")
            if not isinstance(providers, Table):
                providers = tomlkit.table()
                document["model_providers"] = providers
            provider_table = providers.get(provider.provider_id)
            if not isinstance(provider_table, Table):
                provider_table = tomlkit.table()
                providers[provider.provider_id] = provider_table

            provider_table["name"] = provider.name
            provider_table["base_url"] = provider.base_url.rstrip("/")
            provider_table["wire_api"] = "responses"
            if provider.env_key:
                provider_table["env_key"] = provider.env_key
            else:
                provider_table.pop("env_key", None)
            if provider.headers:
                headers = tomlkit.inline_table()
                for key, value in provider.headers.items():
                    headers[key] = value
                provider_table["http_headers"] = headers
            else:
                provider_table.pop("http_headers", None)

        rendered = tomlkit.dumps(document)
        diff = "".join(
            difflib.unified_diff(
                snapshot.raw_text.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile=str(self.config_path),
                tofile=str(self.config_path) + "（预览）",
            )
        )
        return rendered, diff or "配置没有变化。"

    def render_basic_edit(
        self,
        raw_text: str,
        *,
        model: str,
        provider_id: str,
        reasoning_effort: str = "",
        context_window: int | None = None,
        provider_name: str = "",
        base_url: str = "",
        env_key: str = "",
    ) -> str:
        model = model.strip()
        provider_id = provider_id.strip()
        if not model:
            raise ValueError("模型 ID 不能为空。")
        if not PROVIDER_ID_PATTERN.fullmatch(provider_id):
            raise ValueError("Provider ID 只能包含字母、数字、下划线和连字符。")
        if reasoning_effort not in {"", "minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("推理强度取值无效。")

        document = tomlkit.parse(raw_text) if raw_text.strip() else tomlkit.document()
        document["model"] = model
        document["model_provider"] = provider_id
        if reasoning_effort:
            document["model_reasoning_effort"] = reasoning_effort
        else:
            document.pop("model_reasoning_effort", None)
        if context_window:
            document["model_context_window"] = context_window
        else:
            document.pop("model_context_window", None)

        if provider_id not in RESERVED_PROVIDER_IDS:
            parsed_url = urlparse(base_url.strip())
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ValueError("自定义服务商必须填写有效的 Base URL。")
            providers = document.get("model_providers")
            if not isinstance(providers, Table):
                providers = tomlkit.table()
                document["model_providers"] = providers
            provider_table = providers.get(provider_id)
            if not isinstance(provider_table, Table):
                provider_table = tomlkit.table()
                providers[provider_id] = provider_table
            provider_table["name"] = provider_name.strip() or provider_id
            provider_table["base_url"] = base_url.strip().rstrip("/")
            provider_table["wire_api"] = "responses"
            if env_key.strip():
                provider_table["env_key"] = env_key.strip()
            else:
                provider_table.pop("env_key", None)
        return tomlkit.dumps(document)

    def render_raw_diff(self, raw_text: str) -> tuple[ConfigSnapshot, str]:
        tomlkit.parse(raw_text)
        snapshot = self.read()
        diff = "".join(
            difflib.unified_diff(
                snapshot.raw_text.splitlines(keepends=True),
                raw_text.splitlines(keepends=True),
                fromfile=str(self.config_path),
                tofile=str(self.config_path) + "（内置编辑器）",
            )
        )
        return snapshot, diff or "配置没有变化。"

    def apply_selection(
        self,
        provider: ProviderProfile,
        model: ModelProfile,
        *,
        expected_digest: str | None = None,
    ) -> ConfigSnapshot:
        current = self.read()
        if expected_digest is not None and current.digest != expected_digest:
            raise ConcurrentModificationError(
                "Codex 配置在预览后被其他程序修改，请刷新后重新操作。"
            )
        rendered, _ = self.render_selection(provider, model)
        tomlkit.parse(rendered)
        if self.read().digest != current.digest:
            raise ConcurrentModificationError(
                "Codex 配置在生成预览时被其他程序修改，请刷新后重新操作。"
            )
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.backup_manager.create(self.config_path)
        try:
            self._atomic_write(rendered)
            written = self.read()
            if (
                written.model != model.model_id
                or written.model_provider != provider.provider_id
            ):
                raise RuntimeError("配置写入后的验证失败。")
            return written
        except Exception:
            if backup is not None:
                self.backup_manager.restore(backup.path, self.config_path)
            elif self.config_path.exists():
                self.config_path.unlink()
            raise

    def apply_raw_text(
        self, raw_text: str, *, expected_digest: str | None = None
    ) -> ConfigSnapshot:
        tomlkit.parse(raw_text)
        current = self.read()
        if expected_digest is not None and current.digest != expected_digest:
            raise ConcurrentModificationError(
                "Codex 配置已被其他程序修改，请重新加载后再提交。"
            )
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.backup_manager.create(self.config_path)
        try:
            self._atomic_write(raw_text)
            return self.read()
        except Exception:
            if backup is not None:
                self.backup_manager.restore(backup.path, self.config_path)
            elif self.config_path.exists():
                self.config_path.unlink()
            raise

    def _atomic_write(self, value: str) -> None:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self.config_path.name}.",
            suffix=".tmp",
            dir=self.config_path.parent,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.config_path)
        finally:
            temp_path.unlink(missing_ok=True)
