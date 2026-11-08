"""Tests for the SM-2-lite scheduler."""

from datetime import date, timedelta

import pytest

from shortcut_flashcards.scheduler import (
    AGAIN,
    EASY,
    GOOD,
    MAX_EASE,
    MIN_EASE,
    CardRecord,
    due_records,
    is_due,
    schedule,
)

TODAY = date(2026, 11, 8)


def fresh(**kwargs):
    return CardRecord(**kwargs)


class TestSchedule:
    def test_first_good_means_one_day(self):
        record = fresh()
        schedule(record, GOOD, TODAY)
        assert record.interval == 1
        assert record.due == TODAY + timedelta(days=1)
        assert record.reps == 1

    def test_second_good_means_six_days(self):
        record = fresh(reps=1, interval=1)
        schedule(record, GOOD, TODAY)
        assert record.interval == 6
        assert record.reps == 2

    def test_later_good_multiplies_interval_by_ease(self):
        record = fresh(reps=2, interval=6)
        schedule(record, GOOD, TODAY)
        assert         record.interval == 15  # 6 * 2.6 ease
        assert record.reps == 3

    def test_easy_grows_fastest(self):
        good = schedule(fresh(reps=2, interval=6), GOOD, TODAY)
        easy = schedule(fresh(reps=2, interval=6), EASY, TODAY)
        assert easy.interval > good.interval

    def test_again_resets_and_penalizes_ease(self):
        record = fresh(reps=4, interval=30, lapses=0)
        schedule(record, AGAIN, TODAY)
        assert record.interval == 0
        assert record.due == TODAY
        assert record.reps == 0  # learning restarts after a lapse
        assert record.lapses == 1
        assert record.ease == 2.35

    def test_ease_never_drops_below_min(self):
        record = fresh(ease=MIN_EASE)
        for _ in range(5):
            schedule(record, AGAIN, TODAY)
        assert record.ease == MIN_EASE

    def test_ease_never_exceeds_max(self):
        record = fresh(ease=MAX_EASE)
        for _ in range(5):
            schedule(record, GOOD, TODAY)
        assert record.ease == MAX_EASE

    def test_very_long_intervals_are_capped(self):
        record = fresh(reps=20, interval=364, ease=MAX_EASE)
        schedule(record, GOOD, TODAY)
        assert record.interval <= 365

    def test_invalid_grade_raises(self):
        with pytest.raises(ValueError, match="Invalid grade"):
            schedule(fresh(), 7)

    def test_scheduler_recovers_after_again(self):
        record = fresh()
        schedule(record, GOOD, TODAY)
        schedule(record, AGAIN, TODAY)
        schedule(record, GOOD, TODAY)
        assert record.interval == 1  # learning restarts


class TestIsDue:
    def test_new_card_is_due(self):
        assert is_due(CardRecord(), TODAY)

    def test_failed_card_is_due(self):
        assert is_due(fresh(reps=3, interval=0), TODAY)

    def test_future_card_is_not_due(self):
        assert not is_due(fresh(reps=1, interval=1, due=TODAY + timedelta(days=1)), TODAY)

    def test_today_is_due(self):
        assert is_due(fresh(reps=1, interval=1, due=TODAY), TODAY)


class TestDueRecords:
    def test_failure_then_due_then_new_ordering(self):
        records = {
            "failed": fresh(reps=3, interval=0, lapses=1),
            "future": fresh(reps=1, interval=30, due=TODAY + timedelta(days=20)),
            "matured": fresh(reps=3, interval=10, due=TODAY),
        }
        order = ["future", "failed", "new-1", "matured", "new-2"]
        assert due_records(records, order, TODAY) == [
            "failed",
            "matured",
            "new-1",
            "new-2",
        ]

    def test_limit_caps_list(self):
        order = [f"new-{i}" for i in range(20)]
        assert len(due_records({}, order, TODAY, limit=7)) == 7

    def test_no_records_means_deck_order(self):
        assert due_records(None, ["b", "a"], TODAY) == ["b", "a"]

    def test_empty_when_nothing_due(self):
        records = {"later": fresh(reps=1, interval=5, due=TODAY + timedelta(days=3))}
        assert due_records(records, ["later"], TODAY) == []

    def test_new_cards_stay_in_deck_order(self):
        assert due_records({}, ["z", "a", "m"], TODAY) == ["z", "a", "m"]
