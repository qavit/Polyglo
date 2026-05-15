# Polyglo

Polyglo is a local-first Daily Polyglot Vocabulary Scheduler.

It manages a five-language vocabulary bank and generates a daily lesson with:

- English: C1+
- Indonesian: A2+
- Japanese: JLPT N4+
- German: B1+
- Spanish: A2+

The MVP uses only Python standard library modules and SQLite.

## Run

```bash
python3 app.py --seed
```

Then open:

```text
http://127.0.0.1:8000
```

The `--seed` flag adds sample vocabulary if it is not already present.

## API

- `GET /api/today`
- `GET /api/dashboard`
- `GET /api/vocabulary`
- `GET /api/lessons`
- `GET /api/reviews`
- `POST /api/lessons/generate`
- `POST /api/lessons/:id/mark-sent`
- `POST /api/vocabulary`
- `PATCH /api/vocabulary/:id`
- `POST /api/reviews`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/generate \
  -H 'Content-Type: application/json' \
  -d '{"date":"2026-05-16"}'
```

## Data

SQLite database:

```text
polyglo.sqlite3
```

Tables:

- `vocabulary_items`
- `daily_lessons`
- `daily_lesson_items`
- `review_logs`
- `settings`
