# AI Prescoring MVP

Локальный MVP-сервис для предварительной оценки кандидатов по тексту вакансии и резюме. Приложение объединяет два источника оценки:

1. **Эвристический скоринг** по текстовым признакам.
2. **LLM-оценку** через OpenAI.

Итоговый балл помогает быстро отсортировать кандидатов, но не заменяет ручную экспертную оценку.

---

## Что умеет приложение

- принимает текст вакансии;
- принимает резюме как PDF или как вставленный текст;
- считает `Hard score`, `Experience score`, `Soft score`;
- запрашивает у модели структурированную HR-оценку;
- формирует итоговый `Final score`;
- сохраняет историю кандидатов в `history.json`;
- позволяет сравнивать кандидатов в интерфейсе.

---

## Архитектура проекта

```text
app.py          Streamlit UI и orchestration
parser.py       Извлечение и очистка текста резюме
scoring.py      Эвристический скоринг, финальный score, история
gpt_service.py  Запрос к OpenAI и валидация JSON-ответа
models.py       Pydantic-модели
requirements.txt
```

### Основной поток

1. Пользователь вводит вакансию.
2. Загружает PDF или вставляет текст резюме.
3. `parser.py` извлекает и очищает текст.
4. `scoring.py` считает эвристику.
5. `gpt_service.py` получает структурированную оценку от модели.
6. `scoring.py` собирает итоговый балл.
7. Результат отображается в Streamlit и пишется в историю.

---

## Модель

В текущей версии используется модель **`gpt-4o-mini`** через OpenAI Chat Completions API.

Модель должна вернуть JSON следующей структуры:

```json
{
  "score": 0,
  "strong_sides": [],
  "weak_sides": [],
  "missing_skills": [],
  "summary": ""
}
```

> В `gpt_service.py` есть ручная очистка ответа модели (`_extract_json_payload`, `_sanitize_json`, `_repair_json`). Это повышает устойчивость MVP, но не является production-grade решением.

---

## Логика скоринга

### 1. Hard score

Считается как процент пересечения уникальных токенов вакансии и резюме.

Формула:

```text
Hard = (matched_tokens / vacancy_tokens) * 100
```

Особенность: сейчас это **простой токенный матчинг**, поэтому в оценку попадают не только навыки, но и любые значимые слова длиной от 4 символов.

### 2. Experience score

Из резюме извлекаются числа перед словами:
- `years`, `year`, `yrs`
- `лет`, `год`, `года`

Берется максимум найденных лет опыта и масштабируется до 100 по верхнему пределу в 15 лет.

Формула:

```text
Experience = min(extracted_years, 15) / 15 * 100
```

### 3. Soft score

В текущей версии soft skills считаются по фиксированному английскому словарю:

- communication
- teamwork
- leadership
- adaptability
- initiative
- problem-solving
- creativity
- trust
- empathy
- critical thinking

Формула:

```text
Soft = (matched_soft_skills / total_soft_skills) * 100
```

> Ограничение: блок soft skills пока слабо работает на русскоязычных резюме, если в тексте нет английских формулировок.

### 4. Heuristic score

Пользователь задает веса в боковой панели. По умолчанию:

- Hard skills — **60%**
- Experience — **25%**
- Soft skills — **15%**

Веса нормализуются автоматически.

Формула:

```text
Heuristic = Hard * W_hard + Experience * W_exp + Soft * W_soft
```

### 5. Final score

Итоговая оценка объединяет эвристику и GPT-оценку:

```text
Final = Heuristic * 0.45 + GPT_score * 0.55
```

Результат округляется до целого числа в диапазоне 0–100.

---

## Пример расчета

Допустим, получили:

- Hard = 22.06
- Experience = 80.0
- Soft = 60.0

При весах 60 / 25 / 15:

```text
Heuristic = 22.06 * 0.60 + 80.0 * 0.25 + 60.0 * 0.15
          = 13.236 + 20 + 9
          = 42.236
          = 42.24
```

Если GPT дал 95:

```text
Final = 42.24 * 0.45 + 95 * 0.55
      = 19.008 + 52.25
      = 71.258
      = 71
```

---

## Установка

### 1. Создать окружение

