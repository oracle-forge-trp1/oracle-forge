"""Tests for utils.join_key_resolver — runnable without DB or MCP."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from utils.join_key_resolver import JoinKeyResolver  # noqa: E402


def test_normalize_yelp_style_prefix() -> None:
    r = JoinKeyResolver()
    assert r.normalize("businessid_42", target_type="integer") == 42
    assert r.normalize("businessref_42", target_type="integer") == 42


def test_normalize_batch_overlap() -> None:
    r = JoinKeyResolver()
    left = ["businessid_1", "businessid_2"]
    right = ["businessref_2", "businessref_3"]
    ln = r.normalize_batch(left)
    rn = r.normalize_batch(right)
    assert set(ln) & set(rn) == {2}


def test_detect_format_has_prefix_key() -> None:
    r = JoinKeyResolver()
    fmt = r.detect_format(["businessid_10"])
    assert "prefix" in fmt
