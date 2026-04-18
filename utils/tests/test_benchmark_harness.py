"""Tests for utils/benchmark_harness.py — unit tests only (no live DB required)."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from benchmark_harness import BenchmarkHarness


@pytest.fixture
def mock_run_record():
    """A minimal run_harness result dict."""
    return {
        "run_id": "2026-04-15-test",
        "dataset": "yelp",
        "date": "2026-04-15",
        "total_queries": 2,
        "passed": 1,
        "failed": 1,
        "pass_at_1": 0.5,
        "agent_module": "agent.data_agent",
        "dab_root": "/tmp/dab",
        "results": [
            {
                "query_id": "query1",
                "question": "What is the average rating?",
                "agent_answer": "3.55",
                "query_trace": [],
                "passed": True,
                "execution_time_sec": 17.5,
                "validation_message": "Found matching number: 3.55",
                "error": None,
            },
            {
                "query_id": "query2",
                "question": "What is the top state?",
                "agent_answer": "",
                "query_trace": [],
                "passed": False,
                "execution_time_sec": 240.0,
                "validation_message": None,
                "error": "agent_timeout_after_240.0s",
            },
        ],
    }


def test_run_dataset_calls_run_harness(mock_run_record):
    with patch("benchmark_harness.run_harness", return_value=mock_run_record) as mock_fn:
        harness = BenchmarkHarness(agent_module="agent.data_agent")
        result = harness.run_dataset("yelp", run_id="test-001")

    mock_fn.assert_called_once()
    call_kwargs = mock_fn.call_args.kwargs
    assert call_kwargs["dataset"] == "yelp"
    assert call_kwargs["agent_module"] == "agent.data_agent"
    assert call_kwargs["run_id"] == "test-001"
    assert result["pass_at_1"] == 0.5


def test_run_dataset_dummy_mode(mock_run_record):
    with patch("benchmark_harness.run_harness", return_value=mock_run_record) as mock_fn:
        harness = BenchmarkHarness()
        harness.run_dataset("yelp", dummy=True)

    call_kwargs = mock_fn.call_args.kwargs
    assert call_kwargs["dummy"] is True
    assert call_kwargs["agent_module"] is None


def test_run_trials_aggregates_correctly(mock_run_record):
    with patch("benchmark_harness.run_harness", return_value=mock_run_record):
        harness = BenchmarkHarness()
        results = harness.run_trials("yelp", n_trials=3)

    assert results["n_trials"] == 3
    assert len(results["trial_runs"]) == 3
    # query1 passes in all 3 trials
    assert results["query_pass_counts"]["query1"] == 3
    # query2 never passes
    assert results["query_pass_counts"].get("query2", 0) == 0
    # pass@1 = 0.5 (mean of 3 trials, each 0.5)
    assert results["pass_at_1"] == 0.5
    # pass@k = 0.5 (query1 passes in at least 1 trial; query2 never does)
    assert results["pass_at_k"] == 0.5


def test_export_results_writes_correct_format(mock_run_record, tmp_path):
    with patch("benchmark_harness.run_harness", return_value=mock_run_record):
        harness = BenchmarkHarness()
        trial_results = harness.run_trials("yelp", n_trials=2)

    output = tmp_path / "results.json"
    harness.export_results(trial_results, str(output))

    assert output.exists()
    entries = json.loads(output.read_text())
    assert isinstance(entries, list)
    # 2 trials × 2 queries = 4 entries
    assert len(entries) == 4
    # Each entry has required DAB fields
    for entry in entries:
        assert "dataset" in entry
        assert "query" in entry
        assert "run" in entry
        assert "answer" in entry
        assert entry["dataset"] == "yelp"
