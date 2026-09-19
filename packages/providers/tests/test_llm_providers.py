# packages/providers/tests/test_llm_providers.py
import json

import pytest
from fathomark_providers import (
    FakeLLMProvider,
    LLMRequest,
    ProviderError,
    RecordingLLMProvider,
    ReplayLLMProvider,
    prompt_key,
)


def test_prompt_key_is_stable_and_content_addressed():
    k1 = prompt_key("hello")
    k2 = prompt_key("hello")
    assert k1 == k2
    assert k1.startswith("sha256:")
    assert prompt_key("other") != k1


def test_provider_error_carries_retriable_flag():
    err = ProviderError("boom", retriable=True)
    assert err.retriable is True
    assert ProviderError("x").retriable is False


def test_llm_request_defaults():
    req = LLMRequest(prompt="p", schema_name="factor_proposals")
    assert req.max_tokens == 2048


REQ = LLMRequest(prompt="p1", schema_name="s")


def test_fake_provider_pops_queue_and_records_requests():
    fake = FakeLLMProvider(["one", "two"])
    assert fake.complete(REQ).text == "one"
    assert fake.complete(LLMRequest(prompt="p2", schema_name="s")).text == "two"
    assert [r.prompt for r in fake.requests] == ["p1", "p2"]


def test_fake_provider_raises_scripted_error():
    fake = FakeLLMProvider([ProviderError("down", retriable=True)])
    with pytest.raises(ProviderError):
        fake.complete(REQ)


def test_fake_provider_exhausted_queue_raises():
    fake = FakeLLMProvider([])
    with pytest.raises(ProviderError, match="exhausted"):
        fake.complete(REQ)


def test_replay_provider_hit_and_miss(tmp_path):
    cassette = tmp_path / "c.json"
    cassette.write_text(json.dumps({prompt_key("p1"): "canned"}), encoding="utf-8")
    replay = ReplayLLMProvider(cassette)
    assert replay.complete(REQ).text == "canned"
    with pytest.raises(ProviderError, match="cassette miss"):
        replay.complete(LLMRequest(prompt="unknown", schema_name="s"))


def test_recording_provider_roundtrip(tmp_path):
    cassette = tmp_path / "c.json"
    recorder = RecordingLLMProvider(FakeLLMProvider(["fresh"]), cassette)
    assert recorder.complete(REQ).text == "fresh"
    replay = ReplayLLMProvider(cassette, name=recorder.name, version=recorder.version)
    assert replay.complete(REQ).text == "fresh"
    assert replay.name == recorder.name
    assert replay.version == recorder.version
