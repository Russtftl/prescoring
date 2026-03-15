"""OpenAI powered scoring service with strict schema enforcement."""

import json
import logging
import os
import time
from typing import Optional

import openai
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from models import AssessmentResponse


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLIENT: Optional[OpenAI] = None

if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY is not set. GPT service will not function correctly.")
else:
    CLIENT = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = (
    "Ты профессиональный HR-аналитик. Оцени соответствие кандидата вакансии."
    " Верни валидный JSON строго в формате, указанном в документации."
    " Строковые поля не должны содержать переносов строк; если они нужны, используй '\\n'."
)


def _extract_json_payload(raw_text: str) -> str:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw_text[start : end + 1]
    return raw_text


def _strip_code_block(text: str) -> str:
    trimmed = text.strip()
    if trimmed.startswith("```") and trimmed.endswith("```"):
        return trimmed.strip("`\n ")
    return trimmed


def _sanitize_json(raw: str) -> str:
    buffer = []
    in_string = False
    escaped = False
    for char in raw:
        if char == '"' and not escaped:
            in_string = not in_string
        if char == '\\' and not escaped:
            escaped = True
            buffer.append(char)
            continue
        if char == '\r' and in_string:
            buffer.append('\\r')
            escaped = False
            continue
        if char == '\n' and in_string:
            buffer.append('\\n')
            escaped = False
            continue
        buffer.append(char)
        escaped = False
    return ''.join(buffer)


def _repair_json(payload: str) -> str:
    if payload.count("\"") % 2 != 0:
        payload += "\""
    open_braces = payload.count("{") - payload.count("}")
    if open_braces > 0:
        payload += "}" * open_braces
    return payload


def get_assessment(vacancy: str, resume: str, retries: int = 3) -> AssessmentResponse:
    """Call OpenAI and validate the response against `AssessmentResponse`."""

    if not vacancy or not resume:
        raise ValueError("Vacancy and resume text are required to run GPT assessment.")

    if CLIENT is None:
        raise RuntimeError("OpenAI API key is missing; please configure OPENAI_API_KEY in .env.")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Вакансия:\n{vacancy.strip()}\n\n"
                f"Резюме:\n{resume.strip()}\n\n"
                "Верни ответ только как JSON в формате: {{\"score\": int, \"strong_sides\": [...], "
                "\"weak_sides\": [...], \"missing_skills\": [...], \"summary\": string}}."
            ),
        },
    ]

    for attempt in range(1, retries + 1):
        try:
            response = CLIENT.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )
        except OpenAIError as error:
            logging.exception("OpenAI API request failed")
            if attempt == retries:
                raise
            time.sleep(1)
            continue

        content = response.choices[0].message.content
        payload = _strip_code_block(content)
        payload = _extract_json_payload(payload)
        payload = payload.strip()
        payload = _sanitize_json(payload)
        payload = _repair_json(payload)

        try:
            parsed = json.loads(payload, strict=False)
            assessment = AssessmentResponse.parse_obj(parsed)
            return assessment
        except (json.JSONDecodeError, ValidationError) as error:
            logging.warning(
                "GPT assessment response validation failed on attempt %s: %s", attempt, error
            )
            if attempt == retries:
                raise RuntimeError("Failed to produce a valid assessment JSON after retries.")
            time.sleep(1)
            continue

    raise RuntimeError("Unable to get assessment from GPT service.")
