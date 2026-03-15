"""Утилиты для извлечения и очистки текста резюме."""

import io
import logging
import re
from typing import Optional

import pdfplumber


MAX_TEXT_LENGTH = 6000


def extract_text_from_pdf(binary_data: bytes) -> str:
    """Извлекает текст из PDF и возвращает его как строку."""
    try:
        with pdfplumber.open(io.BytesIO(binary_data)) as pdf:
            text_chunks = [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        logging.exception("PDF parsing failed")
        return ""
    return "\n".join(text_chunks)


def clean_text(text: str) -> str:
    """Нормализует пробельные символы и укорачивает текст."""

    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:MAX_TEXT_LENGTH]


def parse_resume(uploaded_file: Optional[bytes], fallback_text: str) -> str:
    """Выбирает истоник текста и возвращает очищенную строку."""

    if uploaded_file:
        text = extract_text_from_pdf(uploaded_file)
    else:
        text = fallback_text

    if not text:
        return ""

    return clean_text(text)
