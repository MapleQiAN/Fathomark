import pytest
from fathomark_agents import AgentError, ScopeAgent, complete_with_repairs
from fathomark_core.schemas import ScopeSnapshot
from fathomark_providers import FakeLLMProvider


def test_scope_agent_freezes_contract(seeded_run):
    repo, run_id = seeded_run
    scope = ScopeAgent().run(repo, run_id)
    assert isinstance(scope, ScopeSnapshot)
    assert scope.symbol == "ADBE" and scope.framework_ref == "common-stock@1.0.0"


def test_repair_loop_succeeds_on_second_attempt():
    llm = FakeLLMProvider(["not json", '{"ok": true}'])
    result = complete_with_repairs(llm, "prompt", "test", lambda text: _parse(text))
    assert result == {"ok": True}
    assert len(llm.requests) == 2
    assert "ERROR:" in llm.requests[1].prompt


def test_repair_loop_exhausted_raises_agent_error():
    llm = FakeLLMProvider(["bad", "bad", "bad"])
    with pytest.raises(AgentError):
        complete_with_repairs(llm, "p", "test", _parse)
    assert len(llm.requests) == 3  # initial + 2 repairs, no more


def _parse(text):
    import json

    return json.loads(text)
