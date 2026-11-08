"""A small SM-2-style spaced-repetition scheduler.

Per-card memory records hold a due date, an ease factor, and repetition
counts. Grading uses three responses:

  0 ("again") -> card failed; reset the interval, drop the ease factor
  1 ("good")  -> grew interval: 1 day, then 6 days, then interval * ease
  2 ("easy")  -> grew interval faster than "good"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

AGAIN = 0
GOOD = 1
EASY = 2

MIN_EASE = 1.3
MAX_EASE = 2.8
EASE_PENALTY = 0.15
EASE_REWARD = 0.1
NEW_INTERVAL = 1
LEARNING_INTERVAL = 6
EASY_BONUS = 1.3
MAX_INTERVAL_DAYS = 365

GRADE_NAMES = {AGAIN: "again", GOOD: "good", EASY: "easy"}


@dataclass
class CardRecord:
    """Schedule state for one card."""

    due: date = field(default_factory=date.today)
    interval: int = 0
    ease: float = 2.5
    reps: int = 0
    lapses: int = 0
    last_grade: int | None = None

    @property
    def is_new(self) -> bool:
        return self.reps == 0 and self.interval == 0

    @property
    def is_due_now(self) -> bool:
        return self.interval == 0


def _clamp_ease(ease: float) -> float:
    return min(MAX_EASE, max(MIN_EASE, round(ease, 3)))


def schedule(record: CardRecord, grade: int, today: date | None = None) -> CardRecord:
    """Update a record for a graded review. Mutates and returns the record."""
    if grade not in GRADE_NAMES:
        raise ValueError(f"Invalid grade {grade!r}; expected 0 (again), 1 (good), or 2 (easy)")
    today = today or date.today()
    record.last_grade = grade
    if grade == AGAIN:
        record.interval = 0
        record.ease = _clamp_ease(record.ease - EASE_PENALTY)
        record.lapses += 1
        record.reps = 0  # learning restarts after a lapse
        record.due = today  # resurface immediately (same drill) or today
        return record
    record.reps += 1
    if grade == GOOD:
        record.ease = _clamp_ease(record.ease + EASE_REWARD)
    if record.reps == 1:
        record.interval = NEW_INTERVAL
    elif record.reps == 2:
        record.interval = LEARNING_INTERVAL
    else:
        bonus = EASY_BONUS if grade == EASY else 1.0
        record.interval = int(
            max(record.interval * record.ease * bonus, record.interval + 1)
        )
    record.interval = min(record.interval, MAX_INTERVAL_DAYS)
    record.due = today + timedelta(days=record.interval)
    return record


def is_due(record: CardRecord, today: date) -> bool:
    """A card is schedulable if it is new, failed, or its due date is today/past."""
    return record.is_new or record.is_due_now or record.due <= today


def _bucket(record: CardRecord, today: date) -> int:
    if record.is_new:
        return 2
    if record.is_due_now:
        return 0
    if record.due <= today:
        return 1
    return 3


def due_records(
    cards: dict[str, CardRecord] | None,
    shortcuts: list[str],
    today: date,
    limit: int | None = None,
) -> list[str]:
    """Return shortcuts for cards that should be studied, due first, then new.

    Failed cards (interval == 0) come first so they reappear in the drill,
    then cards whose due date has arrived, then brand-new cards in deck order.
    Not-yet-due cards are excluded.
    """
    cards = cards or {}
    eligible: list[tuple[int, int, str]] = []
    for position, shortcut in enumerate(shortcuts):
        record = cards.get(shortcut, CardRecord())
        bucket = _bucket(record, today)
        if bucket == 3:
            continue
        eligible.append((bucket, record.reps if record.reps else position, shortcut))
    eligible.sort(key=lambda t: (t[0], t[1]))
    ordered = [shortcut for _, _, shortcut in eligible]
    if limit is not None:
        ordered = ordered[:limit]
    return ordered
