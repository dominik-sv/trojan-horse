"""A thin wrapper around the OpenAI Responses API, pointed at Vercel AI Gateway.

There is intentionally no framework here. This file is the only place that
knows how to ask a model for a plain-text answer or list which models this
account can currently call.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
import threading

from openai import APIConnectionError, APIStatusError, InternalServerError, OpenAI, RateLimitError
from tqdm import tqdm

from .config import (
    GATEWAY_BASE_URL,
    GATEWAY_KEY_ENV_VAR,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
)
from .models import ModelReply

# Errors that usually go away if we wait and send the same request again.
_RETRYABLE = (RateLimitError, InternalServerError, APIConnectionError)


class BenchmarkClient:
    def __init__(self) -> None:
        api_key = os.getenv(GATEWAY_KEY_ENV_VAR)
        if not api_key:
            raise RuntimeError(
                f"{GATEWAY_KEY_ENV_VAR} is missing. Add it as a Windows user environment variable, then open a new terminal."
            )
        # max_retries=0 turns off the library's own retrying, so the loop below is the only one.
        self.client = OpenAI(api_key=api_key, base_url=GATEWAY_BASE_URL, max_retries=0)
        self._stopping = threading.Event()

    def stop(self) -> None:
        """Make calls that are waiting to retry give up now, so a stopped run exits quickly."""
        self._stopping.set()

    def ask(
        self, *, model: str, prompt: str, max_output_tokens: int, effort: str | None = None
    ) -> ModelReply:
        """Send one prompt to one model and return its text and token usage.

        `effort` sets how hard the model thinks; None leaves it at the model's default.
        """
        request: dict = {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if effort:
            request["reasoning"] = {"effort": effort}
        response = self._create_with_retry(request)
        usage = getattr(response, "usage", None)
        details = getattr(usage, "output_tokens_details", None)
        incomplete = getattr(response, "incomplete_details", None)
        return ModelReply(
            text=getattr(response, "output_text", "") or "",
            output_tokens=getattr(usage, "output_tokens", None),
            reasoning_tokens=getattr(details, "reasoning_tokens", None),
            incomplete_reason=(getattr(incomplete, "reason", None) or "incomplete")
            if getattr(response, "status", None) == "incomplete"
            else None,
            cost_usd=_market_cost(response),
        )

    def list_models(self, contains: str = "") -> list[str]:
        """Return every model ID the gateway offers, optionally only those containing `contains`."""
        models = self.client.models.list()
        needle = contains.lower()
        return sorted(model.id for model in models.data if needle in model.id.lower())

    def _create_with_retry(self, request: dict) -> object:
        """Send the request, waiting and retrying temporary failures a bounded number of times."""
        model = request["model"]
        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            try:
                return self.client.responses.create(**request)  # type: ignore
            except _RETRYABLE as error:
                if attempt == RETRY_MAX_ATTEMPTS:
                    raise RuntimeError(
                        f"Gave up on {model} after {attempt} attempts. Last response: {_describe(error)}"
                    ) from error
                delay = _retry_delay(error, attempt)
                tqdm.write(f"{_short(error)} on {model}; waiting {delay:.0f}s (attempt {attempt}/{RETRY_MAX_ATTEMPTS})")
                if self._stopping.wait(delay):
                    raise RuntimeError("Run was stopped.") from error
        raise AssertionError("Retry loop exited unexpectedly.")


def _market_cost(response: object) -> float | None:
    """The call's cost at the provider's list price, from the gateway's metadata.

    marketCost is used, not cost: with your own provider keys the provider bills
    you directly and the gateway's own `cost` is 0, but marketCost still shows
    what the call is worth, so every provider is measured the same way.
    """
    try:
        return float(response.model_dump()["provider_metadata"]["gateway"]["marketCost"])  # type: ignore[attr-defined]
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _retry_delay(error: Exception, attempt: int) -> float:
    """The server's retry-after time if it sent one, otherwise 1, 2, 4, ... seconds."""
    seconds = _retry_after_seconds(error)
    if seconds is None:
        seconds = RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1)
    return min(seconds, RETRY_MAX_WAIT_SECONDS)


def _retry_after_seconds(error: Exception) -> float | None:
    """Parse a retry-after header, which is either a number of seconds or an HTTP date."""
    if not isinstance(error, APIStatusError):
        return None
    header = error.response.headers.get("retry-after")
    if not header:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _short(error: Exception) -> str:
    if isinstance(error, APIStatusError):
        return f"HTTP {error.status_code}"
    return type(error).__name__


def _describe(error: Exception) -> str:
    """The status, retry-after header and response body of a failed call, so we can tell whose limit it was."""
    if not isinstance(error, APIStatusError):
        return f"{type(error).__name__}: {error}"
    retry_after = error.response.headers.get("retry-after")
    body = error.response.text.strip()
    if len(body) > 800:
        body = body[:800] + "..."
    return f"HTTP {error.status_code}" + (f", retry-after {retry_after}" if retry_after else "") + f", body: {body}"
