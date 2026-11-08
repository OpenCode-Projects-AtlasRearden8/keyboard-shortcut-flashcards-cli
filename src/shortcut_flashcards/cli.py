"""Command-line interface for Shortcut Flashcards.

Commands:
    decks                     list available decks (builtins + your CSVs)
    show <deck|file>          print every card in a deck
    run  <deck|file>          run a drill session (default: two minutes)
    stats [deck]              show due/new counts and progress
    reset <deck>              clear schedule state for a deck

State lives under ~/.local/share/shortcut-flashcards (override with
SHORTCUT_FLASHCARDS_HOME or --home). Everything is offline and local.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from shortcut_flashcards import __version__
from shortcut_flashcards.deck import Deck, DeckError, available_decks, load_deck
from shortcut_flashcards.scheduler import due_records, is_due
from shortcut_flashcards.session import DEFAULT_MINUTES, SessionResult, deck_key, run_session
from shortcut_flashcards.store import Store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shortcut-flashcards",
        description="Daily keyboard-shortcut memory drills in your terminal.",
        epilog="Example: shortcut-flashcards run windows",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--home",
        metavar="DIR",
        help="directory for state.json (default: ~/.local/share/shortcut-flashcards; "
        "env SHORTCUT_FLASHCARDS_HOME also works)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("decks", help="list available decks")

    show = sub.add_parser("show", help="print every card in a deck")
    show.add_argument("deck")

    run = sub.add_parser("run", help="run a drill session")
    run.add_argument("deck")
    run.add_argument(
        "--minutes",
        type=float,
        default=DEFAULT_MINUTES,
        help=f"session time budget in minutes (default {DEFAULT_MINUTES:g})",
    )
    run.add_argument("--shuffle", action="store_true", help="shuffle the new-card order")

    stats = sub.add_parser("stats", help="progress summary")
    stats.add_argument("deck", nargs="?", default=None)

    reset = sub.add_parser("reset", help="forget schedule state for a deck")
    reset.add_argument("deck")
    return parser


def _print_deck(out, deck: Deck) -> None:
    header = "=" * len(deck.name)
    out.write(f"{deck.name}\n{header}\n")
    for card in deck.cards:
        out.write(f"{card.shortcut:<18} {card.description}\n")
        if card.notes:
            out.write(f"{'':<18} note: {card.notes}\n")
    out.write(f"({len(deck.cards)} cards)\n")


def _deck_stats(store: Store, deck: Deck) -> str:
    today = date.today()
    records = store.deck(deck_key(deck))
    stored_subset = {s: records[s] for s in (c.shortcut for c in deck.cards) if s in records}
    due = due_records(stored_subset, [c.shortcut for c in deck.cards], today)
    shortcuts = {c.shortcut for c in deck.cards}
    scheduled = sum(
        1
        for shortcut in shortcuts
        if shortcut in stored_subset
        and stored_subset[shortcut].reps > 0
        and not is_due(stored_subset[shortcut], today)
    )
    fresh = sum(1 for shortcut in shortcuts if shortcut not in stored_subset)
    return (
        f"{deck.name}: {len(shortcuts)} cards | due now: {len(due)} | "
        f"scheduled (not due): {scheduled} | never seen: {fresh}"
    )


def cmd_decks(store: Store, out) -> int:
    out.write("Builtin decks:\n")
    for slug in available_decks():
        out.write(f"  {slug:<16} run with: shortcut-flashcards run {slug}\n")
    out.write("\nYour CSV decks: point at any file with lines 'shortcut,description' —\n")
    out.write("for example: shortcut-flashcards run examples/example-deck.csv\n")
    return 0


def cmd_show(out, deck_arg: str) -> int:
    _print_deck(out, load_deck(deck_arg))
    return 0


def cmd_run(store: Store, deck_arg: str, minutes: float, shuffle: bool, out, clock, input_fn) -> int:
    import random

    deck = load_deck(deck_arg)
    rng = random.Random() if shuffle else None
    result: SessionResult = run_session(
        deck,
        store,
        minutes=minutes,
        out=out,
        clock=clock,
        input_fn=input_fn,
        rng=rng,
    )
    out.write(result.summary() + "\n")
    store.save()
    return 0


def cmd_stats(out, deck_arg: str | None, store: Store) -> int:
    if deck_arg is None:
        if not store.decks:
            out.write("No progress yet — run a session first, e.g. `run windows`.\n")
            return 0
        for deck_name in sorted(store.decks):
            try:
                deck = load_deck(deck_name)
            except DeckError:
                out.write(f"{deck_name}: schedule state saved (deck file no longer loadable)\n")
                continue
            out.write(_deck_stats(store, deck) + "\n")
        return 0
    deck = load_deck(deck_arg)
    out.write(_deck_stats(store, deck) + "\n")
    return 0


def cmd_reset(store: Store, deck_arg: str, out) -> int:
    key = deck_arg.strip().lower()
    removed = store.reset_deck(key)
    if removed:
        out.write(f"Reset {removed} card record(s) for '{key}'.\n")
    else:
        out.write(f"No saved records for '{key}'.\n")
    return 0


def main(argv=None, *, clock=None, input_fn=None, out=None) -> int:
    """Entry point. clock/input_fn/out are injectable for tests."""
    import time

    clock = clock if clock is not None else time.monotonic
    input_fn = input_fn if input_fn is not None else input
    out = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(out)
        return 2

    store = Store(state_dir=args.home)
    try:
        if args.command == "decks":
            return cmd_decks(store, out)
        if args.command == "show":
            return cmd_show(out, args.deck)
        if args.command == "run":
            return cmd_run(store, args.deck, args.minutes, args.shuffle, out, clock, input_fn)
        if args.command == "stats":
            return cmd_stats(out, args.deck, store)
        if args.command == "reset":
            return cmd_reset(store, args.deck, out)
    except DeckError as exc:
        out.write(f"Error: {exc}\n")
        return 1
    parser.error(f"Unknown command {args.command!r}")  # pragma: no cover
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
