from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.6, min=0.6, max=6))
async def sentiment_hf_inference(text: str) -> tuple[str, float]:
    if not settings.hf_inference_api_key:
        raise RuntimeError("HF_INFERENCE_API_KEY is not set.")

    headers = {"Authorization": f"Bearer {settings.hf_inference_api_key}"}
    payload = {"inputs": text[:6000]}
    url = f"https://api-inference.huggingface.co/models/{settings.hf_sentiment_model}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"HF inference error ({r.status_code}): {r.text}")
        data = r.json()

    # HF sentiment models typically return [[{label, score}, ...]].
    items = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else data
    best = max(items, key=lambda x: float(x.get("score", 0)))
    label = str(best.get("label", "")).lower()
    score = float(best.get("score", 0.0))

    # Normalize common label variants.
    if "neg" in label:
        return "negative", score
    if "pos" in label:
        return "positive", score
    return "neutral", score

