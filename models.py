"""Pydantic-модели, применяемые в логике прескоринга."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field


class AssessmentResponse(BaseModel):
    """Структурированный ответ GPT с обязательной проверкой."""

    score: int = Field(..., ge=0, le=100)
    strong_sides: List[str]
    weak_sides: List[str]
    missing_skills: List[str]
    summary: str


class HistoryEntry(BaseModel):
    """Запись истории для аудита и сравнения кандидатов."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    candidate_name: str
    vacancy_snippet: str
    final_score: int
    gpt_score: int
    heuristic_score: float
    ratios: Dict[str, float]
    gpt_response: AssessmentResponse
    timestamp: datetime = Field(default_factory=datetime.utcnow)