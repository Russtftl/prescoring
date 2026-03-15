# AI Prescoring MVP

Производственный прототип, где `Streamlit` принимает описание вакансии и резюме, композитно рассчитывает итоговый score и сохраняет историю.

## Стек

- Python 3.11+
- Streamlit (интерфейс)
- OpenAI API 1.0+ (Chat Completions)
- `pdfplumber` для извлечения текста из PDF
- `python-dotenv` для безопасной загрузки ключей
- `pydantic` для строгой валидации ответов GPT

## Структура

- [`app.py`](project/app.py:1): UI, отображение результата, управление историей и скачивание JSON.
- [`parser.py`](project/parser.py:1): извлекает и чистит текст резюме, ограничивает длину.
- [`gpt_service.py`](project/gpt_service.py:1): вызывает OpenAI 1.0+ и проверяет JSON с retries / repair.
- [`scoring.py`](project/scoring.py:1): эвристика hard/soft/experience, хранение истории и агрегирование результата.
- [`models.py`](project/models.py:1): Pydantic-модели для ответа и истории.
- [`requirements.txt`](project/requirements.txt:1): зависимости.
- [`.env.example`](project/.env.example:1): переменные окружения.

## Быстрый запуск

1. Скопировать `.env.example` → `.env`, добавить `OPENAI_API_KEY`.
2. Установить зависимости:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Запустить приложение:
   ```bash
   streamlit run app.py
   ```

## Инфраструктура и UX

- Слайдеры веса hard/experience/soft skills в сайдбаре, нормализуемые автоматически.
- Цветной KPI (красный/жёлтый/зелёный) для финального score.
- Оценка комбинирует GPT (55%) и эвристику (45%); логика записана в `scoring.py`.
- История сохраняется в `history.json`; можно сравнивать двух кандидатов и скачивать JSON-отчет.

## Безопасность и устойчивость

- OpenAI API ключ хранится в `.env`, читается через `dotenv`.
- Запросы к GPT обёрнуты в retries и логируются через модульный `logging`.
- JSON строго валидируется `pydantic`; при некорректном ответе выполняется повторный запрос.
