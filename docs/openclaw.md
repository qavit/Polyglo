# OpenClaw Integration

This guide describes the intended OpenClaw workflow for Polyglo.

The product model is:

- OpenClaw generates vocabulary candidates.
- Polyglo stores those candidates as reviewable backend records.
- You approve good candidates in Polyglo.
- Polyglo generates lessons only from approved `active` vocabulary.
- OpenClaw delivers the generated lesson and marks it as sent.

This keeps the AI creative loop while preserving a quality gate before words
enter your long-term learning feed.

## Roles

| System | Responsibility |
|---|---|
| OpenClaw | Scheduled workflow, AI candidate generation, delivery |
| Polyglo | Language settings, candidate storage, review gate, lesson history, review logs |
| You | Approve candidates, adjust language settings, review learned words |

## Recommended Daily Workflow

Use two OpenClaw jobs.

### Job 1: Generate Candidates

Run this before your learning time, for example at 7:30 AM.

1. Call `GET /api/generation-plan`.
2. Generate one candidate word per enabled language.
3. Call `POST /api/vocabulary/candidates`.
4. Stop. Do not send these words yet.

The candidates enter Polyglo as:

```json
{
  "source": "ai",
  "status": "draft"
}
```

Review them in Polyglo's Vocabulary Bank. Use the `AI Drafts` filter, then
click `Approve` for candidates you want to make eligible for lessons.

### Job 2: Deliver Lesson

Run this at the time you want to study, for example at 8:00 AM.

1. Call `POST /api/lessons/generate`.
2. Read the `generated_message` field.
3. Send `generated_message` exactly as Markdown to your destination.
4. After delivery succeeds, call `POST /api/lessons/{id}/mark-sent`.

This job uses only `active` vocabulary, so unreviewed AI drafts are never sent
by accident.

### Job 3: Daily Quiz

Run this in the evening, for example at 8:00 PM, to close the review loop.

1. Call `GET /api/quiz` (or `GET /api/quiz?date=YYYY-MM-DD` for a past date).
2. Read the `items` array. Each item contains the word and its full metadata.
3. For each word, send a recall prompt to your destination. For example:

```
Daily Review — 2026-05-16

1. English · C1
   What does "ameliorate" mean?
   Reply: ameliorate 3 (or 0–5 rating)

2. Japanese · N4
   What does「相談」mean?
   Reply: 相談 5
```

4. When the user replies, parse the word and rating from their message.
5. For each rated word, call `POST /api/reviews`:

```json
{
  "vocabulary_item_id": "<id from quiz item>",
  "rating": 4,
  "recall_success": true,
  "review_date": "2026-05-16"
}
```

Polyglo will compute the next review date automatically using spaced repetition.
Words that are due for review will be surfaced again in the next day's lesson.

#### Quiz API

```bash
curl http://127.0.0.1:8000/api/quiz
```

Example response:

```json
{
  "date": "2026-05-16",
  "lesson_id": "abc123",
  "items": [
    {
      "vocabulary_item_id": "uuid",
      "word": "ameliorate",
      "reading": "",
      "language": "en",
      "level": "C1",
      "part_of_speech": "verb",
      "meaning_zh": "改善、改良",
      "meaning_en": "to make a bad situation better",
      "example_sentence": "...",
      "example_translation_zh": "...",
      "collocation": "ameliorate a problem",
      "note": "...",
      "mnemonic": "..."
    }
  ]
}
```

Submit a review:

```bash
curl -X POST http://127.0.0.1:8000/api/reviews \
  -H 'Content-Type: application/json' \
  -d '{
    "vocabulary_item_id": "uuid",
    "rating": 4,
    "recall_success": true,
    "review_date": "2026-05-16"
  }'
```

## Before Scheduling

Start Polyglo somewhere OpenClaw can reach it:

```bash
python3 app.py --host 127.0.0.1 --port 8000
```

If OpenClaw runs on another machine or container, bind Polyglo to a reachable
host and protect that endpoint yourself:

```bash
python3 app.py --host 0.0.0.0 --port 8000
```

For the MVP, Polyglo has no account system or API key. Keep it on a trusted
local network or behind your own reverse proxy if exposing it outside localhost.

## Candidate Generation Prompt

Use this as the OpenClaw prompt for Job 1:

