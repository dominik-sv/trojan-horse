"""The small data shapes passed through the benchmark runner.

No Pydantic here: there is no JSON contract with a model to validate, just a
prompt going out and a plain-text answer coming back. Ordinary dataclasses
are enough.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptItem:
    """One question to send to every model."""

    prompt_id: str
    question_type: str
    text: str


@dataclass(frozen=True)
class ModelReply:
    """What one API call returned: the text plus how the model spent its tokens."""

    text: str
    output_tokens: int | None  # everything the model generated, thinking included
    reasoning_tokens: int | None  # the part of output_tokens spent thinking
    incomplete_reason: str | None  # set (e.g. "max_output_tokens") if the model was cut off
    cost_usd: float | None = None  # what the call cost at the provider's list price (the gateway's marketCost)


@dataclass(frozen=True)
class ModelResult:
    """One model's response to one prompt, or the error it failed with."""

    prompt_id: str
    question_type: str
    model: str
    response: str | None
    latency_seconds: float
    error: str | None
    run: int = 1  # which repeat of this (prompt, model) pair, starting at 1
    effort: str | None = None  # thinking effort requested; None means the model's default
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None  # list-price cost of the answer call; None if the call failed or gave no cost
    # Filled in by the judge; all None if this prompt has no criteria.
    verdict: str | None = None  # "yes" (spotted the false premise) or "no"
    judge_quote: str | None = None
    judge_quote_about: str | None = None  # which object the quote is about (A, B, P versus Q, ...)
    judge_reasoning: str | None = None
    judge_error: str | None = None
    judge_cost_usd: float | None = None  # list-price cost of all the judge calls for this answer
    judge_votes: list[dict] | None = None  # one entry per judge: model, verdict, quote, reasoning, cost, error


def provider_of(model_id: str) -> str:
    """The provider part of a gateway model ID: 'openai/gpt-5.6-luna' -> 'openai'."""
    return model_id.split("/", 1)[0]
