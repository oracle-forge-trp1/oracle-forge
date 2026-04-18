"""Round-trip for eval harness score log JSON."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_harness():
    spec = importlib.util.spec_from_file_location("_of_harness", REPO / "eval" / "harness.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_append_score_log_roundtrip() -> None:
    h = _load_harness()
    append_score_log, read_score_log = h.append_score_log, h.read_score_log

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "log.json"
        rec = {
            "run_id": "test-001",
            "dataset": "yelp",
            "date": "2099-01-01",
            "total_queries": 1,
            "passed": 0,
            "failed": 1,
            "pass_at_1": 0.0,
            "agent_module": "dummy",
            "dab_root": "/tmp",
            "methodology": {"note": "unit test"},
            "results": [],
        }
        append_score_log(p, rec)
        runs = read_score_log(p)
        assert len(runs) == 1
        assert runs[0]["run_id"] == "test-001"
        append_score_log(p, {**rec, "run_id": "test-002"})
        runs2 = read_score_log(p)
        assert len(runs2) == 2


def test_read_score_log_empty_file() -> None:
    read_score_log = _load_harness().read_score_log

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "empty.json"
        p.write_text("[]\n", encoding="utf-8")
        assert read_score_log(p) == []
