"""Логика эвристической оценки и хранения истории."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set, Union

from models import AssessmentResponse, HistoryEntry


HISTORY_FILE = Path(__file__).parent / "history.json"

SOFT_SKILL_PATTERNS: Dict[str, List[str]] = {
    "communication": [
        r"\bcommunication\b",
        r"\bcommunicator\b",
        r"\bкоммуникац\w*\b",
        r"\bкоммуникабельн\w*\b",
        r"\bобщени\w*\b",
        r"\bпереговор\w*\b",
    ],
    "teamwork": [
        r"\bteamwork\b",
        r"\bteam player\b",
        r"\bкомандн\w+\s+работ\w*\b",
        r"\bработа\w*\s+в\s+команде\b",
        r"\bработал\w*\s+в\s+команде\b",
        r"\bкоманд\w*\b",
    ],
    "leadership": [
        r"\bleadership\b",
        r"\bleader\b",
        r"\bлидер\w*\b",
        r"\bруковод\w*\b",
        r"\bуправлен\w*\b",
    ],
    "adaptability": [
        r"\badaptability\b",
        r"\badaptable\b",
        r"\bгибк\w*\b",
        r"\bадаптив\w*\b",
        r"\bадаптац\w*\b",
    ],
    "initiative": [
        r"\binitiative\b",
        r"\bproactive\b",
        r"\bинициатив\w*\b",
        r"\bпроактив\w*\b",
        r"\bсамостоятельн\w*\b",
    ],
    "problem_solving": [
        r"\bproblem[- ]solving\b",
        r"\bproblem solving\b",
        r"\bsolve\w*\s+problems?\b",
        r"\bрешени\w*\s+проблем\w*\b",
        r"\bрешени\w*\s+задач\w*\b",
        r"\bустранени\w*\s+проблем\w*\b",
    ],
    "creativity": [
        r"\bcreativity\b",
        r"\bcreative\b",
        r"\bкреатив\w*\b",
        r"\bтворческ\w*\b",
    ],
    "trust": [
        r"\btrust\b",
        r"\breliable\b",
        r"\bнадежн\w*\b",
        r"\bдовер\w*\b",
        r"\bответственн\w*\b",
    ],
    "empathy": [
        r"\bempathy\b",
        r"\bempathetic\b",
        r"\bэмпати\w*\b",
        r"\bэмпатич\w*\b",
    ],
    "critical_thinking": [
        r"\bcritical thinking\b",
        r"\banalytical thinking\b",
        r"\bкритическ\w+\s+мышлен\w*\b",
        r"\bаналитическ\w+\s+мышлен\w*\b",
        r"\bсистемн\w+\s+мышлен\w*\b",
    ],
}


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Нормализует веса, чтобы их сумма равнялась 1, и возвращает значения по умолчанию при необходимости."""
    total = sum(weights.values())
    if not total:
        logging.debug("Сумма весов равна нулю, используются значения по умолчанию.")
        return {"hard": 0.6, "experience": 0.25, "soft": 0.15}
    return {key: value / total for key, value in weights.items()}


def _normalize_text(text: str) -> str:
    """Приводит текст к удобному виду для поиска по шаблонам."""
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _token_set(text: str) -> Iterable[str]:
    """Извлекает уникальные токены длиной от четырех символов из текста для сопоставления навыков."""
    return set(
        token.lower()
        for token in re.findall(r"\b[\wа-яёА-ЯЁ-]{4,}\b", text)
        if len(token) >= 4
    )


def calculate_hard_skill_score(vacancy: str, resume: str) -> float:
    """Оценивает процент совпадений ключевых токенов между вакансией и резюме."""
    vacancy_tokens = _token_set(vacancy)
    resume_tokens = _token_set(resume)
    if not vacancy_tokens:
        return 0.0
    match_count = len(vacancy_tokens & resume_tokens)
    return round((match_count / len(vacancy_tokens)) * 100, 2)


