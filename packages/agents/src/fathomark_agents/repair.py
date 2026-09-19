"""Structured-output repair loop. Max two repairs per design §14."""

from collections.abc import Callable

from fathomark_providers import LLMProvider, LLMRequest

from fathomark_agents.contracts import AgentError


def complete_with_repairs[T](
    llm: LLMProvider,
    prompt: str,
    schema_name: str,
    parse_validate: Callable[[str], T],
    max_repairs: int = 2,
) -> T:
    attempt_prompt = prompt
    last_error: Exception | None = None
    for _ in range(1 + max_repairs):
        response = llm.complete(
            LLMRequest(prompt=attempt_prompt, schema_name=schema_name)
        )
        try:
            return parse_validate(response.text)
        except ValueError as exc:  # parse or contract failure → repair
            last_error = exc
            attempt_prompt = (
                f"{prompt}\n\nERROR: {exc}\nFix and return corrected JSON only."
            )
    raise AgentError(f"output invalid after {max_repairs} repairs: {last_error}")
