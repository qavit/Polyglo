"""Tests for lesson generation, SR logic, and duplicate detection."""
import sys
from pathlib import Path
from datetime import date, timedelta
import pytest

sys.path.insert(0, str(Path(__file__).parent))

import app


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DB_PATH", tmp_path / "test.sqlite3")
    app.init_db()


def _add_language(code: str, name: str, minimum_level: str = "") -> None:
    app.create_language({"code": code, "name": name, "minimum_level": minimum_level})


def _add_word(**kwargs) -> dict:
    defaults = {
        "part_of_speech": "noun",
        "meaning_zh": "測試",
        "meaning_en": "test",
        "example_sentence": "This is a test.",
        "example_translation_zh": "這是測試。",
        "status": "active",
    }
    return app.create_vocabulary({**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Lesson generation
# ---------------------------------------------------------------------------

def test_generate_lesson_picks_active_word():
    _add_language("en", "English", "C1")
    _add_word(language="en", word="ameliorate", level="C1")
    lesson = app.generate_lesson(date.today().isoformat())
    assert len(lesson["items"]) == 1
    assert lesson["items"][0]["word"] == "ameliorate"


def test_generate_lesson_raises_when_no_active_word():
    _add_language("en", "English", "C1")
    _add_word(language="en", word="ameliorate", level="C1", status="draft")
    with pytest.raises(ValueError, match="No active vocabulary item"):
        app.generate_lesson(date.today().isoformat())


def test_generate_lesson_respects_minimum_level():
    _add_language("en", "English", "C1")
    _add_word(language="en", word="cat", level="A1")  # below minimum
    with pytest.raises(ValueError, match="No active vocabulary item"):
        app.generate_lesson(date.today().isoformat())


def test_generate_lesson_duplicate_window_excludes_recent_word():
    _add_language("en", "English")
    w1 = _add_word(language="en", word="apple", level="A1")
    w2 = _add_word(language="en", word="banana", level="A1")

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    lesson1 = app.generate_lesson(yesterday)
    used_id = lesson1["items"][0]["id"]

    today = date.today().isoformat()
    lesson2 = app.generate_lesson(today)
    today_id = lesson2["items"][0]["id"]

    assert today_id != used_id, "Should not repeat a word used yesterday"


def test_generate_lesson_due_review_bypasses_duplicate_window():
    _add_language("en", "English")
    w = _add_word(language="en", word="apple", level="A1")

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    app.generate_lesson(yesterday)

    # Mark it due for review today
    app.create_review({
        "vocabulary_item_id": w["id"],
        "rating": 5,
        "recall_success": True,
        "review_date": yesterday,
        "next_review_date": date.today().isoformat(),
    })

    today = date.today().isoformat()
    lesson = app.generate_lesson(today)
    assert lesson["items"][0]["word"] == "apple", "Due-for-review word should bypass duplicate window"


def test_generate_lesson_prefers_fewer_reviews():
    _add_language("en", "English")
    w_new = _add_word(language="en", word="newword", level="A1")
    w_reviewed = _add_word(language="en", word="oldword", level="A1")

    # Give oldword a review log so review_count = 1
    app.create_review({"vocabulary_item_id": w_reviewed["id"], "rating": 4, "recall_success": True})

    lesson = app.generate_lesson(date.today().isoformat())
    assert lesson["items"][0]["word"] == "newword", "Word with fewer reviews should be preferred"


# ---------------------------------------------------------------------------
# Spaced-repetition intervals
# ---------------------------------------------------------------------------

def test_sr_first_success_gives_stage_0_interval():
    _add_language("en", "English")
    w = _add_word(language="en", word="test", level="A1")
    review = app.create_review({
        "vocabulary_item_id": w["id"],
        "rating": 5,
        "recall_success": True,
    })
    expected = (date.today() + timedelta(days=app.REVIEW_INTERVALS[0])).isoformat()
    assert review["next_review_date"] == expected


def test_sr_failure_resets_to_stage_0():
    _add_language("en", "English")
    w = _add_word(language="en", word="test", level="A1")
    # Two successful reviews to advance stage
    for _ in range(2):
        app.create_review({"vocabulary_item_id": w["id"], "rating": 5, "recall_success": True})
    # Failure resets
    review = app.create_review({
        "vocabulary_item_id": w["id"],
        "rating": 1,
        "recall_success": False,
    })
    expected = (date.today() + timedelta(days=app.REVIEW_INTERVALS[0])).isoformat()
    assert review["next_review_date"] == expected


def test_sr_stage_advances_with_successes():
    _add_language("en", "English")
    w = _add_word(language="en", word="test", level="A1")
    last = None
    for i in range(3):
        last = app.create_review({
            "vocabulary_item_id": w["id"],
            "rating": 5,
            "recall_success": True,
        })
    # After 3 successes we're at stage min(2, 5) = 2 → 7 days
    expected = (date.today() + timedelta(days=app.REVIEW_INTERVALS[2])).isoformat()
    assert last["next_review_date"] == expected


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def test_duplicate_candidate_is_skipped():
    _add_language("en", "English")
    _add_word(language="en", word="Voraussetzung", level="B1")
    result = app.create_vocabulary_candidates({"items": [
        {
            "language": "en", "word": "Voraussetzung", "level": "B1",
            "part_of_speech": "noun", "meaning_zh": "前提", "meaning_en": "prerequisite",
            "example_sentence": "Ex.", "example_translation_zh": "例。",
        }
    ]})
    assert len(result["skipped"]) == 1
    assert len(result["created"]) == 0


def test_case_variant_not_treated_as_duplicate():
    """German: Voraussetzung (noun) and voraussetzung are distinct words."""
    _add_language("de", "German")
    _add_word(language="de", word="Voraussetzung", level="B1")
    result = app.create_vocabulary_candidates({"items": [
        {
            "language": "de", "word": "voraussetzung", "level": "B1",
            "part_of_speech": "noun", "meaning_zh": "前提", "meaning_en": "prerequisite",
            "example_sentence": "Ex.", "example_translation_zh": "例。",
        }
    ]})
    assert len(result["created"]) == 1, "Case variant should be treated as a distinct word"
