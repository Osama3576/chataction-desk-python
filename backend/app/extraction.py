from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import GEMINI_API_KEY, SHARED_RULES_PATH

logger = logging.getLogger("chataction.extraction")


class AIExtractionResult(BaseModel):
    has_action: bool = Field(default=False)
    item_type: str | None = Field(default=None)
    title: str = Field(default="")
    summary: str = Field(default="")
    due_date: str | None = Field(default=None)
    priority: str = Field(default="Medium")
    confidence_score: float | str | None = Field(default=0.0)
    reason: str = Field(default="")
    action_signals: list[str] = Field(default_factory=list)


ALLOWED_ITEM_TYPES = {
    "task": "Task",
    "followup": "Follow-up",
    "follow-up": "Follow-up",
    "follow up": "Follow-up",
    "decision": "Decision",
    "openquestion": "Open Question",
    "open-question": "Open Question",
    "open question": "Open Question",
    "question": "Open Question",
    "action": "Task",
    "action item": "Task",
    "order": "Task",
    "request": "Task",
}

ALLOWED_PRIORITIES = {
    "low": "Low",
    "medium": "Medium",
    "med": "Medium",
    "normal": "Medium",
    "high": "High",
    "urgent": "High",
    "critical": "High",
}

DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
    re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"),
]

TEXT_REPLACEMENTS = {
    "qutation": "quotation",
    "quatation": "quotation",
    "quotatione": "quotation",
    "qoutation": "quotation",
    "qoute": "quote",
    "tmrw": "tomorrow",
    "tmr": "tomorrow",
    "plz ": "please ",
    "pls ": "please ",
    "udate": "update",
    "remidner": "reminder",
}


