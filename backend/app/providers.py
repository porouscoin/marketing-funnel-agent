"""Talking to models: one HTTP adapter for every provider, JSON answers, fallbacks.

Gemini and Groq both speak the OpenAI chat format. Every step of the agent asks
for a JSON object, so ask_json() parses the answer, retries once with the parse
error if the JSON is broken, and moves on to the next model when one is rate
limited or down.
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .config import ModelSpec

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class ProviderError(Exception):
    pass


@dataclass
class Usage:
    """Running totals for one request, shown in the agent's step log."""

    calls: int = 0
    tokens: int = 0
    ms: int = 0
    models: dict[str, int] = field(default_factory=dict)


# Tests and local dev swap in a fake model: a function from (task, messages) to a dict.
MockFn = Callable[[str, list[dict]], dict]
_mock_fn: MockFn | None = None


def set_mock(fn: MockFn | None) -> None:
    global _mock_fn
    _mock_fn = fn


_client: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(50.0, connect=10.0))
    return _client


async def _chat(spec: ModelSpec, messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, int]:
    body: dict[str, Any] = {
        "model": spec.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if spec.provider == "groq":
        body["response_format"] = {"type": "json_object"}
    if "gpt-oss" in spec.model:
        # Reasoning tokens count against max_tokens; low effort leaves room for the answer.
        body["reasoning_effort"] = "low"
    headers = {"Authorization": f"Bearer {spec.api_key}"}
    last = ""
    for attempt in range(2):
        try:
            resp = await http().post(f"{spec.base_url}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as e:
            last = f"network error: {type(e).__name__}"
        else:
            if resp.status_code == 200:
                data = resp.json()
                text = THINK_RE.sub("", data["choices"][0]["message"].get("content") or "").strip()
                usage = data.get("usage") or {}
                return text, int(usage.get("total_tokens", 0))
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            # A rate limit won't clear in a second or two; let the next model take it.
            if resp.status_code == 429 or resp.status_code < 500:
                break
        await asyncio.sleep(1.5 * (attempt + 1))
    raise ProviderError(f"{spec.label}: {last}")


def parse_json(text: str) -> dict:
    """The first JSON object in the text. Models sometimes wrap it in a code fence or a sentence."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise json.JSONDecodeError("expected a JSON object", text, 0)
    return value


async def ask_json(
    task: str,
    specs: list[ModelSpec],
    system: str,
    user: str,
    usage: Usage,
    max_tokens: int = 1500,
    temperature: float = 0.6,
) -> tuple[dict, ModelSpec]:
    """Ask the first model that answers for a JSON object. Returns the object and the model used."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    errors: list[str] = []
    for spec in specs:
        started = time.monotonic()
        if spec.provider == "mock":
            if _mock_fn is None:
                from .mock import mock_answer

                value = mock_answer(task, messages)
            else:
                value = _mock_fn(task, messages)
            usage.calls += 1
            usage.models[spec.label] = usage.models.get(spec.label, 0) + 1
            return value, spec
        convo = list(messages)
        for attempt in range(2):
            try:
                text, tokens = await _chat(spec, convo, max_tokens, temperature)
            except ProviderError as e:
                errors.append(str(e))
                break
            usage.calls += 1
            usage.tokens += tokens
            usage.ms += int((time.monotonic() - started) * 1000)
            usage.models[spec.label] = usage.models.get(spec.label, 0) + 1
            try:
                return parse_json(text), spec
            except json.JSONDecodeError as e:
                errors.append(f"{spec.label}: bad JSON ({e.msg})")
                convo = messages + [
                    {"role": "assistant", "content": text[:4000]},
                    {"role": "user", "content": f"That was not valid JSON ({e.msg}). Send only the JSON object."},
                ]
    raise ProviderError("; ".join(errors) or "no model is configured")
