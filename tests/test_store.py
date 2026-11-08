"""Tests for JSON-persisted schedule state."""

import json
from datetime import date
from pathlib import Path

import pytest

from shortcut_flashcards import store as store_module
from shortcut_flashcards.scheduler import AGAIN, GOOD, CardRecord, schedule
from shortcut_flashcards.store import Store, default_state_dir, load_store


def test_roundtrip(tmp_path):
    store = Store(state_dir=tmp_path)
    record = CardRecord()
    schedule(record, GOOD, date(2026, 11, 8))
    store.set("vim", "gg", record)
    again = Store(state_dir=tmp_path)
    loaded = again.record_for("vim", "gg")
    assert loaded.due == record.due
    assert loaded.reps == record.reps == 1
    assert loaded.ease == pytest.approx(record.ease)
    assert loaded.last_grade == GOOD


def test_deck_key_is_case_insensitive(tmp_path):
    store = Store(state_dir=tmp_path)
    store.set("Vim", "gg", CardRecord())
    assert "gg" in store.deck("vim")
    assert "gg" in store.deck(" VIM ")


def test_record_for_defaults_to_new_record(tmp_path):
    store = Store(state_dir=tmp_path)
    record = store.record_for("missing", "nope")
    assert record.is_new and record.reps == 0


def test_reset_deck_removes_records(tmp_path):
    store = Store(state_dir=tmp_path)
    store.set("vim", "gg", CardRecord())
    assert store.reset_deck("vim") == 1
    assert store.decks == {}
    assert store.reset_deck("vim") == 0


def test_reset_persists_only_that_deck(tmp_path):
    store = Store(state_dir=tmp_path)
    store.set("vim", "dd", CardRecord())
    future = date(2026, 12, 1)
    store.set("windows", "Win+L", CardRecord(reps=3, interval=20, due=future))
    store.reset_deck("vim")
    reloaded = Store(state_dir=tmp_path)
    assert reloaded.record_for("vim", "dd").is_new
    assert reloaded.record_for("windows", "Win+L").reps == 3


def test_corrupt_state_file_starts_fresh(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{not json")
    store = Store(state_dir=tmp_path)
    assert store.decks == {}


def test_unexpected_shapes_do_not_crash(tmp_path):
    (tmp_path / "state.json").write_text(
        json.dumps({"version": 1, "decks": {"vim": {"dd": {"due": "bad-date!"}, "xx": []}}})
    )
    store = Store(state_dir=tmp_path)
    assert store.decks.get("vim", {}) == {}


def test_missing_state_file_is_empty(tmp_path):
    assert Store(state_dir=tmp_path / "fresh").decks == {}
    assert Store(state_dir=tmp_path / "fresh").state_file.name == "state.json"


def test_default_state_dir_honors_env(monkeypatch):
    monkeypatch.delenv(store_module.ENV_HOME, raising=False)
    home = default_state_dir()
    assert home.name == "shortcut-flashcards"
    monkeypatch.setenv(store_module.ENV_HOME, "/tmp/custom-ksfc")
    assert default_state_dir() == Path("/tmp/custom-ksfc")


def test_env_var_flows_through_store_construction(tmp_path, monkeypatch):
    monkeypatch.setenv(store_module.ENV_HOME, str(tmp_path / "envhome"))
    store = load_store()
    store.set("emacs", "Ctrl+g", CardRecord())
    assert (tmp_path / "envhome" / "state.json").exists()


def test_again_grade_survives_roundtrip(tmp_path):
    store = Store(state_dir=tmp_path)
    record = CardRecord()
    schedule(record, AGAIN, date(2026, 11, 8))
    store.set("d", "s", record)
    loaded = Store(state_dir=tmp_path).record_for("d", "s")
    assert loaded.interval == 0
    assert loaded.due == date(2026, 11, 8)
    assert loaded.lapses == 1
