from __future__ import annotations

import json

import httpx

from opencodex_switcher.connection_tester import ConnectionTester
from opencodex_switcher.models import ModelProfile, ProviderProfile


def test_responses_request_uses_expected_endpoint_and_auth() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers.get("authorization")
        observed["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "resp_test", "output": []})

    provider = ProviderProfile(
        "proxy", "Proxy", "https://example.test/v1", "PROXY_API_KEY"
    )
    model = ModelProfile("Coder", "coder-1", "medium")
    report = ConnectionTester().test(
        provider,
        model,
        api_key="test-secret",
        transport=httpx.MockTransport(handler),
    )

    assert report.ok
    assert observed["url"] == "https://example.test/v1/responses"
    assert observed["authorization"] == "Bearer test-secret"
    assert observed["payload"]["model"] == "coder-1"


def test_missing_key_stops_before_network_call() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    provider = ProviderProfile(
        "proxy", "Proxy", "https://example.test/v1", "MISSING_API_KEY"
    )
    model = ModelProfile("Coder", "coder-1")
    report = ConnectionTester().test(
        provider, model, transport=httpx.MockTransport(handler)
    )

    assert not report.ok
    assert not called
    assert any(check.name == "API Key" and not check.ok for check in report.checks)


def test_error_body_is_redacted() -> None:
    secret = "very-secret-value"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"invalid key {secret}")

    provider = ProviderProfile(
        "proxy", "Proxy", "https://example.test/v1", "PROXY_API_KEY"
    )
    model = ModelProfile("Coder", "coder-1")
    report = ConnectionTester().test(
        provider,
        model,
        api_key=secret,
        transport=httpx.MockTransport(handler),
    )

    all_messages = " ".join(check.message for check in report.checks)
    assert secret not in all_messages
    assert "***" in all_messages


def test_success_status_with_non_responses_json_fails_shape_check() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    provider = ProviderProfile("proxy", "Proxy", "https://example.test/v1")
    model = ModelProfile("Coder", "coder-1")
    report = ConnectionTester().test(
        provider, model, transport=httpx.MockTransport(handler)
    )

    assert not report.ok
    assert "不像 Responses API" in report.checks[-1].message
