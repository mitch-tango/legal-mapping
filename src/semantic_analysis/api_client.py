"""Anthropic API wrapper with retry logic for analysis calls."""

from __future__ import annotations

import logging
import time

import anthropic

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1, 4, 16]  # Exponential backoff


class AnalysisAPIClient:
    """Wraps the Anthropic client with retry logic and error classification."""

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def call_pass1(
        self,
        system_messages: list[dict],
        user_message: str,
        tool_schema: dict,
        api_params: dict,
    ) -> dict:
        """Make Pass 1 API call with retry logic."""
        def do_call():
            return self.client.messages.create(
                model=api_params.get("model", "claude-sonnet-4-20250514"),
                max_tokens=api_params.get("max_tokens", 8192),
                temperature=api_params.get("temperature", 0),
                system=system_messages,
                messages=[{"role": "user", "content": user_message}],
            )

        return self._call_with_retry(do_call)

    def call_pass2(
        self,
        messages: list[dict],
        api_params: dict,
    ) -> dict:
        """Make Pass 2 verification call with retry."""
        system_msg = next((m for m in messages if m.get("role") == "system"), None)
        user_msg = next((m for m in messages if m.get("role") == "user"), None)

        def do_call():
            return self.client.messages.create(
                model=api_params.get("model", "claude-sonnet-4-20250514"),
                max_tokens=api_params.get("max_tokens", 4096),
                temperature=api_params.get("temperature", 0),
                system=system_msg["content"] if system_msg else "",
                messages=[{"role": "user", "content": user_msg["content"] if user_msg else ""}],
            )

        return self._call_with_retry(do_call)

    def _call_with_retry(self, api_call, max_retries: int = 3) -> dict | None:
        """Execute API call with exponential backoff retry."""
        last_error = None

        for attempt in range(max_retries):
            try:
                result = api_call()
                return result
            except anthropic.RateLimitError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                    logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                    time.sleep(delay)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                        logger.warning(f"Server error {e.status_code}, retrying in {delay}s")
                        time.sleep(delay)
                else:
                    raise
            except anthropic.APIConnectionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                    logger.warning(f"Connection error, retrying in {delay}s")
                    time.sleep(delay)

        raise last_error if last_error else RuntimeError("API call failed")
