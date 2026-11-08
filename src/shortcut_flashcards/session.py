"""The drill runner: show a prompt, reveal the answer, grade, repeat.

Sessions run against a time budget (two minutes by default) and use an
injectable clock and input function, so the runner is fully testable.
"""

from __future__ import annotations

import random
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import date

from shortcut_flashcards.deck import Deck
from shortcut_flashcards.scheduler import (
    AGAIN,
    EASY,
    GOOD,
    CardRecord,
    due_records,
    schedule,
)
from shortcut_flashcards.store import Store

DEFAULT_MINUTES = 2.0
DEFAULT_NEW_LIMIT = 10

GRADES_BY_ANSWER: dict[str, int | None] = {
    "": GOOD,
    "y": GOOD,
    "n": AGAIN,
    "e": EASY,
    "q": None,  # quit
}


@dataclass
class SessionResult:
    deck_name: str
    answered: int = 0
    correct: int = 0
    again: int = 0
    easy: int = 0
    retried: int = 0
    new_seen: int = 0
    best_streak: int = 0
    ended_by: str = "time"
    seconds_used: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.correct / self.answered if self.answered else 0.0

    def summary(self) -> str:
        verdict = {
            "time": "Time is up",
            "quit": "Session ended early",
            "exhausted": "All due cards finished",
            "empty": "Nothing to study",
        }.get(self.ended_by, self.ended_by)
        if self.answered == 0:
            return f"{verdict} — no cards graded this session."
        return (
            f"{verdict} after {self.seconds_used / 60:.1f} min: "
            f"{self.answered} graded, {self.correct} correct "
            f"({self.accuracy * 100:.0f}%), best streak {self.best_streak}, "
            f"{self.new_seen} new."
        )


def deck_key(deck: Deck) -> str:
    """Stable storage key for a deck in the store."""
    return deck.name.strip().lower()


def build_queue(
    deck: Deck,
    records: dict[str, CardRecord],
    today: date,
    new_limit: int = DEFAULT_NEW_LIMIT,
    rng: random.Random | None = None,
) -> deque[str]:
    """Decide which cards to study: failed/re-due cards first, then new ones.

    Caps brand-new cards at ``new_limit`` so an untouched deck does not
    flood a two-minute session.
    """
    deck_shortcuts = [c.shortcut for c in deck.cards]
    stored = {s: records[s] for s in deck_shortcuts if s in records}
    eligible = due_records(stored, deck_shortcuts, today)
    new_cards = [s for s in eligible if records.get(s, CardRecord()).is_new]
    known_cards = [s for s in eligible if s not in set(new_cards)]
    chosen_new: list[str]
    if len(new_cards) > new_limit:
        chosen_new = rng.sample(new_cards, new_limit) if rng is not None else new_cards[:new_limit]
    else:
        chosen_new = new_cards[:new_limit]
    if rng is not None and len(chosen_new) > 1:
        rng.shuffle(chosen_new)
    return deque(known_cards + chosen_new)


def run_session(
    deck: Deck,
    store: Store,
    *,
    minutes: float = DEFAULT_MINUTES,
    clock=time.monotonic,
    input_fn=input,
    out=sys.stdout,
    today: date | None = None,
    rng: random.Random | None = None,
) -> SessionResult:
    """Run one drill session against a time budget and persist every grade."""
    today = today or date.today()
    budget = minutes * 60
    result = SessionResult(deck_name=deck.name)
    records = store.deck(deck_key(deck))

    queue = build_queue(deck, records, today, rng=rng)
    if not queue:
        result.ended_by = "empty"
        out.write("All caught up! Nothing is due for this deck today.\n")
        return result

    out.write(f"Drill: {deck.name} — recall the shortcut, then grade yourself.\n")
    out.write("Reveal with Enter, then grade: y good, n again, e easy, q quit.\n")

    start = clock()
    streak = 0
    seen_new: set[str] = set()
    retried: set[str] = set()
    cards_by_shortcut = {c.shortcut: c for c in deck.cards}

    def remaining() -> int:
        return max(0, int(budget - (clock() - start)))

    try:
        while queue:
            if clock() - start >= budget:
                result.ended_by = "time"
                break
            shortcut = queue[0]
            card = cards_by_shortcut[shortcut]
            out.write(f"\n[{remaining() // 60}:{remaining() % 60:02d} left] {card.description}\n")
            prompt_line = str(input_fn()).strip().lower()
            if prompt_line == "q":
                result.ended_by = "quit"
                break
            reveal = f"-> {card.shortcut}"
            if card.notes:
                reveal += f"  ({card.notes})"
            out.write(f"{reveal}\n")
            grade_line = str(input_fn()).strip().lower()
            while grade_line not in GRADES_BY_ANSWER:
                out.write("Grade with y (good), n (again), e (easy), or q (quit).\n")
                grade_line = str(input_fn()).strip().lower()
            grade = GRADES_BY_ANSWER[grade_line]
            if grade is None:
                result.ended_by = "quit"
                break
            record = store.record_for(deck_key(deck), shortcut)
            if record.reps == 0 and shortcut not in seen_new:
                seen_new.add(shortcut)
                result.new_seen += 1
            schedule(record, grade, today)
            store.set(deck_key(deck), shortcut, record)
            result.answered += 1
            if grade == AGAIN:
                result.again += 1
                streak = 0
                retried.add(shortcut)
                queue.append(shortcut)
            else:
                result.correct += 1
                if grade == EASY:
                    result.easy += 1
                streak += 1
                result.best_streak = max(result.best_streak, streak)
            queue.popleft()
            if not queue:
                result.ended_by = "exhausted"
                break
    except EOFError:
        result.ended_by = "quit"
    finally:
        result.seconds_used = clock() - start
        result.retried = len(retried)
    return result