```bash
python -m venv .venv
```

### 2. Активировать окружение

**Windows:**

```bash
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Создать `.env`

```env
OPENAI_API_KEY=your_api_key_here
```

### 5. Запустить приложение

```bash
streamlit run app.py
```

---

## Зависимости

Текущий `requirements.txt`:

- `streamlit`
- `pdfplumber`
- `python-dotenv`
- `openai`
- `pydantic`
- `anthropic`

> `anthropic` сейчас в коде не используется и может быть удален из зависимостей.

---

## Формат истории

История сохраняется в `history.json` рядом с приложением. Каждая запись содержит:

- имя кандидата;
- фрагмент вакансии;
- `final_score`;
- `gpt_score`;
- `heuristic_score`;
- веса;
- GPT-ответ;
- timestamp.

---

## Известные ограничения

### 1. Hard score слишком грубый

Сейчас используется пересечение токенов, а не выделение обязательных и желательных навыков. Это значит, что score зависит от формулировок текста.

### 2. Soft skills ориентированы на английский словарь

Русскоязычные резюме могут получать заниженный soft score.

### 3. Возможна логическая ошибка в истории

В текущем `app.py` в `build_history_entry()` передается `heuristic_details`, где поле `"heuristic"` подменяется на `final_score`. Из-за этого в истории колонка `Эвристика` может содержать **не исходную эвристику, а уже финальный балл**.

Проблемный участок:

```python
entry = build_history_entry(
    candidate_name=candidate_name or "Безымянный кандидат",
    vacancy=vacancy,
    assessment=gpt_response,
    heuristic_details={
        **heuristic_details,
        "heuristic": final_score,
    },
    final_score=final_score,
)
```

### 4. Устаревшие вызовы библиотек

По логам уже видны предупреждения:

- `gpt_response.dict()` → нужно заменить на `gpt_response.model_dump()`;
- `datetime.utcnow()` → заменить на `datetime.now(UTC)`;
- `use_container_width=True` → заменить на `width="stretch"`.

### 5. Pydantic и datetime требуют обновления кода

Сейчас проект запускается, но часть вызовов уже помечена как deprecated.

---

## Что стоит исправить в первую очередь

### За 1 день

- исправить запись эвристики в историю;
- перевести `heuristic_score` в `float`;
- убрать deprecated-вызовы;
- вывести в UI отдельно `Hard`, `Experience`, `Soft`, `Heuristic`, `GPT`, `Final`.

### За 1 неделю

- сделать двуязычный словарь soft skills;
- улучшить извлечение опыта;
- добавить explainability по найденным/ненайденным навыкам;
- покрыть scoring unit-тестами.

### За 1 месяц

- заменить `history.json` на SQLite/Postgres;
- ввести версионирование логики скоринга;
- разделить must-have и nice-to-have требования вакансии;
- усилить обработку LLM-ответа через более строгий structured output.

---

## Рекомендованные точечные правки

### Pydantic

Было:

```python
gpt_response.dict()
```

Нужно:

```python
gpt_response.model_dump()
```

### Datetime

Было:

```python
from datetime import datetime
datetime.utcnow()
```

Нужно:

```python
from datetime import datetime, UTC
datetime.now(UTC)
```

### Streamlit

Было:

```python
st.dataframe(rows, use_container_width=True)
```

Нужно:

```python
st.dataframe(rows, width="stretch")
```

---

## Для кого подходит проект

Проект хорошо подходит для:

- пилота внутри HR / recruitment команды;
- быстрого первичного отбора кандидатов;
- демонстрации концепции прескоринга;
- сравнения кандидатов на одном потоке вакансий.

Проект пока **не подходит** как единственный источник решения о найме без ручной проверки.

---

## Краткий вывод

Это рабочий MVP с понятной архитектурой и полезной идеей гибридного скоринга. Сильная сторона проекта — простота, прозрачная формула итогового балла и возможность быстро получить структурированную HR-оценку. Основные слабые места — грубый `Hard score`, англоязычная логика `Soft score`, технические deprecated-вызовы и ошибка с записью эвристики в историю. После точечных доработок проект можно заметно усилить и использовать как практичный инструмент первичного скрининга кандидатов.
