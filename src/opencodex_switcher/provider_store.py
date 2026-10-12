from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import ProviderProfile


DEFAULT_PROVIDERS: tuple[dict[str, object], ...] = (
    {
        "provider_id": "openai",
        "name": "OpenAI（Codex 内置）",
        "base_url": "",
        "env_key": "OPENAI_API_KEY",
        "builtin": True,
        "notes": "用于切回 Codex 内置 OpenAI 服务商；请自行添加需要使用的模型 ID。",
    },
    {
        "provider_id": "deepseek",
        "name": "DeepSeek",
        "base_url": "",
        "env_key": "DEEPSEEK_API_KEY",
        "notes": "请填写支持 Responses API 的官方地址或兼容中转地址。",
    },
    {
        "provider_id": "dashscope",
        "name": "通义千问 / 百炼",
        "base_url": "",
        "env_key": "DASHSCOPE_API_KEY",
        "notes": "接口是否兼容 Codex Responses API 需要实际测试。",
    },
    {
        "provider_id": "zhipu",
        "name": "智谱 GLM",
        "base_url": "",
        "env_key": "ZHIPU_API_KEY",
        "notes": "接口是否兼容 Codex Responses API 需要实际测试。",
    },
    {
        "provider_id": "moonshot",
        "name": "Kimi / Moonshot",
        "base_url": "",
        "env_key": "MOONSHOT_API_KEY",
        "notes": "接口是否兼容 Codex Responses API 需要实际测试。",
    },
    {
        "provider_id": "volcengine_ark",
        "name": "豆包 / 火山方舟",
        "base_url": "",
        "env_key": "ARK_API_KEY",
        "notes": "接口是否兼容 Codex Responses API 需要实际测试。",
    },
    {
        "provider_id": "siliconflow",
        "name": "硅基流动",
        "base_url": "",
        "env_key": "SILICONFLOW_API_KEY",
        "notes": "接口是否兼容 Codex Responses API 需要实际测试。",
    },
    {
        "provider_id": "local_ollama",
        "name": "Ollama（自定义连接）",
        "base_url": "http://localhost:11434/v1",
        "env_key": "",
        "notes": "本地服务；请添加本机已经下载的模型 ID。",
    },
    {
        "provider_id": "local_lmstudio",
        "name": "LM Studio（自定义连接）",
        "base_url": "http://localhost:1234/v1",
        "env_key": "",
        "notes": "本地服务；请添加 LM Studio 当前加载的模型 ID。",
    },
)


class ProviderStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[ProviderProfile]:
        if not self.path.exists():
            providers = [ProviderProfile.from_dict(item) for item in DEFAULT_PROVIDERS]
            self.save(providers)
            return providers

        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("providers"), list):
            raise ValueError(f"服务商文件格式无效：{self.path}")
        return [ProviderProfile.from_dict(item) for item in value["providers"]]

    def save(self, providers: list[ProviderProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "providers": [provider.to_dict() for provider in providers],
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            temp_path.unlink(missing_ok=True)
