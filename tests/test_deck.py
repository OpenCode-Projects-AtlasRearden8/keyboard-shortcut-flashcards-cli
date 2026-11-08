"""Tests for the deck loader and CSV parser (the core, most-exercised code)."""

import pytest

from shortcut_flashcards.deck import (
    Card,
    Deck,
    DeckError,
    available_decks,
    builtin_deck_text,
    is_builtin,
    load_builtin,
    load_deck,
    parse_csv_file,
    parse_csv_text,
)


def card_shortcuts(deck):
    return [card.shortcut for card in deck.cards]


class TestParseCsvText:
    def test_parses_simple_rows(self):
        deck = parse_csv_text("Ctrl+C,Copy\nCtrl+V,Paste\n")
        assert [c.shortcut for c in deck.cards] == ["Ctrl+C", "Ctrl+V"]
        assert deck.cards[0].description == "Copy"

    def test_optional_notes_column(self):
        deck = parse_csv_text("Win+S,Search,press Win not Ctrl\n")
        assert deck.cards[0].notes == "press Win not Ctrl"

    def test_quoted_description_with_comma(self):
        deck = parse_csv_text('Win+V,"Clipboard history, after enabling"\n')
        assert deck.cards[0].description == "Clipboard history, after enabling"

    def test_comments_and_blank_lines_are_skipped(self):
        deck = parse_csv_text("# header comment\n\nCtrl+C,Copy\n\n   \n# tail\n")
        assert card_shortcuts(deck) == ["Ctrl+C"]

    def test_header_row_is_ignored(self):
        deck = parse_csv_text("shortcut,description,notes\nCtrl+C,Copy,n(none)-\n")
        assert card_shortcuts(deck) == ["Ctrl+C"]

    def test_strips_surrounding_whitespace(self):
        deck = parse_csv_text("  Ctrl+C ,  Copy  \n")
        assert (deck.cards[0].shortcut, deck.cards[0].description) == ("Ctrl+C", "Copy")

    def test_utf8_bom_is_stripped(self):
        deck = parse_csv_text("﻿Ctrl+C,Copy\n")
        assert card_shortcuts(deck) == ["Ctrl+C"]

    def test_single_column_row_raises_with_line_number(self):
        with pytest.raises(DeckError) as excinfo:
            parse_csv_text("Ctrl+C,Copy\nlonely\n")
        assert "line 2" in str(excinfo.value)

    def test_empty_shortcut_raises(self):
        with pytest.raises(DeckError, match="shortcut cannot be empty"):
            parse_csv_text(",Copy\n")

    def test_empty_description_raises(self):
        with pytest.raises(DeckError, match="description cannot be empty"):
            parse_csv_text("Ctrl+C,\n")

    def test_duplicate_shortcut_raises(self):
        with pytest.raises(DeckError, match="duplicate shortcut"):
            parse_csv_text("Ctrl+C,Copy\nCtrl+C,Paste\n")

    def test_empty_deck_raises(self):
        with pytest.raises(DeckError, match="no cards found"):
            parse_csv_text("# only comments\n\n")

    def test_deck_name_flows_into_error_messages(self):
        with pytest.raises(DeckError, match="mydeck.csv"):
            parse_csv_text("broken\n", deck_name="mydeck.csv")


class TestBuiltins:
    def test_available_decks_lists_all_five(self):
        assert available_decks() == ["emacs", "macos", "vim", "vscode", "windows"]

    @pytest.mark.parametrize("slug", available_decks())
    def test_every_builtin_loads(self, slug):
        deck = load_deck(slug)
        assert len(deck.cards) >= 20
        assert len({c.shortcut for c in deck.cards}) == len(deck.cards)
        assert all(c.description for c in deck.cards)

    def test_every_builtin_csv_is_valid(self):
        for slug in available_decks():
            parse_csv_text(builtin_deck_text(slug), deck_name=slug)

    def test_slug_loader_rejects_unknown(self):
        with pytest.raises(DeckError, match="Unknown builtin deck"):
            load_builtin("nonsense")

    def test_friendly_name_works_too(self):
        assert card_shortcuts(load_deck("Windows keyboard shortcuts")) == card_shortcuts(
            load_builtin("windows")
        )

    def test_is_builtin_matches_slug_and_friendly(self):
        assert is_builtin("VSCODE") and is_builtin("Vim keyboard shortcuts")
        assert not is_builtin("bogus")


class TestLoadDeck:
    def test_loads_csv_from_path(self, tmp_path):
        path = tmp_path / "mydeck.csv"
        path.write_text("Ctrl+Q,Deck: quit\n")
        deck = parse_csv_file(path)
        assert deck.name == "mydeck"
        assert deck.cards[0].shortcut == "Ctrl+Q"

    def test_load_deck_prefers_path_over_builtin_name(self, tmp_path):
        path = tmp_path / "vim.csv"
        path.write_text("custom,entry\n")
        deck = load_deck(str(path))
        assert card_shortcuts(deck) == ["custom"]

    def test_load_deck_missing_both_raises_and_suggests(self, tmp_path):
        with pytest.raises(DeckError, match="windows"):
            load_deck(str(tmp_path / "missing.csv"))

    def test_frozen_cards_share_value_semantics(self):
        assert Card("Ctrl+C", "Copy") == Card("Ctrl+C", "Copy")


class TestDeckModel:
    def test_shortcuts_set(self):
        deck = Deck(name="d", description="d", cards=[Card("a", "1"), Card("b", "2"), Card("a", "3")])
        assert deck.shortcuts() == {"a", "b"}
