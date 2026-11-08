"""End-to-end CLI tests (entry point `main` with injected I/O)."""

import json

import pytest

from shortcut_flashcards.cli import main


class Sink:
    def __init__(self):
        self.lines = []

    def write(self, text):
        self.lines.append(text)

    @property
    def output(self):
        return "".join(self.lines)


def run_cli(args, *, inputs=None, clock=None):
    out = Sink()
    if inputs is not None:
        replies = list(inputs)

        def input_fn():
            if not replies:
                raise EOFError
            return replies.pop(0)
    else:
        def input_fn():
            raise AssertionError("input_fn should not be called")

    code = main(args, clock=clock, input_fn=input_fn, out=out)
    return code, out.output


def csv_file(tmp_path, text="Ctrl+Q,Quit the app\nCtrl+Shift+T,Reopen closed tab\n", name="mine.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


class TestBasicCommands:
    def test_decks_lists_builtins(self):
        code, output = run_cli(["decks"])
        assert code == 0
        for slug in ("windows", "macos", "vscode", "vim", "emacs"):
            assert slug in output

    def test_show_builtin_deck(self):
        code, output = run_cli(["show", "windows"])
        assert code == 0
        assert "Ctrl+Shift+Esc" in output
        assert "Task Manager" in output
        assert output.rstrip().endswith("cards)")

    def test_show_csv_file(self, tmp_path):
        code, output = run_cli(["show", csv_file(tmp_path)])
        assert code == 0
        assert "Ctrl+Q" in output

    def test_unknown_deck_is_a_clean_error(self, tmp_path):
        code, output = run_cli(["show", str(tmp_path / "gone.csv")])
        assert code == 1
        assert output.startswith("Error: Unknown deck")

    def test_broken_csv_is_a_clean_error(self, tmp_path):
        code, output = run_cli(["show", csv_file(tmp_path, text="just-one-field\n")])
        assert code == 1
        assert "line 1" in output

    def test_bad_deck_slug(self):
        code, output = run_cli(["show", "definitely-not-a-deck"])
        assert code == 1
        assert "Unknown deck" in output

    def test_no_args_prints_help_and_exits_two(self, monkeypatch):
        code, output = run_cli([])
        assert code == 2
        assert "run" in output or "usage" in output

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0


class TestRunCommand:
    def test_run_saves_state_and_reports(self, tmp_path):
        deck = csv_file(tmp_path)
        inputs = ["y", "y", "y", "q"]  # reveal k0, grade good, reveal k1, quit

        class Clock:
            def __init__(self):
                self.t = 0.0

            def __call__(self):
                self.t += 10
                return self.t

        code, output = run_cli(
            ["--home", str(tmp_path / "state"), "run", deck, "--minutes", "2"],
            inputs=inputs,
            clock=Clock(),
        )
        assert code == 0
        assert "-> Ctrl+Q" in output
        assert "1 graded" in output
        assert "Session ended early" in output
        state = json.loads((tmp_path / "state" / "state.json").read_text())
        assert "Ctrl+Q" in next(iter(state["decks"].values()))

    def test_run_unknown_deck_fails_cleanly(self, tmp_path):
        code, output = run_cli(["--home", str(tmp_path), "run", "nope-nada"])
        assert code == 1
        assert "Unknown deck" in output

    def test_stats_after_run(self, tmp_path):
        deck = csv_file(tmp_path, name="progress.csv")
        inputs = ["y", "y", "y", "y", "q"]
        run_cli(["--home", str(tmp_path), "run", deck], inputs=inputs)
        code, output = run_cli(["--home", str(tmp_path), "stats", deck])
        assert code == 0
        assert "due now: 0" in output or "scheduled" in output

    def test_stats_before_any_run(self, tmp_path):
        code, output = run_cli(
            ["--home", str(tmp_path), "stats", csv_file(tmp_path)]
        )
        assert code == 0
        assert "never seen: 2" in output

    def test_reset_clears_state(self, tmp_path):
        deck = csv_file(tmp_path)
        run_cli(["--home", str(tmp_path), "run", deck], inputs=["y", "y", "y", "y", "q"])
        code, output = run_cli(["--home", str(tmp_path), "reset", "mine"])
        assert code == 0 and "Reset" in output
        code, output = run_cli(["--home", str(tmp_path), "stats", deck])
        assert "never seen: 2" in output

    def test_without_saved_records_reset_says_so(self, tmp_path):
        code, output = run_cli(["--home", str(tmp_path), "reset", "ghost"])
        assert code == 0 and "No saved records" in output


class TestStateLocation:
    def test_env_home_is_used(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SHORTCUT_FLASHCARDS_HOME", str(tmp_path / "env"))
        deck = csv_file(tmp_path)
        inputs = ["y", "y", "y", "y", "q"]
        code, _output = run_cli(["run", deck], inputs=inputs)
        assert code == 0
        assert (tmp_path / "env" / "state.json").is_file()

    def test_state_dir_is_created_on_save(self, tmp_path):
        deep = tmp_path / "a" / "b"
        deck = csv_file(tmp_path)
        run_cli(["--home", str(deep), "run", deck], inputs=["y", "y", "y", "y", "q"])
        assert (deep / "state.json").is_file()
