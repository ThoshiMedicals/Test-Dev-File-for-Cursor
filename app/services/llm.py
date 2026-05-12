from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger


class LlmError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


def _base_url() -> str:
    if settings.openai_base_url is not None:
        return str(settings.openai_base_url).rstrip("/")
    return "https://api.openai.com/v1"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.6, min=0.6, max=6))
async def chat_json(*, model: str, messages: list[ChatMessage], json_schema: dict) -> dict:
    if not settings.openai_api_key:
        raise LlmError("OPENAI_API_KEY is not set.")

    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": json_schema, "strict": True},
        },
    }

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(f"{_base_url()}/chat/completions", json=payload, headers=headers)
        if r.status_code >= 400:
            raise LlmError(f"LLM error ({r.status_code}): {r.text}")
        data = r.json()

    usage = data.get("usage")
    if isinstance(usage, dict):
        logger.info("llm_usage", kind="chat", model=model, usage=usage)

    try:
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:  # noqa: BLE001
        raise LlmError(f"Failed to parse LLM JSON response: {e}") from e


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.6, min=0.6, max=6))
async def embed_text(*, model: str, text: str) -> list[float]:
    if not settings.openai_api_key:
        raise LlmError("OPENAI_API_KEY is not set.")

    payload = {"model": model, "input": text[:20000]}
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(f"{_base_url()}/embeddings", json=payload, headers=headers)
        if r.status_code >= 400:
            raise LlmError(f"Embedding error ({r.status_code}): {r.text}")
        data = r.json()

    usage = data.get("usage")
    if isinstance(usage, dict):
        logger.info("llm_usage", kind="embed", model=model, usage=usage)

    try:
        return list(map(float, data["data"][0]["embedding"]))
    except Exception as e:  # noqa: BLE001
        raise LlmError(f"Failed to parse embeddings response: {e}") from e

