"""Thin client for the AI model, with no SDK dependencies.

Supports Google Gemini and any OpenAI-compatible API (Groq, OpenAI, OpenRouter...).
The model is only used for reading photos, suggesting ingredients for unknown
brands and writing plain-language summaries. Legal decisions come from the
verified rules engine, never from the model's memory.
"""
import base64
import json
import logging
import math
import re
import time

import httpx

from .. import config


log = logging.getLogger("medpassport.llm")


class LLMError(Exception):
    def __init__(self, message: str, status: int | None = None,
                 kind: str | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.kind = kind                # for 429: "daily", "minute" or "unknown"
        self.retry_after = retry_after  # seconds Google asked us to wait, if it said


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


def _error_message(r) -> str:
    try:
        err = r.json().get("error", {})
        msg = err.get("message") if isinstance(err, dict) else str(err)
    except ValueError:
        msg = r.text
    return (msg or "no details")[:240]


# ---------- quota (HTTP 429) handling ----------
# After a 429 the model is put on a cooldown, so the app stops calling it (and stops
# making the traveller wait) until the limit has reset. The cooldown is per process.
_cooldown: dict[str, tuple[float, str]] = {}  # model -> (until, as time.monotonic(); kind)


def _quota_info(r) -> tuple[str, float | None]:
    """Reads Google's 429 details: which limit was hit and how long to wait."""
    kind, retry = "unknown", None
    try:
        details = r.json().get("error", {}).get("details", []) or []
    except (ValueError, AttributeError):
        details = []
    for d in details if isinstance(details, list) else []:
        t = str(d.get("@type", ""))
        if t.endswith("QuotaFailure"):
            for v in d.get("violations", []) or []:
                qid = f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}".lower()
                if "perday" in qid:
                    kind = "daily"
                elif "perminute" in qid and kind != "daily":
                    kind = "minute"
        elif t.endswith("RetryInfo"):
            m = re.match(r"([\d.]+)s", str(d.get("retryDelay", "")))
            if m:
                retry = float(m.group(1))
    return kind, retry


def _seconds_to_daily_reset() -> float:
    """Gemini daily quotas reset at midnight Pacific time."""
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
        nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return (nxt - now).total_seconds()
    except Exception:  # no time zone data on this server
        return 3600.0


def _cooldown_seconds(kind: str, retry_after: float | None) -> float:
    if kind == "daily":
        return _seconds_to_daily_reset()
    if kind == "minute":
        return max(retry_after or 60.0, 5.0)
    return max(retry_after or 300.0, 5.0)


def _quota_message(kind: str, seconds_left: float) -> str:
    """Short, plain message. Callers add their own lead-in and closing sentence."""
    if kind == "daily":
        hours = max(1, math.ceil(seconds_left / 3600))
        return ("the AI's free daily limit for this app is used up. It resets at midnight Pacific time, "
                f"in about {hours} hour{'s' if hours != 1 else ''}")
    if kind == "minute":
        secs = max(5, math.ceil(seconds_left))
        return f"too many AI requests in the last minute. Try again in about {secs} seconds"
    mins = max(1, math.ceil(seconds_left / 60))
    return f"the AI's usage limit for this app has been reached. Try again in about {mins} minute{'s' if mins != 1 else ''}"


def _thinking_config(model: str) -> dict | None:
    """Labels and short summaries need no long reasoning; less thinking = much faster replies."""
    if "2.5-flash" in model:
        return {"thinkingBudget": 0}
    if model.startswith("gemini-3"):
        return {"thinkingLevel": "low"}
    return None


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left < 1:
        raise LLMError("The AI took too long, so MedPassport continued without it.", status=408)
    return min(config.LLM_TIMEOUT, left)


