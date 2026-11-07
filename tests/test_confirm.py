# ramani: tests/test_confirm.py
from ramani.cli import main


def make(root, count=3):
    for i in range(count):
        (root / f"f{i}.py").write_text("x = 1\n")


def untouched(root, count=3):
    return all((root / f"f{i}.py").read_text() == "x = 1\n" for i in range(count))


def test_over_limit_without_terminal_aborts(tmp_path, capsys):
    make(tmp_path)
    assert main([str(tmp_path), "--max-files", "2"]) == 1
    assert "--yes" in capsys.readouterr().err
    assert untouched(tmp_path)


def test_yes_skips_the_prompt(tmp_path):
    make(tmp_path)
    assert main([str(tmp_path), "--max-files", "2", "-y"]) == 0
    assert not untouched(tmp_path)


def test_at_the_limit_does_not_prompt(tmp_path):
    make(tmp_path)
    assert main([str(tmp_path), "--max-files", "3"]) == 0


def test_dry_run_and_check_never_prompt(tmp_path):
    make(tmp_path)
    assert main([str(tmp_path), "--max-files", "1", "--dry-run"]) == 0
    assert main([str(tmp_path), "--max-files", "1", "--check"]) == 1  # needs changes
    assert untouched(tmp_path)


def test_interactive_answers(tmp_path, monkeypatch):
    make(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert main([str(tmp_path), "--max-files", "2"]) == 1
    assert untouched(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    assert main([str(tmp_path), "--max-files", "2"]) == 0
    assert not untouched(tmp_path)


def test_single_file_never_prompts(tmp_path):
    make(tmp_path, 1)
    assert main([str(tmp_path / "f0.py"), "--max-files", "0"]) == 0
