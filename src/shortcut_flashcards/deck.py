"""Deck and card data model, CSV parsing, and builtin/CSV loading."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

BUILTIN_DECKS: dict[str, str] = {
    "windows": "Windows keyboard shortcuts",
    "macos": "macOS keyboard shortcuts",
    "vscode": "Visual Studio Code keyboard shortcuts",
    "vim": "Vim keyboard shortcuts",
    "emacs": "GNU Emacs keyboard shortcuts",
}

HEADER_WORDS = {"shortcut", "description"}


class DeckError(ValueError):
    """Raised when a deck cannot be found or parsed."""


@dataclass(frozen=True)
class Card:
    shortcut: str
    description: str
    notes: str = ""


@dataclass
class Deck:
    name: str
    description: str
    cards: list[Card] = field(default_factory=list)

    def shortcuts(self) -> set[str]:
        return {card.shortcut for card in self.cards}


def parse_csv_text(text: str, deck_name: str = "deck") -> Deck:
    """Parse CSV text into a Deck.

    Accepted format (one card per line):
        shortcut,description[,notes]
    Lines starting with '#' are comments, blank lines are skipped, and a
    header row of shortcut/description is allowed and ignored.
    """
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff"), newline=""))
    cards: list[Card] = []
    seen: set[str] = set()
    for line_num, row in enumerate(reader, start=1):
        fields = [f.strip() for f in row]
        if not fields or all(not f for f in fields):
            continue
        if fields[0].startswith("#"):
            continue
        if len(fields) >= 2 and fields[0].lower() in HEADER_WORDS:
            continue
        if len(fields) < 2:
            raise DeckError(
                f"{deck_name}: line {line_num}: expected 'shortcut,description', "
                f"got: {' | '.join(fields) or '<empty>'}"
            )
        shortcut, description = fields[0], fields[1]
        if not shortcut:
            raise DeckError(f"{deck_name}: line {line_num}: shortcut cannot be empty")
        if not description:
            raise DeckError(f"{deck_name}: line {line_num}: description cannot be empty")
        if shortcut in seen:
            raise DeckError(f"{deck_name}: line {line_num}: duplicate shortcut '{shortcut}'")
        seen.add(shortcut)
        notes = "|".join(fields[2:])
        cards.append(Card(shortcut=shortcut, description=description, notes=notes))
    if not cards:
        raise DeckError(f"{deck_name}: no cards found in deck")
    return Deck(name=deck_name, description=deck_name, cards=cards)


def parse_csv_file(path: Path) -> Deck:
    """Read a CSV file from disk and parse it as a deck."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise DeckError(f"{path}: cannot read deck file ({exc.strerror or exc})") from exc
    return parse_csv_text(text, deck_name=path.stem or path.name)


def builtin_deck_text(key: str) -> str:
    return (
        resources.files("shortcut_flashcards") / "builtin_decks" / f"{key}.csv"
    ).read_text(encoding="utf-8")


def available_decks() -> list[str]:
    """Sorted list of deck names: builtin slugs plus README-style names."""
    return sorted(BUILTIN_DECKS)


def load_deck(name_or_path: str) -> Deck:
    """Load a deck by builtin slug, friendly name, or CSV file path."""
    key = name_or_path.strip().lower()
    if key in BUILTIN_DECKS:
        slug = key
    else:
        slug = next((s for s, f in BUILTIN_DECKS.items() if key == f.lower()), None)
    if slug is not None:
        friendly = BUILTIN_DECKS[slug]
        return parse_csv_text(builtin_deck_text(slug), deck_name=friendly)
    path = Path(name_or_path).expanduser()
    if path.is_file():
        return parse_csv_file(path)
    available = ", ".join(available_decks())
    raise DeckError(
        f"Unknown deck '{name_or_path}'. Use a builtin deck ({available}) "
        f"or the path to a CSV file."
    )


def load_builtin(key: str) -> Deck:
    """Load a single builtin deck by slug (raises DeckError for bad keys)."""
    if key not in BUILTIN_DECKS:
        raise DeckError(f"Unknown builtin deck '{key}'")
    return load_deck(key)


def is_builtin(name: str) -> bool:
    key = name.strip().lower()
    return key in BUILTIN_DECKS or key in {f.lower() for f in BUILTIN_DECKS.values()}
