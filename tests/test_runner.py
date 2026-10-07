import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

import run_models  # noqa: E402

LEVELS = ["level1_clean", "level2_mixed", "level4_hard"]


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    for level in LEVELS:
        (root / level).mkdir(parents=True)
        for n in range(1, 6):
            (root / level / f"{level}_{n:03d}.json").write_text("{}")
    return root


def ids(paths):
    return [p.stem for p in paths]


def test_default_is_all_levels_sorted(data):
    got = ids(run_models.select_invoices(data, None, 2))
    assert got == ["level1_clean_001", "level1_clean_002", "level2_mixed_001",
                   "level2_mixed_002", "level4_hard_001", "level4_hard_002"]


def test_levels_run_only_those_in_the_given_order(data):
    got = ids(run_models.select_invoices(data, ["level4_hard", "level1_clean"], 2))
    assert got == ["level4_hard_001", "level4_hard_002", "level1_clean_001", "level1_clean_002"]


def test_per_level_limit_and_repeated_level(data):
    got = ids(run_models.select_invoices(data, ["level2_mixed", "level2_mixed"], 3))
    assert got == ["level2_mixed_001", "level2_mixed_002", "level2_mixed_003"]


def test_unknown_level_error_lists_valid_names(data):
    with pytest.raises(ValueError) as e:
        run_models.select_invoices(data, ["level4_hard", "level9"], 5)
    msg = str(e.value)
    assert "level9" in msg and all(lv in msg for lv in LEVELS)


def test_cli_rejects_unknown_level_with_clear_message(data, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_models.py", "--model", "m", "--data", str(data),
                                      "--levels", "nope", "--dry-run"])
    with pytest.raises(SystemExit) as e:
        run_models.main()
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "unknown level(s) nope" in err and "level4_hard" in err


def test_dry_run_reports_run_retry_skip_and_makes_no_calls(data, tmp_path, capsys, monkeypatch):
    out = tmp_path / "raw"
    model_dir = out / "m"
    model_dir.mkdir(parents=True)
    (model_dir / "level4_hard_001.json").write_text(json.dumps({"error": None}))
    (model_dir / "level4_hard_002.json").write_text(json.dumps({"error": "503 UNAVAILABLE"}))

    def boom(*a, **k):
        raise AssertionError("dry run must not call the API")

    monkeypatch.setattr(run_models, "extract", boom)
    monkeypatch.setattr(sys, "argv", ["run_models.py", "--model", "m", "--data", str(data), "--out", str(out),
                                      "--levels", "level4_hard", "--per-level", "3", "--dry-run"])
    run_models.main()
    text = capsys.readouterr().out
    assert "level4_hard_001  SKIP" in text
    assert "level4_hard_002  WOULD RETRY" in text
    assert "level4_hard_003  WOULD RUN" in text
    assert "level1_clean" not in text
    assert "1 to run, 1 to retry, 1 skipped" in text
    assert sorted(p.name for p in model_dir.iterdir()) == ["level4_hard_001.json", "level4_hard_002.json"]


def test_stops_after_three_consecutive_failures_and_retries_on_rerun(data, tmp_path, monkeypatch):
    for level in LEVELS:  # real runs need an image next to each key
        for p in (data / level).glob("*.json"):
            p.with_suffix(".png").write_bytes(b"x")
    calls = []

    def failing(model, image):
        calls.append(image.stem)
        return {"response_text": None, "seconds": None, "input_tokens": 0, "output_tokens": 0,
                "thinking_tokens": 0, "error": "503 UNAVAILABLE"}

    monkeypatch.setattr(run_models, "extract", failing)
    monkeypatch.setattr(run_models.time, "sleep", lambda s: None)
    out = tmp_path / "raw"
    argv = ["run_models.py", "--model", "m", "--data", str(data), "--out", str(out),
            "--levels", "level4_hard", "--per-level", "5"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as e:
        run_models.main()
    assert "3 API failures in a row" in str(e.value)
    assert calls == ["level4_hard_001", "level4_hard_002", "level4_hard_003"]

    calls.clear()  # rerun: the three saved errors are retried first, not skipped
    with pytest.raises(SystemExit):
        run_models.main()
    assert calls == ["level4_hard_001", "level4_hard_002", "level4_hard_003"]
