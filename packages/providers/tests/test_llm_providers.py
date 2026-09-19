# packages/providers/tests/test_llm_providers.py
import pytest

from fathomark_providers import LLMRequest, ProviderError, prompt_key


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
