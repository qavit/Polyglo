# OpenClaw Integration

This guide describes the OpenClaw workflow for Polyglo.

The product model is:

- OpenClaw generates vocabulary and delivers the daily lesson in one job.
- Polyglo stores vocabulary, generates lessons, and tracks review history.
- OpenClaw runs a second evening job to send the daily quiz and record your ratings.

AI-generated words go directly to `active` status, so they are eligible for
the same day's lesson without any manual review step.

## Roles

| System | Responsibility |
|---|---|
| OpenClaw | Scheduled workflows, AI word generation, lesson delivery, quiz delivery |
| Polyglo | Language settings, vocabulary storage, lesson generation, review history |
| You | Adjust language settings, archive unwanted words, rate quiz responses |

## Recommended Daily Workflow

Use two OpenClaw jobs.

### Job 1: Generate and Deliver

Run this at your study time, for example at 8:00 AM.

1. Call `GET /api/generation-plan`.
2. Generate one word per enabled language.
3. Call `POST /api/vocabulary/candidates`. The words are added as `active` immediately.
4. Call `POST /api/lessons/generate`. This picks from all active words including
   the ones just added.
5. Send `generated_message` to your destination.
6. Call `POST /api/lessons/{id}/mark-sent`.

### Job 2: Daily Quiz

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

## Job 1 Prompt

Use this as the OpenClaw prompt for the morning job:

```text
Create a daily 8:00 AM workflow named "Polyglo Daily Vocabulary".

Every day:

1. Send:
   GET http://127.0.0.1:8000/api/generation-plan

2. Read:
   - languages
   - candidate_defaults (source and status for new words)
   - duplicate_avoidance_days
   - existing_words
   - recent_lesson_words

3. For each enabled language, generate one vocabulary word that satisfies
   that language's minimum_level.

4. Avoid:
   - words already present in existing_words
   - words recently used in recent_lesson_words
   - proper nouns unless they are especially useful
   - joke words, obscure trivia, or low-utility vocabulary

5. Each word must include:
   - language
   - word
   - reading, if useful (e.g. Japanese kana, Chinese pinyin)
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

7. Send:
   POST http://127.0.0.1:8000/api/lessons/generate

   Body:
   {}

8. Read the response fields:
   - id
   - generated_message

9. Send generated_message exactly as Markdown to my configured learning channel.

10. After the message is successfully delivered, send:
    POST http://127.0.0.1:8000/api/lessons/{{id}}/mark-sent

Rules:

- Do not rewrite generated_message.
- If Polyglo skips a duplicate word, report it and continue.
- If a language is missing or invalid, report the API error and continue with
  the remaining languages.
- If lesson generation fails because a language has no eligible active words,
  report the error and do not mark the lesson as sent.
- Only call mark-sent after the delivery step succeeds.
```

## Job 2 Prompt

Use this as the OpenClaw prompt for the evening quiz job:

```text
Create a daily 8:00 PM workflow named "Polyglo Daily Quiz".

Every day:

1. Send:
   GET http://127.0.0.1:8000/api/quiz

2. Read the items array. Each item has: vocabulary_item_id, word, language,
   level, meaning_zh, meaning_en, example_sentence, collocation, note, mnemonic.

3. Send one recall prompt per word to my configured learning channel:

   Daily Review — {{date}}

   {{#each items}}
   {{@index+1}}. {{language}} · {{level}}
      What does "{{word}}" mean?
      Reply: {{word}} <rating 0–5>
   {{/each}}

4. When I reply, parse each line for a word and a numeric rating.

5. For each rated word, match the word text back to vocabulary_item_id from
   step 2, then send:

   POST http://127.0.0.1:8000/api/reviews

   Body:
   {
     "vocabulary_item_id": "<matched id>",
     "rating": <0–5>,
     "recall_success": <true if rating >= 3, else false>,
     "review_date": "<today's date YYYY-MM-DD>"
   }

Rules:

- Send one POST /api/reviews per rated word.
- If a word in my reply does not match any quiz item, ask me to clarify.
- If I do not reply within 15 minutes, do nothing. Do not submit blank ratings.
- Do not fabricate ratings.
```

## API Reference

### Generation Plan

```bash
curl http://127.0.0.1:8000/api/generation-plan
```

Example response:

```json
{
  "date": "2026-05-16",
  "duplicate_avoidance_days": 30,
  "candidate_defaults": {
    "source": "ai",
    "status": "active"
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

### Create Candidates

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

Response:

```json
{
  "created": [
    {
      "id": "new-item-id",
      "source": "ai",
      "status": "active"
    }
  ],
  "skipped": []
}
```

### Generate and Deliver Lesson

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/generate \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Response:

```json
{
  "id": "lesson-id",
  "lesson_date": "2026-05-16",
  "status": "pending",
  "generated_message": "### Daily Vocabulary\nDate: 2026-05-16\n..."
}
```

Mark as sent after delivery:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/lesson-id/mark-sent
```

### Quiz

```bash
curl http://127.0.0.1:8000/api/quiz
# or for a past date:
curl http://127.0.0.1:8000/api/quiz?date=2026-05-15
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

## Failure Handling

If candidate generation returns `skipped`, OpenClaw reports the skipped items
and their reasons. Duplicates are intentionally skipped — this is expected.

If lesson generation fails with:

```text
No active vocabulary item found for French at A2+
```

Fix it in Polyglo:

1. Add vocabulary manually for that language, or
2. Lower the language's minimum level, or
3. Temporarily disable that language in Settings.

Then rerun the job.

## Archiving Unwanted Words

Since AI words go directly to `active`, you can remove a word you dislike by
opening Polyglo's Vocabulary Bank and clicking **Archive**. Archived words are
excluded from future lessons but preserved for your records.

You cannot delete a word that appeared in a sent lesson. Archive it instead.

## Obsidian Option

If your destination is Obsidian, configure OpenClaw to append `generated_message`
to a daily note or vocabulary note.

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

Keep review scores in Polyglo if you want spaced repetition data. Use Obsidian
for reading and personal notes.