```text
Create a daily workflow named "Polyglo Generate Vocabulary Candidates".

Every day:

1. Send:
   GET http://127.0.0.1:8000/api/generation-plan

2. Read:
   - languages
   - duplicate_avoidance_days
   - existing_words
   - recent_lesson_words
   - required_fields

3. For each enabled language, generate one vocabulary candidate that satisfies
   that language's minimum_level.

4. Avoid:
   - words already present in existing_words
   - words recently used in recent_lesson_words
   - proper nouns unless they are especially useful
   - joke words, obscure trivia, or low-utility vocabulary

5. Each candidate must include:
   - language
   - word
   - reading, if useful
   - part_of_speech
   - level
   - meaning_zh
   - meaning_en
   - example_sentence
   - example_translation_zh
   - collocation
   - note
   - mnemonic

6. Send:
   POST http://127.0.0.1:8000/api/vocabulary/candidates

   Body:
   {
     "items": [
       {
         "language": "...",
         "word": "...",
         "reading": "...",
         "part_of_speech": "...",
         "level": "...",
         "meaning_zh": "...",
         "meaning_en": "...",
         "example_sentence": "...",
         "example_translation_zh": "...",
         "collocation": "...",
         "note": "...",
         "mnemonic": "..."
       }
     ]
   }

Rules:

- Store generated vocabulary only as candidates.
- Do not mark candidates active.
- Do not send the generated candidates to me as the daily lesson.
- If Polyglo skips a duplicate, report the skipped word and continue.
- If a language is missing or invalid, report the API error.
```

## Candidate API

Read the generation plan:

```bash
curl http://127.0.0.1:8000/api/generation-plan
```

Example response shape:

```json
{
  "date": "2026-05-16",
  "duplicate_avoidance_days": 30,
  "candidate_defaults": {
    "source": "ai",
    "status": "draft"
  },
  "languages": [
    {
      "code": "en",
      "name": "English",
      "minimum_level": "C1",
      "enabled": 1
    }
  ],
  "existing_words": {
    "en": [
      {
        "language": "en",
        "word": "ameliorate",
        "level": "C1",
        "status": "active",
        "source": "manual"
      }
    ]
  },
  "recent_lesson_words": {}
}
```

Create AI candidates:

```bash
curl -X POST http://127.0.0.1:8000/api/vocabulary/candidates \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [
      {
        "language": "en",
        "word": "mitigate",
        "reading": "",
        "part_of_speech": "verb",
        "level": "C1",
        "meaning_zh": "緩和、減輕",
        "meaning_en": "to make something less severe or harmful",
        "example_sentence": "The new policy aims to mitigate the impact of rising rents.",
        "example_translation_zh": "新政策旨在減輕租金上漲造成的影響。",
        "collocation": "mitigate risk; mitigate damage",
        "note": "Often used in formal, policy, risk, and environmental contexts.",
        "mnemonic": "Think of making a problem milder."
      }
    ]
  }'
```

The response includes `created` and `skipped` arrays:

```json
{
  "created": [
    {
      "id": "new-item-id",
      "source": "ai",
      "status": "draft"
    }
  ],
  "skipped": []
}
```

## Lesson Delivery Prompt

Use this as the OpenClaw prompt for Job 2:

```text
Create a daily 8:00 AM workflow named "Polyglo Deliver Daily Vocabulary".

Every day:

1. Send:
   POST http://127.0.0.1:8000/api/lessons/generate

   Body:
   {}

2. Read the response fields:
   - id
   - generated_message

3. Send generated_message exactly as Markdown to my configured learning channel.

4. After the message is successfully delivered, send:
   POST http://127.0.0.1:8000/api/lessons/{{id}}/mark-sent

Rules:

- Do not generate new words in this workflow.
- Do not rewrite generated_message.
- If lesson generation fails because a language has no eligible active words,
  report the error and do not mark the lesson as sent.
- Only call mark-sent after the delivery step succeeds.
```

## Lesson API

Generate or fetch today's lesson:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/generate \
  -H 'Content-Type: application/json' \
  -d '{}'
```

The response includes:

```json
{
  "id": "lesson-id",
  "lesson_date": "2026-05-16",
  "status": "pending",
  "generated_message": "### Daily Vocabulary\nDate: 2026-05-16\n..."
}
```

After the send succeeds:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/lesson-id/mark-sent
```

## Review Workflow

In Polyglo:

1. Open Vocabulary Bank.
2. Click `AI Drafts`.
3. Review the generated word, level, translations, example, note, and mnemonic.
4. Click `Approve` to change it from `draft` to `active`.
5. Leave questionable words as `draft` or archive them.

Only `active` words are eligible for lessons.

## Failure Handling

If candidate generation returns `skipped`, OpenClaw should report the skipped
items and their reasons. Duplicates are intentionally skipped.

If lesson delivery receives an error like:

```text
No active vocabulary item found for French at A2+
```

Fix it in Polyglo:

1. Approve AI drafts for that language, or
2. Add vocabulary manually, or
3. Lower the language's minimum level, or
4. Temporarily disable that language in Settings.

Then rerun the lesson delivery job.

## Obsidian Option

If your destination is Obsidian, configure OpenClaw to append the
`generated_message` Markdown to a daily note or vocabulary note.

Suggested path pattern:

```text
Daily Vocabulary/{{date}}.md
```

Suggested content:

```text
{{generated_message}}

## Review

- Rating:
- Recall:
- Notes:
```

Keep review scores in Polyglo if you want spaced repetition data later. Use
Obsidian for reading and personal notes.
