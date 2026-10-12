from __future__ import annotations

import json
from pathlib import Path

from opencodex_switcher.models import ModelProfile
from opencodex_switcher.provider_store import ProviderStore


def test_store_seeds_editable_presets(tmp_path: Path) -> None:
    path = tmp_path / "app" / "providers.json"
    store = ProviderStore(path)
    providers = store.load()

    assert path.exists()
    assert len(providers) >= 8
    assert any(
        provider.provider_id == "openai" and provider.builtin for provider in providers
    )
    assert any(provider.provider_id == "deepseek" for provider in providers)
    assert all(provider.wire_api == "responses" for provider in providers)


def test_store_round_trip_never_adds_api_key(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    store = ProviderStore(path)
    providers = store.load()
    providers[0].models.append(ModelProfile("Coder", "model-id", "medium"))
    store.save(providers)

    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["schema_version"] == 1
    assert payload["providers"][0]["models"][0]["model_id"] == "model-id"
    assert '"api_key"' not in raw.lower()
