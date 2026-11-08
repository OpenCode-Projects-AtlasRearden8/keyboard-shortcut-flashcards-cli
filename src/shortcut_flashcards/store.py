"""JSON persistence for per-card spaced-repetition records."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date
from pathlib import Path

from shortcut_flashcards.scheduler import CardRecord

ENV_HOME = "SHORTCUT_FLASHCARDS_HOME"
STATE_FILENAME = "state.json"
STATE_VERSION = 1


def default_state_dir() -> Path:
    """Resolve the state directory: env var, else a platform default."""
    env = os.environ.get(ENV_HOME)
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share" / "shortcut-flashcards"


def _encode_date(value: date) -> str:
    return value.isoformat()


def _decode_date(value: str) -> date:
    return date.fromisoformat(value)


class Store:
    """Persistent store of CardRecords grouped by deck, keyed by shortcut."""

    def __init__(self, state_dir: Path | str | None = None):
        if state_dir is None:
            state_dir = default_state_dir()
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / STATE_FILENAME
        self.decks: dict[str, dict[str, CardRecord]] = {}
        self._load()

    def deck(self, deck_name: str) -> dict[str, CardRecord]:
        """Get (or create) the record mapping for a deck.

        Deck names are lowercased so `Vim.csv`, `vim`, and `VIM` share state.
        """
        return self.decks.setdefault(deck_name.strip().lower(), {})

    def record_for(self, deck_name: str, shortcut: str) -> CardRecord:
        return self.deck(deck_name).get(shortcut, CardRecord())

    def set(self, deck_name: str, shortcut: str, record: CardRecord) -> None:
        self.deck(deck_name)[shortcut] = record
        self.save()

    def save(self) -> None:
        encoded: dict[str, object] = {"version": STATE_VERSION, "decks": {}}
        for deck, records in self.decks.items():
            encoded["decks"][deck] = {}
            for shortcut, record in records.items():
                data = asdict(record)
                data["due"] = _encode_date(data["due"])
                encoded["decks"][deck][shortcut] = data
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(encoded, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def reset_deck(self, deck_name: str) -> int:
        """Discard schedule state for a deck. Returns the number of cards reset."""
        key = deck_name.strip().lower()
        removed = self.decks.pop(key, {})
        if removed:
            self.save()
        return len(removed)

    def _load(self) -> None:
        try:
            missing = object()
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Corrupt or unreadable state: start fresh rather than crash.
            self.decks = {}
            return
        decks = raw.get("decks", missing) if isinstance(raw, dict) else missing
        if decks is missing or not isinstance(decks, dict):
            self.decks = {}
            return
        loaded: dict[str, dict[str, CardRecord]] = {}
        for deck_name, records in decks.items():
            if not isinstance(records, dict):
                continue
            deck_map: dict[str, CardRecord] = {}
            for shortcut, data in records.items():
                if not isinstance(data, dict):
                    continue
                try:
                    record = CardRecord(
                        due=_decode_date(data.get("due", date.today().isoformat())),
                        interval=int(data.get("interval", 0)),
                        ease=float(data.get("ease", 2.5)),
                        reps=int(data.get("reps", 0)),
                        lapses=int(data.get("lapses", 0)),
                        last_grade=data.get("last_grade"),
                    )
                except (TypeError, ValueError):
                    continue
                deck_map[shortcut] = record
            loaded[deck_name] = deck_map
        self.decks = loaded


def load_store(state_dir: Path | str | None = None) -> Store:
    return Store(state_dir=state_dir)
