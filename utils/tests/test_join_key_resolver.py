"""Tests for JoinKeyResolver utility."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from join_key_resolver import JoinKeyResolver


@pytest.fixture
def resolver():
    """Create a fresh JoinKeyResolver instance."""
    return JoinKeyResolver()


class TestDetectFormat:
    """Test format detection on various key styles."""

    def test_integer_keys(self, resolver):
        """Detect plain integer keys."""
        result = resolver.detect_format([1, 2, 3, 100, 200])
        assert result["type"] == "integer"

    def test_prefixed_keys(self, resolver):
        """Detect prefixed string keys like CUST-00123."""
        result = resolver.detect_format(["CUST-00123", "CUST-00456", "CUST-00789"])
        assert result["type"] == "prefixed_int"
        assert result["prefix"] == "CUST-"

    def test_zero_padded_keys(self, resolver):
        """Detect zero-padded integer strings."""
        result = resolver.detect_format(["00123", "00456", "00789"])
        assert result["type"] == "padded_int"
        assert result["padding"] == 5

    def test_string_int_keys(self, resolver):
        """Detect string integer keys with varying lengths."""
        result = resolver.detect_format(["123", "4567", "89"])
        assert result["type"] == "string_int"

    def test_empty_input(self, resolver):
        """Handle empty input gracefully."""
        result = resolver.detect_format([])
        assert result["type"] == "unknown"

    def test_none_values(self, resolver):
        """Handle None values in sample."""
        result = resolver.detect_format([None, None, None])
        assert result["type"] == "unknown"

    # --- DAB-specific format tests ---

    def test_yelp_businessid_prefix(self, resolver):
        """Detect yelp businessid_ prefix pattern."""
        result = resolver.detect_format(["businessid_1", "businessid_2", "businessid_3"])
        assert result["prefix"] == "businessid_"

    def test_yelp_businessref_prefix(self, resolver):
        """Detect yelp businessref_ prefix pattern."""
        result = resolver.detect_format(["businessref_1", "businessref_2", "businessref_3"])
        assert result["prefix"] == "businessref_"

    def test_crm_hash_corruption(self, resolver):
        """Detect CRM leading '#' corruption pattern."""
        result = resolver.detect_format(
            ["#001Wt00000PFj4z", "#001Wt00000QGk5a", "#001Wt00000RHl6b"]
        )
        assert result["type"] == "hash_prefixed"
        assert result["prefix"] == "#"


class TestNormalize:
    """Test key normalization."""

    def test_integer_passthrough(self, resolver):
        """Integer keys pass through unchanged."""
        assert resolver.normalize(123) == 123

    def test_strip_prefix(self, resolver):
        """Strip known prefixes and convert to int."""
        assert resolver.normalize("CUST-00123") == 123
        assert resolver.normalize("ORD-0042") == 42
        assert resolver.normalize("PROD-001") == 1

    def test_strip_leading_zeros(self, resolver):
        """Strip leading zeros from padded strings."""
        assert resolver.normalize("00123") == 123
        assert resolver.normalize("000") == 0

    def test_string_integer(self, resolver):
        """Convert string integers to int."""
        assert resolver.normalize("456") == 456

    def test_none_value(self, resolver):
        """Handle None input."""
        assert resolver.normalize(None) is None

    def test_normalize_to_string(self, resolver):
        """Normalize to string type when requested."""
        result = resolver.normalize("CUST-00123", target_type="string")
        assert result == "00123"

    def test_normalize_to_stripped(self, resolver):
        """Normalize to stripped type when requested."""
        result = resolver.normalize("CUST-00123", target_type="stripped")
        assert result == "123"

    # --- DAB-specific normalization tests ---

    def test_yelp_businessid_normalization(self, resolver):
        """Normalize yelp businessid_ prefix to integer."""
        assert resolver.normalize("businessid_42") == 42

    def test_yelp_businessref_normalization(self, resolver):
        """Normalize yelp businessref_ prefix to integer."""
        assert resolver.normalize("businessref_42") == 42

    def test_yelp_keys_normalize_to_same_value(self, resolver):
        """Both yelp key formats normalize to the same integer."""
        assert resolver.normalize("businessid_7") == resolver.normalize("businessref_7")

    def test_crm_hash_strip(self, resolver):
        """Strip leading '#' from CRM-corrupted IDs."""
        result = resolver.normalize("#001Wt00000PFj4z", target_type="string")
        assert result == "001Wt00000PFj4z"
        assert not result.startswith("#")

    def test_whitespace_strip(self, resolver):
        """Strip trailing whitespace from values."""
        result = resolver.normalize("  Company Name  ", target_type="string")
        assert result == "Company Name"
        assert not result.endswith(" ")
        assert not result.startswith(" ")

    def test_combined_hash_and_whitespace(self, resolver):
        """Handle both '#' prefix and whitespace simultaneously."""
        result = resolver.normalize("  #001Wt00000PFj4z  ", target_type="string")
        assert result == "001Wt00000PFj4z"


class TestJoin:
    """Test cross-database join with key normalization."""

    def test_inner_join_with_format_mismatch(self, resolver):
        """Join records where keys have different formats."""
        pg_data = [
            {"customer_id": 123, "name": "Alice", "total": 100},
            {"customer_id": 456, "name": "Bob", "total": 200},
            {"customer_id": 789, "name": "Charlie", "total": 300},
        ]
        mongo_data = [
            {"customerId": "CUST-00123", "tickets": 3},
            {"customerId": "CUST-00456", "tickets": 1},
            {"customerId": "CUST-00999", "tickets": 5},  # No match
        ]

        merged = resolver.join(
            pg_data, mongo_data,
            left_key="customer_id",
            right_key="customerId",
            how="inner",
        )

        assert len(merged) == 2
        alice = next(r for r in merged if r.get("name") == "Alice")
        assert alice["tickets"] == 3
        assert alice["_join_key_normalized"] == 123

    def test_left_join(self, resolver):
        """Left join keeps all left records even without matches."""
        left = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
        right = [{"id": "CUST-00001", "score": 10}]

        merged = resolver.join(left, right, "id", "id", how="left")
        assert len(merged) == 2

    def test_empty_join(self, resolver):
        """Join with empty data returns empty."""
        merged = resolver.join([], [], "id", "id")
        assert merged == []

    # --- DAB-specific join tests ---

    def test_yelp_cross_db_join(self, resolver):
        """Join yelp MongoDB business data with DuckDB review data."""
        mongo_businesses = [
            {"business_id": "businessid_1", "name": "Pizza Place"},
            {"business_id": "businessid_2", "name": "Sushi Bar"},
        ]
        duckdb_reviews = [
            {"business_ref": "businessref_1", "stars": 4.5},
            {"business_ref": "businessref_2", "stars": 3.0},
            {"business_ref": "businessref_99", "stars": 5.0},  # No match
        ]

        merged = resolver.join(
            mongo_businesses, duckdb_reviews,
            left_key="business_id",
            right_key="business_ref",
            how="inner",
        )

        assert len(merged) == 2
        pizza = next(r for r in merged if r.get("name") == "Pizza Place")
        assert pizza["stars"] == 4.5

    def test_crm_join_with_hash_corruption(self, resolver):
        """Join CRM data where one side has '#' prefix corruption."""
        clean_data = [
            {"Id": "001Wt00000PFj4z", "name": "Acme"},
        ]
        corrupted_data = [
            {"AccountId": "#001Wt00000PFj4z", "status": "Open"},
        ]

        merged = resolver.join(
            clean_data, corrupted_data,
            left_key="Id",
            right_key="AccountId",
            how="inner",
            target_type="string",
        )

        assert len(merged) == 1
        assert merged[0]["name"] == "Acme"
        assert merged[0]["status"] == "Open"

    def test_many_to_many_join(self, resolver):
        """Join with duplicate keys produces cross product per key."""
        left = [
            {"id": 1, "order": "A"},
            {"id": 1, "order": "B"},
        ]
        right = [
            {"id": "CUST-00001", "ticket": "T1"},
            {"id": "CUST-00001", "ticket": "T2"},
        ]

        merged = resolver.join(left, right, "id", "id", how="inner")
        # 2 left x 2 right = 4 combinations for key 1
        assert len(merged) == 4


class TestDiagnoseJoinFailure:
    """Test join failure diagnosis."""

    def test_detects_format_mismatch(self, resolver):
        """Diagnose correctly identifies format mismatch."""
        left = [{"id": 123}, {"id": 456}]
        right = [{"id": "CUST-00123"}, {"id": "CUST-00456"}]

        diagnosis = resolver.diagnose_join_failure(left, right, "id", "id")

        assert diagnosis["format_mismatch"] is True
        assert diagnosis["normalized_join_would_match"] is True

    def test_compatible_formats(self, resolver):
        """Compatible formats produce no mismatch diagnosis."""
        left = [{"id": 1}, {"id": 2}]
        right = [{"id": 1}, {"id": 2}]

        diagnosis = resolver.diagnose_join_failure(left, right, "id", "id")

        assert diagnosis["format_mismatch"] is False

    def test_detects_whitespace_issue(self, resolver):
        """Diagnose detects trailing whitespace corruption."""
        left = [{"id": "abc  "}, {"id": "def  "}]
        right = [{"id": "abc"}, {"id": "def"}]

        diagnosis = resolver.diagnose_join_failure(left, right, "id", "id")

        assert diagnosis["whitespace_issue"] is True

    def test_detects_hash_corruption(self, resolver):
        """Diagnose detects CRM '#' corruption."""
        left = [{"id": "#001Wt"}, {"id": "#002Xt"}]
        right = [{"id": "001Wt"}, {"id": "002Xt"}]

        diagnosis = resolver.diagnose_join_failure(left, right, "id", "id")

        assert diagnosis["hash_corruption"] is True
