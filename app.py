"""Streamlit interface for the prescoring MVP."""

import json
import logging
from datetime import datetime
from typing import Dict

import streamlit as st

from parser import parse_resume
from scoring import (
    append_history,
    build_history_entry,
    calculate_final_score,
    calculate_heuristic_score,
    load_history,
)
from gpt_service import get_assessment

logging.basicConfig(level=logging.INFO)


def _score_color(score: int) -> str:
    if score < 50:
        return "#d63447"
    if score < 75:
        return "#f7b731"
    return "#40c057"


def _render_score_block(score: int) -> None:
    color = _score_color(score)
    st.markdown(
        f"""
        <div style='background:{color};padding:24px;border-radius:12px;text-align:center;'>
            <p style='color:#fff;font-size:32px;margin:0;font-weight:bold;'>Финальный score</p>
            <p style='color:#fff;font-size:56px;margin:0;font-weight:800;'>{score}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _serialize_result(candidate_name: str, final_score: int, gpt_payload: Dict, heuristics: Dict) -> str:
    return json.dumps(
        {
            "candidate": candidate_name,
            "final_score": final_score,
            "gpt_response": gpt_payload,
            "heuristic": heuristics,
            "timestamp": datetime.utcnow().isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    )


def _display_history(history_entries) -> None:
    if not history_entries:
        st.info("История оценок пока пуста.")
        return

    sorted_history = sorted(history_entries, key=lambda entry: entry.final_score, reverse=True)
    st.subheader("История кандидатов")
    rows = []
    for entry in sorted_history:
        rows.append(
            {
                "Кандидат": entry.candidate_name,
                "Финальный score": entry.final_score,
                "GPT score": entry.gpt_score,
                "Эвристика": round(entry.heuristic_score, 2),
                "Дата": entry.timestamp.strftime("%Y-%m-%d %H:%M"),
            }
        )
    st.dataframe(rows, use_container_width=True)

    if len(sorted_history) >= 2:
        st.markdown("---")
        st.subheader("Сравнение кандидатов")
        options = {entry.id: entry for entry in sorted_history}
        keys = list(options.keys())
        a = st.selectbox("Кандидат 1", keys, format_func=lambda k: f"{options[k].candidate_name} ({options[k].final_score})")
        b = st.selectbox("Кандидат 2", keys, index=1, format_func=lambda k: f"{options[k].candidate_name} ({options[k].final_score})")
        if a and b and a != b:
            left, right = st.columns(2)
            for column, entry in zip((left, right), (options[a], options[b])):
                column.metric("Финальный score", entry.final_score)
                column.metric("GPT score", entry.gpt_score)
                column.metric("Эвристика", round(entry.heuristic_score, 2))
                column.write(f"**Сильные стороны:** {', '.join(entry.gpt_response.strong_sides)}")
                column.write(f"**Слабые стороны:** {', '.join(entry.gpt_response.weak_sides)}")
        else:
            st.warning("Выберите двух разных кандидатов для сравнения.")


def main() -> None:
    st.set_page_config(page_title="AI Prescoring", layout="wide")
    st.title("ИИ-прескоринг кандидатов")
    st.caption("Сервис для быстрой предоценки соответствия вакансии и резюме.")

    with st.sidebar:
        st.header("Настройки")
        hard_weight = st.slider("Hard skills weight (%)", 20, 80, 60)
        experience_weight = st.slider("Experience weight (%)", 0, 60, 25)
        soft_weight = st.slider("Soft skills weight (%)", 0, 40, 15)
        st.markdown("Весовые коэффициенты нормализуются автоматически.")

    vacancy = st.text_area("Описание вакансии", height=220)
    candidate_name = st.text_input("Имя кандидата", placeholder="Иван Иванов")
    resume_upload = st.file_uploader("Загрузите PDF резюме", type=["pdf"])
    resume_text = st.text_area("Или вставьте текст резюме", height=200)

    weights = {
        "hard": hard_weight,
        "experience": experience_weight,
        "soft": soft_weight,
    }

    submit = st.button("Оценить кандидата")

    if submit:
        if not vacancy.strip():
            st.error("Текст вакансии обязателен для оценки.")
            return

        resume_content = parse_resume(resume_upload.read() if resume_upload else None, resume_text)
        if not resume_content:
            st.error("Не удалось извлечь текст резюме. Проверьте файл или вставьте текст вручную.")
            return

        with st.spinner("Анализируем соответствие..."):
            try:
                heuristic_details = calculate_heuristic_score(vacancy, resume_content, weights)
                gpt_response = get_assessment(vacancy, resume_content)
                final_score = calculate_final_score(float(heuristic_details["heuristic"]), gpt_response.score)

                entry = build_history_entry(
                    candidate_name=candidate_name or "Безымянный кандидат",
                    vacancy=vacancy,
                    assessment=gpt_response,
                    heuristic_details=heuristic_details,
                    final_score=final_score,
                )
                append_history(entry)
            except Exception as error:
                logging.exception("Оценка отклонена")
                st.error(f"Не удалось выполнить оценку: {error}")
                return

        _render_score_block(entry.final_score)

        st.markdown("### Эвристический скоринг")
        h_cols = st.columns(4)
        h_cols[0].metric("Hard score", round(float(heuristic_details["hard"]), 2))
        h_cols[1].metric("Experience score", round(float(heuristic_details["experience"]), 2))
        h_cols[2].metric("Soft score", round(float(heuristic_details["soft"]), 2))
        h_cols[3].metric("Heuristic", round(float(heuristic_details["heuristic"]), 2))

        matched_soft = heuristic_details.get("soft_matched", [])
        if matched_soft:
            st.write("**Найденные soft skills:** " + ", ".join(matched_soft))
        else:
            st.write("**Найденные soft skills:** не обнаружены")

        st.caption(
            "Веса: "
            f"hard={round(float(heuristic_details['ratios']['hard']) * 100, 1)}%, "
            f"experience={round(float(heuristic_details['ratios']['experience']) * 100, 1)}%, "
            f"soft={round(float(heuristic_details['ratios']['soft']) * 100, 1)}%"
        )

        st.markdown("### Результаты GPT анализа")
        cols = st.columns(3)
        cols[0].write("**Сильные стороны:**")
        cols[0].write("* " + "\n* ".join(gpt_response.strong_sides or ["-"]))
        cols[1].write("**Слабые стороны:**")
        cols[1].write("* " + "\n* ".join(gpt_response.weak_sides or ["-"]))
        cols[2].write("**Чего не хватает:**")
        cols[2].write("* " + "\n* ".join(gpt_response.missing_skills or ["-"]))

        st.markdown("### Итоговое резюме")
        st.info(gpt_response.summary)

        serialized = _serialize_result(
            candidate_name=candidate_name or "Безымянный кандидат",
            final_score=entry.final_score,
            gpt_payload=gpt_response.dict(),
            heuristics=heuristic_details,
        )
        st.download_button(
            label="Скачать результат в JSON",
            data=serialized,
            file_name=f"prescore_{candidate_name or 'candidate'}_{datetime.utcnow().strftime('%Y%m%d%H%M')}.json",
            mime="application/json",
        )

    st.markdown("---")
    _display_history(load_history())


if __name__ == "__main__":
    main()