def calculate_experience_score(resume: str) -> float:
    """Извлекает годы опыта и масштабирует результат до диапазона 0-100 на основе верхнего предела."""
    years = [
        float(match)
        for match in re.findall(
            r"(\d+(?:\.\d+)?)\s*(?:years?|лет|yrs|года|год)",
            resume,
            flags=re.IGNORECASE,
        )
    ]
    extracted = max(years, default=0.0)
    scaled = min(extracted, 15.0) / 15.0
    return round(scaled * 100, 2)


def extract_soft_skill_matches(resume: str) -> Set[str]:
    """Возвращает канонические soft skills, найденные в резюме на русском или английском."""
    normalized_text = _normalize_text(resume)
    found: Set[str] = set()

    for skill_name, patterns in SOFT_SKILL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized_text, flags=re.IGNORECASE):
                found.add(skill_name)
                break

    return found


def calculate_soft_skill_score(resume: str) -> Dict[str, Union[float, List[str], int]]:
    """Считает soft skills по двуязычному словарю и возвращает score с деталями."""
    matched = sorted(extract_soft_skill_matches(resume))
    total = len(SOFT_SKILL_PATTERNS)
    score = round((len(matched) / total) * 100, 2) if total else 0.0
    return {
        "score": score,
        "matched": matched,
        "matched_count": len(matched),
        "total": total,
    }


def calculate_heuristic_score(
    vacancy: str, resume: str, weights: Dict[str, float]
) -> Dict[str, Union[float, Dict[str, float], List[str], int]]:
    normalized_weights = _normalize_weights(weights)
    hard = calculate_hard_skill_score(vacancy, resume)
    experience = calculate_experience_score(resume)

    soft_result = calculate_soft_skill_score(resume)
    soft = float(soft_result["score"])

    weighted = (
        hard * normalized_weights["hard"]
        + experience * normalized_weights["experience"]
        + soft * normalized_weights["soft"]
    )

    return {
        "hard": hard,
        "experience": experience,
        "soft": soft,
        "soft_matched": soft_result["matched"],
        "soft_matched_count": soft_result["matched_count"],
        "soft_total": soft_result["total"],
        "heuristic": round(weighted, 2),
        "ratios": normalized_weights,
    }


def calculate_final_score(heuristic_score: float, gpt_score: int) -> int:
    """Сочетает эвристическую и GPT-оценки по фиксированным коэффициентам для получения итогового балла."""
    final = (heuristic_score * 0.45) + (gpt_score * 0.55)
    return min(100, max(0, int(round(final))))


def load_history() -> List[HistoryEntry]:
    """Возвращает ранее сохраненные оценки, если файл истории доступен."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open(encoding="utf-8") as handler:
            data = json.load(handler)
        return [HistoryEntry.parse_obj(entry) for entry in data]
    except Exception:
        logging.exception("Не удалось загрузить историю оценок")
        return []


def _persist_history(history: List[HistoryEntry]) -> None:
    """Сохраняет обновленную историю оценок в файл в читаемом формате JSON."""
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as handler:
        sanitized = []
        for entry in history:
            record = entry.dict()
            record["timestamp"] = entry.timestamp.isoformat()
            sanitized.append(record)
        json.dump(sanitized, handler, ensure_ascii=False, indent=2)


def append_history(entry: HistoryEntry) -> None:
    history = load_history()
    history.append(entry)
    _persist_history(history)


def build_history_entry(
    candidate_name: str,
    vacancy: str,
    assessment: AssessmentResponse,
    heuristic_details: Dict[str, Union[float, Dict[str, float], List[str], int]],
    final_score: int,
) -> HistoryEntry:
    return HistoryEntry(
        candidate_name=candidate_name,
        vacancy_snippet=vacancy.strip()[:300],
        final_score=final_score,
        gpt_score=assessment.score,
        heuristic_score=float(heuristic_details["heuristic"]),
        ratios={
            "hard": round(float(heuristic_details["ratios"]["hard"]), 2),
            "experience": round(float(heuristic_details["ratios"]["experience"]), 2),
            "soft": round(float(heuristic_details["ratios"]["soft"]), 2),
        },
        gpt_response=assessment,
    )