@lru_cache(maxsize=1)
def _load_manual_rules() -> dict[str, list[str]]:
    path = Path(SHARED_RULES_PATH)
    if not path.exists():
        logger.warning("Manual rules file not found at %s", path)
        return {
            "task_keywords": ["send", "share", "check", "review", "update", "call", "confirm"],
            "followup_keywords": ["follow up", "remind", "check back"],
            "decision_keywords": ["final", "approved", "confirmed", "done"],
            "question_keywords": ["?", "can you", "should we"],
            "deadline_keywords": ["today", "tomorrow", "kal", "aaj"],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    for wrong, correct in TEXT_REPLACEMENTS.items():
        lowered = lowered.replace(wrong, correct)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _build_context_block(recent_messages: list[dict]) -> str:
    if not recent_messages:
        return "No prior context available."

    lines = []
    for item in recent_messages:
        sender = item.get("sender_label", "Contact")
        body = (item.get("body") or "").strip()
        time_text = item.get("message_time", "")
        lines.append(f"- [{time_text}] {sender}: {body}")
    return "\n".join(lines)


def _primary_prompt(contact_name: str, message_text: str, message_time: datetime, recent_messages: list[dict]) -> str:
    today = message_time.date().isoformat()
    tomorrow = (message_time.date() + timedelta(days=1)).isoformat()

    return f"""
You are analyzing the latest business chat message for a workflow tool.

Current contact: {contact_name}
Current message time: {message_time.isoformat()}
Reference today date: {today}
Reference tomorrow date: {tomorrow}

Latest message:
{message_text}

Recent conversation context:
{_build_context_block(recent_messages)}

Your job:
Understand the latest message like a careful human operator.

Action rule:
If the latest message asks, requests, reminds, instructs, expects, or implies that someone should do anything at all, it is actionable and should go to the Review Queue.

Examples of actionable intent:
- send something
- share something
- review something
- check something
- confirm something
- update someone
- call someone
- prepare something
- remind/follow up
- respond after completion
- compound instructions such as "send X and confirm once shared"

Important:
- Support English, Roman Urdu, and mixed-language business chats.
- Polite requests are actionable.
- Indirect requests are actionable.
- Typos do not remove actionability if the meaning is clear.
- For compound instructions, treat the message as actionable.
- Extract clear requested actions into action_signals.
- If action_signals is not empty, has_action should be true.
- Only return has_action=false when the message is clearly non-actionable.
- Use one of these item_type values when actionable: Task, Follow-up, Decision, Open Question.
- Use one of these priority values: Low, Medium, High.
- Convert relative dates like today, tomorrow, kal, aaj, Monday, next week into YYYY-MM-DD when reasonably clear.
- Keep title short and dashboard-friendly.
- Keep summary concise.
- confidence_score must be a number between 0 and 1.

Return JSON only.
""".strip()


def _verifier_prompt(contact_name: str, message_text: str, message_time: datetime, recent_messages: list[dict]) -> str:
    today = message_time.date().isoformat()
    tomorrow = (message_time.date() + timedelta(days=1)).isoformat()

    return f"""
You are doing a second-pass action verification for a business chat workflow tool.

Current contact: {contact_name}
Current message time: {message_time.isoformat()}
Reference today date: {today}
Reference tomorrow date: {tomorrow}

Latest message:
{message_text}

Recent conversation context:
{_build_context_block(recent_messages)}

Verification rule:
If there is any reasonable chance that the latest message asks someone to do something, you must treat it as actionable.

Important:
- Be highly recall-oriented.
- Do not miss real tasks.
- If the message contains any requested action, action_signals must list it.
- If action_signals is not empty, has_action must be true.
- Compound instructions count as actionable.
- Polite wording still counts as actionable.
- Return compact JSON only.
""".strip()


@lru_cache(maxsize=1)
def _build_client():
    if not GEMINI_API_KEY:
        return None
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def score_to_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Medium"
    return "Low"


def _normalize_item_type(value: Any) -> str:
    text = str(value or "task").strip().lower()
    key = re.sub(r"[^a-z -]", "", text)
    return ALLOWED_ITEM_TYPES.get(key, "Task")


def _normalize_priority(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    return ALLOWED_PRIORITIES.get(text, "Medium")


def _normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(1.0, score))


def _normalize_has_action(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "yes", "1", "y"}


def _normalize_action_signals(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            cleaned.append(text[:120])
    return cleaned


def _normalize_due_date(value: Any, message_time: datetime, fallback_text: str) -> str | None:
    text = str(value or "").strip()
    lowered = text.lower()

    if lowered in {"today", "aaj", "aj"}:
        return message_time.date().isoformat()
    if lowered in {"tomorrow", "tmrw", "kal"}:
        return (message_time.date() + timedelta(days=1)).isoformat()

    for pattern in DATE_PATTERNS:
        if pattern.match(text):
            if "/" in text:
                day, month, year = text.split("/")
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            if re.match(r"^\d{1,2}-\d{1,2}-\d{4}$", text):
                day, month, year = text.split("-")
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            return text

    parsed = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    if parsed:
        return parsed.date().isoformat()

    lowered_fallback = fallback_text.lower()
    if re.search(r"\btomorrow\b|\bkal\b", lowered_fallback):
        return (message_time.date() + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b|\baaj\b|\baj\b", lowered_fallback):
        return message_time.date().isoformat()

    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, index in weekday_map.items():
        if re.search(rf"\b{name}\b", lowered_fallback):
            current = message_time.weekday()
            days_ahead = (index - current) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (message_time.date() + timedelta(days=days_ahead)).isoformat()

    return None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]

    return None


def _extract_payload(response: Any) -> dict[str, Any]:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    if parsed is not None and hasattr(parsed, "model_dump"):
        return parsed.model_dump()

    text = (getattr(response, "text", "") or "").strip()
    if not text:
        return {}

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        candidate = _extract_first_json_object(text)
        if candidate:
            return json.loads(candidate)
        raise


def _call_gemini(model: str, prompt: str, system_instruction: str) -> AIExtractionResult | None:
    client = _build_client()
    if client is None:
        logger.warning("Gemini client not available because GEMINI_API_KEY is missing")
        return None

    from google.genai import types
    from google.genai.errors import ServerError

    last_exception = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                    max_output_tokens=220,
                    response_mime_type="application/json",
                    response_json_schema=AIExtractionResult.model_json_schema(),
                ),
            )

            logger.info("Gemini raw response text: %s", getattr(response, "text", ""))
            payload = _extract_payload(response)
            return AIExtractionResult.model_validate(payload)

        except ServerError as exc:
            last_exception = exc
            logger.warning("Gemini ServerError on attempt %s/3: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            break

        except Exception as exc:
            last_exception = exc
            logger.exception("Gemini request failed")
            break

    if last_exception:
        logger.error("Gemini failed after retries: %s", last_exception)

    return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _extract_title_from_manual(text: str) -> str:
    cleaned = text.strip().rstrip(".?!")
    patterns = [
        (r"please\s+send\s+(.+?)($|\band\b|\bby\b|\btomorrow\b|\btoday\b)", "Send {0}"),
        (r"send\s+(.+?)($|\band\b|\bby\b|\btomorrow\b|\btoday\b)", "Send {0}"),
        (r"review\s+(.+?)($|\band\b|\bby\b|\btomorrow\b|\btoday\b)", "Review {0}"),
        (r"check\s+(.+?)($|\band\b|\bby\b|\btomorrow\b|\btoday\b)", "Check {0}"),
        (r"update\s+(.+?)($|\band\b|\bby\b|\btomorrow\b|\btoday\b)", "Update {0}"),
        (r"call\s+(.+?)($|\band\b|\bby\b|\btomorrow\b|\btoday\b)", "Call {0}"),
    ]
    lowered = cleaned.lower()
    for pattern, template in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            target = match.group(1).strip(" .,")
            if target:
                return template.format(target).strip().capitalize()[:72]
    return cleaned[:72]


def _manual_detection(original_text: str, normalized_text: str, message_time: datetime) -> list[dict]:
    rules = _load_manual_rules()
    task_keywords = rules.get("task_keywords", [])
    followup_keywords = rules.get("followup_keywords", [])
    decision_keywords = rules.get("decision_keywords", [])
    question_keywords = rules.get("question_keywords", [])
    deadline_keywords = rules.get("deadline_keywords", [])

    has_task_signal = _contains_any(normalized_text, task_keywords)
    has_followup_signal = _contains_any(normalized_text, followup_keywords)
    has_decision_signal = _contains_any(normalized_text, decision_keywords)
    has_question_signal = original_text.strip().endswith("?") or _contains_any(normalized_text, question_keywords)
    has_deadline_signal = _contains_any(normalized_text, deadline_keywords)

    if not any([has_task_signal, has_followup_signal, has_decision_signal, has_question_signal]):
        logger.info("Manual fallback found no actionable signal")
        return []

    item_type = "Task"
    confidence = 0.62
    reason = "Manual fallback matched actionable keywords."

    if has_followup_signal:
        item_type = "Follow-up"
        confidence = 0.66
        reason = "Manual fallback matched follow-up language."
    elif has_decision_signal and not has_task_signal:
        item_type = "Decision"
        confidence = 0.64
        reason = "Manual fallback matched decision language."
    elif has_question_signal and not has_task_signal:
        item_type = "Open Question"
        confidence = 0.58
        reason = "Manual fallback matched question language."

    if has_task_signal and has_deadline_signal:
        confidence = max(confidence, 0.78)
        reason = "Manual fallback matched an action request with deadline language."
    elif has_task_signal:
        confidence = max(confidence, 0.72)
        reason = "Manual fallback matched clear action-request language."

    due_date = _normalize_due_date(None, message_time, normalized_text)
    title = _extract_title_from_manual(original_text)
    priority = "High" if has_deadline_signal else "Medium"

    detection = {
        "item_type": item_type,
        "title": title,
        "summary": original_text.strip(),
        "source_preview": original_text.strip()[:180],
        "due_date": due_date,
        "confidence_score": round(confidence, 2),
        "confidence_label": score_to_label(confidence),
        "priority": priority,
        "notes": reason,
    }
    logger.info("Manual fallback created detection: %s", detection)
    return [detection]


def _build_detection(result: AIExtractionResult, original_text: str, normalized_text: str, message_time: datetime) -> dict[str, Any]:
    score = _normalize_score(result.confidence_score)
    item_type = _normalize_item_type(result.item_type)
    priority = _normalize_priority(result.priority)
    due_date = _normalize_due_date(result.due_date, message_time, normalized_text)
    signals = _normalize_action_signals(result.action_signals)

    title = (result.title or "").strip()
    if not title:
        if signals:
            title = signals[0].capitalize()
        else:
            title = _extract_title_from_manual(original_text)

    title = title[:72].rstrip(" .,;:")
    summary = (result.summary or original_text.strip()).strip()

    notes_parts = []
    if result.reason:
        notes_parts.append(f"AI reason: {result.reason}")
    if signals:
        notes_parts.append(f"Action signals: {', '.join(signals)}")

    return {
        "item_type": item_type,
        "title": title,
        "summary": summary,
        "source_preview": original_text.strip()[:180],
        "due_date": due_date,
        "confidence_score": round(score, 2),
        "confidence_label": score_to_label(score),
        "priority": priority,
        "notes": " | ".join(notes_parts) if notes_parts else "AI matched an actionable request.",
    }


def _is_actionable(result: AIExtractionResult) -> bool:
    return _normalize_has_action(result.has_action) or len(_normalize_action_signals(result.action_signals)) > 0


def classify_message_with_ai(
    text: str,
    contact_name: str,
    message_time: datetime,
    recent_messages: list[dict],
    ai_settings: dict,
) -> list[dict]:
    normalized_text = _normalize_text(text)

    if not ai_settings.get("enabled", True):
        logger.info("AI extraction disabled, using manual fallback")
        return _manual_detection(text, normalized_text, message_time)

    model = ai_settings.get("model") or "gemini-2.5-flash"
    configured_threshold = float(ai_settings.get("confidence_threshold", 0.58) or 0.58)

    primary_result = _call_gemini(
        model=model,
        prompt=_primary_prompt(contact_name, normalized_text, message_time, recent_messages),
        system_instruction=(
            "Understand the message like a human operator. "
            "If someone is being asked to do anything at all, mark it actionable and fill action_signals."
        ),
    )

    if primary_result and _is_actionable(primary_result):
        primary_score = _normalize_score(primary_result.confidence_score)
        primary_signals = _normalize_action_signals(primary_result.action_signals)

        if primary_signals or primary_score >= configured_threshold:
            detection = _build_detection(primary_result, text, normalized_text, message_time)
            logger.info("Gemini primary pass created detection: %s", detection)
            return [detection]

        logger.info(
            "Gemini primary pass looked actionable but confidence %.2f was below threshold %.2f; running verifier pass",
            primary_score,
            configured_threshold,
        )
    else:
        logger.info("Gemini primary pass did not produce an actionable result; running verifier pass")

    verifier_result = _call_gemini(
        model=model,
        prompt=_verifier_prompt(contact_name, normalized_text, message_time, recent_messages),
        system_instruction=(
            "You are the final safeguard against missing real tasks. "
            "If there is any requested action, set has_action=true and populate action_signals."
        ),
    )

    if verifier_result and _is_actionable(verifier_result):
        detection = _build_detection(verifier_result, text, normalized_text, message_time)
        logger.info("Gemini verifier pass created detection: %s", detection)
        return [detection]

    logger.info("Gemini unavailable or non-actionable; switching to manual fallback")
    return _manual_detection(text, normalized_text, message_time)
