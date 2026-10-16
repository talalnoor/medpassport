"""Thin client for the AI model, with no SDK dependencies.

Supports Google Gemini and any OpenAI-compatible API (Groq, OpenAI, OpenRouter...).
The model is only used for reading photos, suggesting ingredients for unknown
brands and writing plain-language summaries. Legal decisions come from the
verified rules engine, never from the model's memory.
"""
import base64
import json
import re

import httpx

from .. import config


class LLMError(Exception):
    pass


def provider() -> str:
    if config.LLM_PROVIDER == "gemini" and config.GEMINI_API_KEY:
        return "gemini"
    if config.LLM_PROVIDER == "openai" and config.OPENAI_API_KEY:
        return "openai"
    return "none"


def available() -> bool:
    return provider() != "none"


def model_name() -> str:
    p = provider()
    if p == "gemini":
        return config.GEMINI_MODEL
    if p == "openai":
        return config.OPENAI_MODEL
    return "none (offline mode)"


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    raise LLMError("The AI model did not return valid JSON.")


def _gemini(prompt: str, image: bytes | None, mime: str, want_json: bool) -> str:
    parts: list[dict] = [{"text": prompt}]
    if image:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}})
    body: dict = {"contents": [{"role": "user", "parts": parts}],
                  "generationConfig": {"temperature": 0.2}}
    if want_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    try:
        r = httpx.post(url, json=body, timeout=config.LLM_TIMEOUT,
                       headers={"x-goog-api-key": config.GEMINI_API_KEY})
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach Gemini: {e.__class__.__name__}") from e
    if r.status_code != 200:
        raise LLMError(f"Gemini returned HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError("Gemini returned an empty answer.") from e


def _openai(prompt: str, image: bytes | None, mime: str, want_json: bool) -> str:
    if image:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"}},
        ]
        model = config.OPENAI_VISION_MODEL
    else:
        content = prompt
        model = config.OPENAI_MODEL
    body: dict = {"model": model, "temperature": 0.2,
                  "messages": [{"role": "user", "content": content}]}
    if want_json and not image:
        body["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(f"{config.OPENAI_BASE_URL}/chat/completions", json=body,
                       timeout=config.LLM_TIMEOUT,
                       headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"})
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the AI API: {e.__class__.__name__}") from e
    if r.status_code != 200:
        raise LLMError(f"AI API returned HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError("The AI API returned an empty answer.") from e


def generate(prompt: str, image: bytes | None = None, mime: str = "image/jpeg",
             want_json: bool = False):
    p = provider()
    if p == "none":
        raise LLMError("No AI model is configured (offline mode).")
    text = (_gemini if p == "gemini" else _openai)(prompt, image, mime, want_json)
    return _extract_json(text) if want_json else text.strip()
