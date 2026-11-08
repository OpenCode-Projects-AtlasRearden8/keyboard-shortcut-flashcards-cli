"""Tests for the two-minute drill runner with injected clock and input."""

import random
from datetime import date, timedelta
from pathlib import Path
from tempfile import mkdtemp

from shortcut_flashcards.deck import Card, Deck
from shortcut_flashcards.scheduler import CardRecord
from shortcut_flashcards.session import DEFAULT_MINUTES, build_queue, deck_key, run_session
from shortcut_flashcards.store import Store

TODAY = date(2026, 11, 8)


def make_deck(n, name="test deck"):
    return Deck(
        name=name,
        description=name,
        cards=[Card(f"k{i}", f"Action {i}") for i in range(n)],
    )


def temp_store():
    return Store(state_dir=Path(mkdtemp()))


class FakeClock:
    def __init__(self, step=5.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


class Sink:
    def write(self, text):
        pass


def scripted_inputs(*responses):
    answers = list(responses)

    def read():
        if not answers:
            raise EOFError
        return answers.pop(0)

    return read


def drill_inputs(drill_rounds):
    """reveal,grade pairs for N card visits (grade 'y' = good)."""
    inputs = []
    for _ in range(drill_rounds):
        inputs.append("y")
        inputs.append("y")
    return scripted_inputs(*inputs)


def run(deck, store, inputs, minutes=DEFAULT_MINUTES, clock=None, rng=None):
    return run_session(
        deck,
        store,
        minutes=minutes,
        clock=clock or FakeClock(),
        input_fn=inputs,
        out=Sink(),
        today=TODAY,
        rng=rng,
    )


class TestRunSession:
    def test_full_deck_graded_and_state_saved(self):
        deck, store = make_deck(3), temp_store()
        result = run(deck, store, drill_inputs(5))
        assert result.answered == 3
        assert result.correct == 3
        assert result.ended_by == "exhausted"
        for i in range(3):
            record = store.record_for(deck_key(deck), f"k{i}")
            assert record.reps == 1
            assert record.interval == 1

    def test_new_cards_limit_caps_brand_new_deck(self):
        deck, store = make_deck(25), temp_store()
        result = run(deck, store, drill_inputs(15), clock=FakeClock(step=0.1))
        assert result.new_seen == 10  # DEFAULT_NEW_LIMIT
        assert result.answered == 10

    def test_wrong_card_is_requeued_and_resurfaced(self):
        deck, store = make_deck(1), temp_store()
        inputs = scripted_inputs("y", "n", "y", "y", "q")
        result = run(deck, store, inputs)
        assert result.answered == 2
        assert result.again == 1
        assert result.correct == 1
        # The 'again' card was appended back and resurfaced before quitting.
        assert result.retried == 1
        record = store.record_for(deck_key(deck), "k0")
        assert record.lapses == 1

    def test_again_resets_then_easy_card_relearns(self):
        deck, store = make_deck(2), temp_store()
        inputs = scripted_inputs("y", "y", "y", "n", "y", "e", "y", "q")
        result = run(deck, store, inputs)
        assert result.answered == 3
        assert result.again == 1
        assert result.easy == 1
        assert result.correct == 2
        assert store.record_for(deck_key(deck), "k0").interval == 1
        after_again = store.record_for(deck_key(deck), "k1")
        assert after_again.lapses == 1
        assert after_again.interval == 1

    def test_quit_ends_session_early(self):
        deck, store = make_deck(3), temp_store()
        result = run(deck, store, scripted_inputs("y", "y", "y", "y", "q"))
        assert result.ended_by == "quit"
        assert result.answered == 2

    def test_eof_ends_session_gracefully(self):
        deck, store = make_deck(3), temp_store()
        result = run(deck, store, scripted_inputs("y", "y", "y", "y"))
        assert result.ended_by == "quit"
        assert result.answered == 2

    def test_time_budget_terminates(self):
        deck, store = make_deck(30), temp_store()
        result = run(deck, store, drill_inputs(40), clock=FakeClock(step=30.0))
        assert result.ended_by == "time"
        assert result.answered < 30

    def test_empty_queue_reports_all_caught_up(self):
        deck, store = make_deck(5), temp_store()
        far = TODAY + timedelta(days=30)
        for i in range(5):
            store.set(deck_key(deck), f"k{i}", CardRecord(reps=3, interval=30, due=far))
        result = run(deck, store, scripted_inputs("q"))
        assert result.ended_by == "empty"
        assert result.answered == 0

    def test_summary_text_counts_accuracy(self):
        deck, store = make_deck(2), temp_store()
        result = run(deck, store, scripted_inputs("y", "y", "y", "n", "y", "y"))
        text = result.summary()
        assert "2 correct (67%" in text
        assert "streak 1" in text
        assert "min" in text

    def test_prompt_shows_time_remaining(self):
        deck, store = make_deck(1), temp_store()
        seen = []

        class HUD:
            def write(self, text):
                seen.append(text)

        run_session(
            deck,
            store,
            clock=FakeClock(),
            input_fn=scripted_inputs("y", "y", "q"),
            out=HUD(),
            today=TODAY,
        )
        joined = "".join(seen)
        assert "left]" in joined
        assert "Action 0" in joined
        assert "-> k0" in joined


class TestBuildQueue:
    def test_failed_first_then_new(self):
        deck, store = make_deck(3), temp_store()
        store.set(deck_key(deck), "k1", CardRecord(reps=3, interval=0, due=TODAY))
        queue = list(build_queue(deck, store.deck(deck_key(deck)), TODAY))
        assert queue[0] == "k1"
        assert set(queue) == {"k0", "k1", "k2"}

    def test_future_cards_excluded(self):
        deck, store = make_deck(2), temp_store()
        store.set(deck_key(deck), "k0", CardRecord(reps=2, interval=30, due=TODAY + timedelta(days=30)))
        assert list(build_queue(deck, store.deck(deck_key(deck)), TODAY)) == ["k1"]

    def test_shuffle_flag_randomizes_new_cards(self):
        deck = make_deck(12)
        plain = list(build_queue(deck, {}, TODAY, new_limit=12))
        shuffled = list(
            build_queue(deck, {}, TODAY, new_limit=12, rng=random.Random(7))
        )
        assert sorted(shuffled) == sorted(plain)
        assert shuffled != plain


def test_default_minutes_is_two():
    assert DEFAULT_MINUTES == 2.0


def test_deck_key_is_lowercased_name():
    assert deck_key(Deck(name="  My Deck ", description="x")) == "my deck"
