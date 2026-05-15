# OpenClaw Integration

This guide describes how to use OpenClaw as the daily workflow runner for
Polyglo.

Polyglo should remain the source of truth for vocabulary, lessons, review
history, language settings, and quality control. OpenClaw should only trigger
the daily workflow, fetch the generated lesson, send it to your chosen channel,
and mark the lesson as sent.

## Target Workflow

Run this workflow every day at 8:00 AM:

1. Call Polyglo to generate today's lesson.
2. Read the generated Markdown message.
3. Send the Markdown to the destination you choose, such as Telegram, email,
   LINE, Slack, or Obsidian.
4. Mark the lesson as sent in Polyglo.
5. Leave review ratings to be filled in later from the Polyglo UI.

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

## Recommended OpenClaw Prompt

Use this as the OpenClaw task prompt:

```text
Create a daily 8:00 AM language learning workflow named "Polyglo Daily Vocabulary".

Every day:

1. Send POST http://127.0.0.1:8000/api/lessons/generate
   with JSON body:
   {"date":"{{today}}"}

2. Read the JSON response field:
   generated_message

3. Send generated_message exactly as Markdown to my configured learning channel.

4. After the message is successfully sent, send:
   POST http://127.0.0.1:8000/api/lessons/{{id}}/mark-sent

Rules:

- Do not invent vocabulary inside OpenClaw.
- Do not rewrite the generated Markdown unless I explicitly ask.
- If lesson generation fails because a language has no eligible active words,
  report the error and do not mark the lesson as sent.
- Polyglo is the source of truth for enabled languages, minimum levels,
  duplicate avoidance, lesson history, and review history.
```

Replace `{{today}}` with OpenClaw's date variable if it has one. If OpenClaw
does not provide a date variable, omit the `date` field and Polyglo will use
the server's current local date:

```json
{}
```

## API Flow

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

Send `generated_message` to the destination channel.

After the send succeeds:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/lesson-id/mark-sent
```

OpenClaw should call `mark-sent` only after the delivery step succeeds. If
delivery fails, leave the lesson as `pending` so you can retry safely.

## Language Configuration

Polyglo is not limited to five languages. Configure languages in the Settings
page:

- `code`: a short stable identifier, such as `en`, `id`, `ja`, `de`, `es`,
  `fr`, `ko`, `yue`, or `nan`.
- `name`: display name, such as `English`, `French`, or `Taiwanese Hokkien`.
- `minimum_level`: optional. Use any system that fits the language, such as
  `A2`, `B1`, `C1`, `N4`, `HSK3`, `TOPIK2`, `beginner`, or `intermediate`.
- `enabled`: enabled languages are included in each generated lesson.

Each generated lesson selects one active vocabulary item per enabled language.

## Quality Control

For the current MVP, add vocabulary manually or import curated data yourself.
OpenClaw should not generate new words directly into a lesson.

Recommended policy:

1. AI-generated vocabulary may be added as `draft`.
2. Review the word, example, translation, usage note, and level in Polyglo.
3. Change the item to `active` only after review.
4. Let OpenClaw send only generated lessons from active vocabulary.

This keeps the daily learning feed stable and prevents low-quality generated
entries from becoming part of your long-term vocabulary bank.

## Failure Handling

If OpenClaw receives an error like:

```text
No active vocabulary item found for French at A2+
```

Fix it in Polyglo:

1. Add more vocabulary for that language, or
2. Lower the language's minimum level, or
3. Temporarily disable that language in Settings.

Then rerun the OpenClaw task.

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
