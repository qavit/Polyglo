# Polyglo

Polyglo is a local-first daily vocabulary scheduler.

It manages vocabulary banks for any language and generates a daily lesson from
the enabled languages you configure. Each language can have its own optional
minimum level, such as `A2`, `B1`, `N4`, `beginner`, or any label that fits your
learning system.

The MVP uses only Python standard library modules and SQLite.

## Run

```bash
python3 app.py --seed
```

Then open:

```text
http://127.0.0.1:8000
```

The `--seed` flag adds sample languages and vocabulary if they are not already
present. The samples are only demo data; Polyglo itself is not limited to those
languages.

## API

- `GET /api/today`
- `GET /api/dashboard`
- `GET /api/vocabulary`
- `GET /api/languages`
- `GET /api/lessons`
- `GET /api/reviews`
- `POST /api/lessons/generate`
- `POST /api/lessons/:id/mark-sent`
- `POST /api/languages`
- `PATCH /api/languages/:code`
- `POST /api/vocabulary`
- `PATCH /api/vocabulary/:id`
- `POST /api/reviews`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/generate \
  -H 'Content-Type: application/json' \
  -d '{"date":"2026-05-16"}'
```

## OpenClaw

Use OpenClaw as the daily trigger and delivery runner. Polyglo should remain the
source of truth for vocabulary, generated lessons, review history, and language
settings.

See [docs/openclaw.md](docs/openclaw.md) for the recommended daily 8:00 AM
workflow, prompt, API calls, and failure handling.

## Data

SQLite database:

```text
polyglo.sqlite3
```

Tables:

- `languages`
- `vocabulary_items`
- `daily_lessons`
- `daily_lesson_items`
- `review_logs`
- `settings`

## License

MIT
