"""Shared LLM backbone for the grade/vet/commit passes.

OpenAI or Anthropic, JSON-mode, short timeout. A failure raises
:class:`LLMUnavailable` so the calling pass degrades to a deterministic fallback
(or NO_TRADE) — never a silent bad trade.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import requests

from yeaster.core.settings import get_settings

TIMEOUT = 60
_OPENAI_DEFAULT = "gpt-5-mini"
_ANTHROPIC_DEFAULT = "claude-haiku-4-5-20251001"


class LLMUnavailable(Exception):
    """The model could not be reached or returned unusable output."""


def provider() -> str:
    return get_settings().llm_provider


def _model() -> str:
    s = get_settings()
    if s.llm_model:
        return s.llm_model
    return _ANTHROPIC_DEFAULT if s.llm_provider == "anthropic" else _OPENAI_DEFAULT


def available() -> bool:
    s = get_settings()
    return bool(s.anthropic_api_key if s.llm_provider == "anthropic" else s.openai_api_key)


def complete_json(system: str, user: str, *, max_tokens: int = 800) -> dict[str, Any]:
    """Call the model and parse a single JSON object from the reply."""
    return _parse_json(complete_text(system, user, max_tokens=max_tokens, json_mode=True))


def complete_text(system: str, user: str, *, max_tokens: int = 800, json_mode: bool = False) -> str:
    """Call the model and return its raw text reply."""
    s = get_settings()
    if s.llm_provider == "anthropic":
        return _anthropic(system, user, s.anthropic_api_key, max_tokens)
    return _openai(system, user, s.openai_api_key, max_tokens, json_mode=json_mode)


def _openai(system: str, user: str, key: Optional[str], max_tokens: int, json_mode: bool = True) -> str:
    if not key:
        raise LLMUnavailable("OPENAI_API_KEY not set")
    url = "https://api.openai.com/v1/chat/completions"
    body: dict = {
        "model": _model(),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMUnavailable(f"openai: {exc}")


def _anthropic(system: str, user: str, key: Optional[str], max_tokens: int) -> str:
    if not key:
        raise LLMUnavailable("ANTHROPIC_API_KEY not set")
    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": _model(), "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    try:
        r = requests.post(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                          json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as exc:
        raise LLMUnavailable(f"anthropic: {exc}")


def _parse_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMUnavailable("model did not return parseable JSON")
