"""
LLM client wrapper — supports Anthropic Claude, OpenAI GPT, and Groq.

Falls back gracefully if no API key is configured. The rest of the AI
module checks `is_available()` before making calls, so the tool works
fully without any LLM provider.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Parsed response from the LLM."""
    text: str
    provider: str
    model: str
    tokens_used: int = 0


class LLMClient:
    """Unified LLM client with multi-provider fallback."""

    def __init__(self) -> None:
        self._provider: str | None = None
        self._client = None
        self._model: str = ""
        self._initialize()

    def _initialize(self) -> None:
        """Try to initialize a provider in order of preference."""
        # Try Anthropic first
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                self._provider = "anthropic"
                self._model = "claude-sonnet-4-20250514"
                log.info("LLM: Anthropic Claude initialized")
                return
            except ImportError:
                log.debug("anthropic package not installed")
            except Exception as e:
                log.warning("Anthropic init failed: %s", e)

        # Try OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                import openai
                self._client = openai.OpenAI(api_key=api_key)
                self._provider = "openai"
                self._model = "gpt-4o-mini"
                log.info("LLM: OpenAI initialized")
                return
            except ImportError:
                log.debug("openai package not installed")
            except Exception as e:
                log.warning("OpenAI init failed: %s", e)

        # Try Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key:
            try:
                import groq
                self._client = groq.Groq(api_key=api_key)
                self._provider = "groq"
                self._model = "llama-3.1-70b-versatile"
                log.info("LLM: Groq initialized")
                return
            except ImportError:
                log.debug("groq package not installed")
            except Exception as e:
                log.warning("Groq init failed: %s", e)

        log.info("LLM: No provider configured. AI features disabled. "
                 "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY to enable.")

    def is_available(self) -> bool:
        """Check if any LLM provider is configured and ready."""
        return self._provider is not None

    @property
    def provider_name(self) -> str:
        return self._provider or "none"

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse | None:
        """
        Send a prompt to the LLM and return the response.

        Returns None if no provider is available or the call fails.
        Uses low temperature for deterministic analysis responses.
        """
        if not self.is_available():
            return None

        try:
            if self._provider == "anthropic":
                return self._call_anthropic(prompt, system, max_tokens, temperature)
            elif self._provider == "openai":
                return self._call_openai(prompt, system, max_tokens, temperature)
            elif self._provider == "groq":
                return self._call_groq(prompt, system, max_tokens, temperature)
        except Exception as e:
            log.warning("LLM call failed (%s): %s", self._provider, e)
            return None

        return None

    def complete_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
    ) -> dict | list | None:
        """
        Send a prompt expecting JSON response. Parses and returns the data.
        Returns None on failure.
        """
        response = self.complete(prompt, system, max_tokens, temperature=0.1)
        if not response:
            return None

        text = response.text.strip()

        # Strip markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.warning("Failed to parse LLM JSON response: %s", e)
            log.debug("Raw response: %s", text[:500])
            return None

    def _call_anthropic(self, prompt, system, max_tokens, temperature) -> LLMResponse:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a code analysis assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text
        tokens = message.usage.input_tokens + message.usage.output_tokens
        return LLMResponse(text=text, provider="anthropic", model=self._model, tokens_used=tokens)

    def _call_openai(self, prompt, system, max_tokens, temperature) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0
        return LLMResponse(text=text, provider="openai", model=self._model, tokens_used=tokens)

    def _call_groq(self, prompt, system, max_tokens, temperature) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0
        return LLMResponse(text=text, provider="groq", model=self._model, tokens_used=tokens)


# Module-level singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client