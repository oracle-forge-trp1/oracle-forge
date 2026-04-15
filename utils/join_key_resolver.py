"""
Join Key Resolver — Cross-Database Key Normalization

Detects and resolves format mismatches in join keys across databases.
Handles DAB-specific patterns:
- yelp: businessid_X vs businessref_X prefix mismatch
- crmarenapro: leading '#' prefix and trailing whitespace corruption
- bookreview: different column names (book_id vs purchase_id) for same entity
- Generic: prefixed strings, zero-padded integers, plain integers

This is critical for DAB because the same entity has different ID formats
across PostgreSQL, MongoDB, SQLite, and DuckDB.
"""

import re
from collections import defaultdict
from typing import Any


class JoinKeyResolver:
    """Detects format mismatches in join keys and normalizes them for cross-database joins."""

    # DAB-specific prefixes (from actual datasets) + common enterprise patterns
    KNOWN_PREFIXES = [
        # DAB yelp dataset
        "businessid_", "businessref_",
        # Generic enterprise patterns
        "CUST-", "cust_", "C-", "CUSTOMER-",
        "ORD-", "ord_", "ORDER-",
        "PROD-", "prod_", "PRODUCT-",
        "TXN-", "txn_", "TRANS-",
        "ACCT-", "acct_", "ACC-",
    ]

    def detect_format(self, sample_values: list) -> dict[str, Any]:
        """
        Analyze a sample of key values to detect the format pattern.

        Args:
            sample_values: List of sample key values from one database

        Returns:
            Dict with pattern info: type, prefix, padding, etc.
        """
        if not sample_values:
            return {"type": "unknown", "pattern": None}

        # Filter out None values
        values = [v for v in sample_values if v is not None]
        if not values:
            return {"type": "unknown", "pattern": None}

        # Check if all values are integers
        if all(isinstance(v, int) for v in values):
            return {"type": "integer", "pattern": "N", "prefix": None, "padding": 0}

        # Convert all to strings for pattern analysis
        str_values = [str(v).strip() for v in values]

        # Check for CRM-style '#' corruption
        if all(s.startswith("#") for s in str_values):
            return {
                "type": "hash_prefixed",
                "pattern": "#...",
                "prefix": "#",
                "padding": 0,
            }

        # Check for known prefix
        detected_prefix = None
        for prefix in self.KNOWN_PREFIXES:
            if all(s.startswith(prefix) for s in str_values):
                detected_prefix = prefix
                break

        # Auto-detect prefix if not in known list
        if detected_prefix is None and len(str_values) >= 2:
            common = self._common_prefix(str_values)
            # Only treat as prefix if it ends with a separator char
            if common and len(common) >= 2 and not common[-1].isdigit():
                detected_prefix = common

        if detected_prefix:
            numeric_parts = [s[len(detected_prefix):] for s in str_values]
            if all(p.isdigit() for p in numeric_parts if p):
                max_len = max(len(p) for p in numeric_parts if p) if numeric_parts else 0
                is_padded = all(len(p) == max_len for p in numeric_parts if p)
                return {
                    "type": "prefixed_int",
                    "pattern": f"{detected_prefix}{'N' * max_len}",
                    "prefix": detected_prefix,
                    "padding": max_len if is_padded else 0,
                }
            return {
                "type": "prefixed_string",
                "pattern": f"{detected_prefix}...",
                "prefix": detected_prefix,
                "padding": 0,
            }

        # Check for zero-padded integers
        if all(s.isdigit() for s in str_values):
            lengths = set(len(s) for s in str_values)
            if len(lengths) == 1:
                return {
                    "type": "padded_int",
                    "pattern": "0" * list(lengths)[0],
                    "prefix": None,
                    "padding": list(lengths)[0],
                }
            return {"type": "string_int", "pattern": "N+", "prefix": None, "padding": 0}

        # Default: treat as opaque string
        return {"type": "string", "pattern": None, "prefix": None, "padding": 0}

    def normalize(self, value: Any, target_type: str = "integer") -> Any:
        """
        Normalize a single key value to a canonical form.

        Handles:
        - Whitespace stripping (CRM trailing spaces)
        - '#' prefix removal (CRM corruption)
        - Known prefix removal (yelp businessid_/businessref_, CUST-, etc.)
        - Leading zero removal
        - Type casting

        Args:
            value: The raw key value
            target_type: Target type — 'integer', 'string', or 'stripped'

        Returns:
            Normalized value
        """
        if value is None:
            return None

        str_val = str(value).strip()

        # Strip CRM '#' corruption
        str_val = str_val.lstrip("#")

        # Strip known prefixes
        for prefix in self.KNOWN_PREFIXES:
            if str_val.startswith(prefix):
                str_val = str_val[len(prefix):]
                break

        # Strip leading zeros (preserve "0" itself)
        stripped = str_val.lstrip("0") or "0"

        if target_type == "integer":
            try:
                return int(stripped)
            except ValueError:
                return str_val  # Can't convert, return as-is
        elif target_type == "stripped":
            return stripped
        else:
            return str_val

    def normalize_batch(
        self, values: list, target_type: str = "integer"
    ) -> list:
        """Normalize a list of key values."""
        return [self.normalize(v, target_type) for v in values]

    def build_key_map(
        self, records: list[dict], key_field: str, target_type: str = "integer"
    ) -> dict[str, list[dict]]:
        """
        Build a lookup map from normalized key to list of records.

        Uses lists to handle duplicate keys correctly (e.g., one customer
        with multiple orders).

        Args:
            records: List of record dicts
            key_field: Name of the key field in each record
            target_type: How to normalize the key

        Returns:
            Dict mapping normalized_key -> list of records
        """
        result = defaultdict(list)
        for record in records:
            raw_key = record.get(key_field)
            norm_key = self.normalize(raw_key, target_type)
            result[norm_key].append(record)
        return dict(result)

    def join(
        self,
        left_data: list[dict],
        right_data: list[dict],
        left_key: str,
        right_key: str,
        how: str = "inner",
        target_type: str = "integer",
    ) -> list[dict]:
        """
        Join two result sets from different databases with key normalization.

        Handles many-to-many: if multiple records share a normalized key,
        all combinations are produced (cross product per key).

        Args:
            left_data: Records from database A
            right_data: Records from database B
            left_key: Key field name in left_data
            right_key: Key field name in right_data
            how: Join type — 'inner', 'left', 'right', or 'outer'
            target_type: Normalization target type

        Returns:
            List of merged record dicts
        """
        right_map = self.build_key_map(right_data, right_key, target_type)

        merged = []
        matched_right_keys = set()

        for left_record in left_data:
            norm_key = self.normalize(left_record.get(left_key), target_type)
            right_records = right_map.get(norm_key, [])

            if right_records:
                for right_record in right_records:
                    combined = {**left_record, **right_record}
                    combined["_join_key_normalized"] = norm_key
                    merged.append(combined)
                matched_right_keys.add(norm_key)
            elif how in ("left", "outer"):
                combined = {**left_record, "_join_key_normalized": norm_key}
                merged.append(combined)

        if how in ("right", "outer"):
            for right_record in right_data:
                norm_key = self.normalize(right_record.get(right_key), target_type)
                if norm_key not in matched_right_keys:
                    combined = {**right_record, "_join_key_normalized": norm_key}
                    merged.append(combined)

        return merged

    def diagnose_join_failure(
        self,
        left_data: list[dict],
        right_data: list[dict],
        left_key: str,
        right_key: str,
    ) -> dict[str, Any]:
        """
        Diagnose why a cross-database join returned 0 results.

        Returns a diagnosis with detected formats and suggested fix.
        """
        left_samples = [r.get(left_key) for r in left_data[:20] if r.get(left_key)]
        right_samples = [r.get(right_key) for r in right_data[:20] if r.get(right_key)]

        left_format = self.detect_format(left_samples)
        right_format = self.detect_format(right_samples)

        format_mismatch = left_format["type"] != right_format["type"]
        prefix_mismatch = left_format.get("prefix") != right_format.get("prefix")

        # Check for whitespace issues
        left_has_whitespace = any(
            str(v) != str(v).strip() for v in left_samples
        )
        right_has_whitespace = any(
            str(v) != str(v).strip() for v in right_samples
        )
        whitespace_issue = left_has_whitespace or right_has_whitespace

        # Check for '#' corruption
        left_has_hash = any(str(v).startswith("#") for v in left_samples)
        right_has_hash = any(str(v).startswith("#") for v in right_samples)
        hash_corruption = left_has_hash or right_has_hash

        # Try normalized join to see if it would work
        test_merge = self.join(
            left_data[:10], right_data[:10], left_key, right_key, how="inner"
        )

        # Build suggestion
        issues = []
        if format_mismatch or prefix_mismatch:
            issues.append(
                "Strip prefixes and leading zeros, then cast to common type."
            )
        if whitespace_issue:
            issues.append("Strip trailing whitespace from key values.")
        if hash_corruption:
            issues.append("Strip leading '#' from corrupted IDs (CRM pattern).")
        if not issues:
            issues.append("Key formats appear compatible. Check for data quality issues.")

        return {
            "left_format": left_format,
            "right_format": right_format,
            "format_mismatch": format_mismatch,
            "prefix_mismatch": prefix_mismatch,
            "whitespace_issue": whitespace_issue,
            "hash_corruption": hash_corruption,
            "normalized_join_would_match": len(test_merge) > 0,
            "sample_left": left_samples[:3],
            "sample_right": right_samples[:3],
            "suggestion": " ".join(issues),
        }

    @staticmethod
    def _common_prefix(strings: list[str]) -> str:
        """Find the common prefix of a list of strings."""
        if not strings:
            return ""
        shortest = min(strings, key=len)
        for i, char in enumerate(shortest):
            if any(s[i] != char for s in strings):
                return shortest[:i]
        return shortest