def _gemini_once(model: str, prompt: str, image: bytes | None, mime: str, want_json: bool, deadline: float) -> str:
    parts: list[dict] = [{"text": prompt}]
    if image:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}})
    body: dict = {"contents": [{"role": "user", "parts": parts}],
                  "generationConfig": {"temperature": 0.2}}
    if want_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    thinking = _thinking_config(model)
    if thinking:
        body["generationConfig"]["thinkingConfig"] = thinking
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": config.GEMINI_API_KEY}
    try:
        r = httpx.post(url, json=body, timeout=_remaining(deadline), headers=headers)
        if r.status_code == 400:
            # Newer models can reject optional settings (thinking, temperature...).
            # Log why, then retry once with only the essentials.
            log.warning("Gemini 400 with full settings: %s", _error_message(r))
            minimal = {"contents": body["contents"]}
            if want_json:
                minimal["generationConfig"] = {"responseMimeType": "application/json"}
            r = httpx.post(url, json=minimal, timeout=_remaining(deadline), headers=headers)
            if r.status_code == 400 and want_json:
                log.warning("Gemini 400 with JSON mode: %s", _error_message(r))
                r = httpx.post(url, json={"contents": body["contents"]}, timeout=_remaining(deadline), headers=headers)
    except httpx.TimeoutException as e:
        raise LLMError(f"Gemini did not answer in time (model {model})", status=408) from e
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach Gemini: {e.__class__.__name__}") from e
    if r.status_code == 429:
        kind, retry = _quota_info(r)
        log.warning("Gemini 429 (%s limit, retry after %s s, model %s): %s", kind, retry, model, _error_message(r))
        wait = _cooldown_seconds(kind, retry)
        raise LLMError(_quota_message(kind, wait), status=429, kind=kind, retry_after=retry)
    if r.status_code != 200:
        raise LLMError(f"Gemini returned HTTP {r.status_code}: {_error_message(r)}", status=r.status_code)
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError("Gemini returned an empty answer.") from e
    if not text.strip():
        raise LLMError("Gemini returned an empty answer.")
    return text


BUSY_CODES = (500, 503)  # temporary server trouble: worth a quick retry. 429 is handled separately.


def _gemini(prompt: str, image: bytes | None, mime: str, want_json: bool, deadline: float) -> str:
    """Retries when Google is busy (within the time budget), then tries the optional fallback model.
    A model that hit its quota is skipped until the quota resets; the fallback model has its own quota."""
    models = [config.GEMINI_MODEL] + ([config.GEMINI_FALLBACK_MODEL] if config.GEMINI_FALLBACK_MODEL else [])
    last: LLMError | None = None
    for model in models:
        cd = _cooldown.get(model)
        if cd:
            left = cd[0] - time.monotonic()
            if left > 0:
                last = LLMError(_quota_message(cd[1], left), status=429, kind=cd[1])
                continue
            _cooldown.pop(model, None)
        for attempt, wait in enumerate((0, 1.5, 4)):
            if wait:
                if deadline - time.monotonic() < wait + 4:
                    break  # not enough time left for another try
                time.sleep(wait)
            try:
                return _gemini_once(model, prompt, image, mime, want_json, deadline)
            except LLMError as e:
                last = e
                if e.status == 429:
                    _cooldown[model] = (time.monotonic() + _cooldown_seconds(e.kind or "unknown", e.retry_after),
                                        e.kind or "unknown")
                    break  # retrying now would only burn more quota; try the fallback model
                if e.status not in BUSY_CODES:
                    raise
                log.warning("Gemini busy (%s, model %s, attempt %d): %s", e.status, model, attempt + 1, e)
        if deadline - time.monotonic() < 5:
            break
    if last and last.status == 429:
        raise last
    raise LLMError("Google's AI is busy right now. Try again in a minute",
                   status=last.status if last else None)


def _openai(prompt: str, image: bytes | None, mime: str, want_json: bool, deadline: float) -> str:
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
                       timeout=_remaining(deadline),
                       headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"})
    except httpx.TimeoutException as e:
        raise LLMError("The AI API did not answer in time", status=408) from e
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the AI API: {e.__class__.__name__}") from e
    if r.status_code == 429:
        log.warning("AI API 429: %s", _error_message(r))
        raise LLMError("the AI's usage limit for this app has been reached. Try again later", status=429)
    if r.status_code != 200:
        raise LLMError(f"AI API returned HTTP {r.status_code}: {_error_message(r)}", status=r.status_code)
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError("The AI API returned an empty answer.") from e


def generate(prompt: str, image: bytes | None = None, mime: str = "image/jpeg",
             want_json: bool = False, budget: float = 20):
    """budget = maximum seconds for the whole call, including retries.
    The hosting gateway gives up after about 30 s, so callers keep budgets below that."""
    p = provider()
    if p == "none":
        raise LLMError("No AI model is configured (offline mode).")
    deadline = time.monotonic() + budget
    text = (_gemini if p == "gemini" else _openai)(prompt, image, mime, want_json, deadline)
    return _extract_json(text) if want_json else text.strip()