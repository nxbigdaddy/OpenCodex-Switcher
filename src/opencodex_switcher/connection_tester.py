from __future__ import annotations

import json
import time
from urllib.parse import urlparse

import httpx

from .models import CheckResult, ConnectionReport, ModelProfile, ProviderProfile


class ConnectionTester:
    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds

    def test(
        self,
        provider: ProviderProfile,
        model: ModelProfile,
        *,
        api_key: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> ConnectionReport:
        checks: list[CheckResult] = []
        base_url = provider.base_url or (
            "https://api.openai.com/v1"
            if provider.builtin and provider.provider_id == "openai"
            else ""
        )
        parsed = urlparse(base_url)
        url_ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        checks.append(
            CheckResult(
                "Base URL",
                url_ok,
                "地址格式正确。" if url_ok else "Base URL 格式无效。",
            )
        )
        if not url_ok:
            return ConnectionReport(provider.provider_id, model.model_id, tuple(checks))

        if not model.model_id:
            checks.append(CheckResult("Model ID", False, "Model ID 不能为空。"))
            return ConnectionReport(provider.provider_id, model.model_id, tuple(checks))
        checks.append(CheckResult("Model ID", True, "Model ID 已填写。"))

        if provider.env_key and not api_key:
            checks.append(
                CheckResult(
                    "API Key",
                    False,
                    f"没有找到环境变量 {provider.env_key}，也没有提供临时 API Key。",
                )
            )
            return ConnectionReport(provider.provider_id, model.model_id, tuple(checks))
        checks.append(
            CheckResult(
                "API Key",
                True,
                "已提供鉴权信息。" if api_key else "该服务商未要求 API Key。",
            )
        )

        endpoint = base_url.rstrip("/") + "/responses"
        headers = {"Content-Type": "application/json", **provider.headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model.model_id,
            "input": "Reply with OK only.",
            "max_output_tokens": 16,
            "stream": False,
        }

        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                transport=transport,
            ) as client:
                response = client.post(endpoint, headers=headers, json=payload)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if response.is_success:
                try:
                    body = response.json()
                except json.JSONDecodeError:
                    checks.append(
                        CheckResult(
                            "Responses API",
                            False,
                            "接口返回成功状态码，但响应不是 JSON。",
                            elapsed_ms,
                        )
                    )
                else:
                    shape_ok = isinstance(body, dict) and (
                        "output" in body
                        or "output_text" in body
                        or body.get("object") == "response"
                        or str(body.get("id", "")).startswith("resp_")
                    )
                    checks.append(
                        CheckResult(
                            "Responses API",
                            shape_ok,
                            (
                                f"接口返回 HTTP {response.status_code}，响应结构可识别。"
                                if shape_ok
                                else "接口返回 JSON，但不像 Responses API 响应。"
                            ),
                            elapsed_ms,
                        )
                    )
            else:
                message = self._safe_error_message(response, api_key)
                checks.append(
                    CheckResult(
                        "Responses API",
                        False,
                        f"HTTP {response.status_code}：{message}",
                        elapsed_ms,
                    )
                )
        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            checks.append(CheckResult("Responses API", False, "请求超时。", elapsed_ms))
        except httpx.HTTPError as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            checks.append(
                CheckResult(
                    "Responses API",
                    False,
                    f"网络错误：{type(exc).__name__}",
                    elapsed_ms,
                )
            )
        return ConnectionReport(provider.provider_id, model.model_id, tuple(checks))

    @staticmethod
    def _safe_error_message(response: httpx.Response, api_key: str) -> str:
        text = response.text.replace("\r", " ").replace("\n", " ")[:300]
        if api_key:
            text = text.replace(api_key, "***")
        return text or response.reason_phrase
