"""
Integration tests for InjectionTester — validates that the KB documents
actually answer questions correctly when injected as LLM context.

Uses OpenRouter (same provider as the production agent). Skips automatically
if the API key is unavailable or the token budget is exhausted.

Run:
    conda run -n dabench pytest utils/tests/test_injection_tester_kb.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from injection_tester import InjectionTester

REPO_ROOT = Path(__file__).parent.parent.parent
KB_DIR    = REPO_ROOT / "kb"

# Skip all tests if no API key is configured
OPENROUTER_KEY = os.getenv("ANTHROPIC_API_KEY")  # project uses ANTHROPIC_API_KEY for OpenRouter
pytestmark = pytest.mark.skipif(
    not OPENROUTER_KEY,
    reason="ANTHROPIC_API_KEY (OpenRouter) not set — skip LLM injection tests",
)


@pytest.fixture(scope="module")
def tester():
    return InjectionTester(
        provider="openrouter",
        model="anthropic/claude-haiku-4-5",
        api_key=OPENROUTER_KEY,
    )


# ── Corrections log ───────────────────────────────────────────────────────────

class TestCorrectionsLog:
    """Verify that the corrections log can be retrieved correctly by an LLM."""

    CORRECTIONS_LOG = KB_DIR / "corrections" / "corrections-log.md"

    def test_join_key_correction_retrievable(self, tester):
        """Entry 001: Agent should know to strip prefixes from Yelp join keys."""
        result = tester.test(
            document_path=str(self.CORRECTIONS_LOG),
            question=(
                "How should I join MongoDB business_id values like 'businessid_34' "
                "with DuckDB business_ref values like 'businessref_34'?"
            ),
            expected_keywords=["strip", "integer", "prefix"],
        )
        assert result["passed"], (
            f"Corrections log failed join key test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )

    def test_date_format_correction_retrievable(self, tester):
        """Entry 002: Agent should know to use TRY_STRPTIME with multiple patterns."""
        result = tester.test(
            document_path=str(self.CORRECTIONS_LOG),
            question="How should I filter DuckDB review.date by year without dropping rows?",
            expected_keywords=["TRY_STRPTIME", "COALESCE"],
        )
        assert result["passed"], (
            f"Corrections log failed date format test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )

    def test_stockindex_up_day_correction_retrievable(self, tester):
        """Entry 008: Agent should define 'up day' as Close > Open, not prev_Close."""
        result = tester.test(
            document_path=str(self.CORRECTIONS_LOG),
            question="How should I define an 'up day' for stockindex queries?",
            expected_keywords=["Open", "Close"],
        )
        assert result["passed"], (
            f"Corrections log failed up-day test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )

    def test_dca_methodology_retrievable(self, tester):
        """Entry 009: Agent should know DCA = sum of intramonth returns, not buy-and-hold."""
        result = tester.test(
            document_path=str(self.CORRECTIONS_LOG),
            question=(
                "If asked about 'monthly investments' in stock indices since 2000, "
                "should I use buy-and-hold or DCA? What are the top 5 indices?"
            ),
            expected_keywords=["399001.SZ", "IXIC", "NSEI"],
        )
        assert result["passed"], (
            f"Corrections log failed DCA test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )


# ── Domain KB ─────────────────────────────────────────────────────────────────

class TestYelpDomainKB:
    """Verify yelp-domain.md is retrievable for key questions."""

    YELP_DOMAIN = KB_DIR / "domain" / "yelp-domain.md"

    @pytest.fixture(autouse=True)
    def skip_if_missing(self):
        if not self.YELP_DOMAIN.exists():
            pytest.skip(f"Domain file not found: {self.YELP_DOMAIN}")

    def test_location_extraction_pattern(self, tester):
        """Agent should know location is in description field, not a structured field."""
        result = tester.test(
            document_path=str(self.YELP_DOMAIN),
            question="Where is city and state stored for Yelp businesses?",
            expected_keywords=["description"],
        )
        assert result["passed"], (
            f"Yelp domain KB failed location test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )

    def test_attributes_are_string_valued(self, tester):
        """Agent should know boolean attributes are stored as strings 'True'/'False'."""
        result = tester.test(
            document_path=str(self.YELP_DOMAIN),
            question="How are boolean attributes like BikeParking stored in MongoDB?",
            expected_keywords=["string", "True"],
        )
        assert result["passed"], (
            f"Yelp domain KB failed attributes test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )


class TestJoinKeysKB:
    """Verify join_keys.md covers all known DAB cross-DB join mismatches."""

    JOIN_KEYS_DOC = KB_DIR / "domain" / "join_keys.md"

    @pytest.fixture(autouse=True)
    def skip_if_missing(self):
        if not self.JOIN_KEYS_DOC.exists():
            pytest.skip(f"Domain file not found: {self.JOIN_KEYS_DOC}")

    def test_crm_hash_corruption_documented(self, tester):
        """Agent should know crmarenapro has '#' prefix corruption."""
        result = tester.test(
            document_path=str(self.JOIN_KEYS_DOC),
            question="What data quality issue affects join keys in the crmarenapro dataset?",
            expected_keywords=["#"],
        )
        assert result["passed"], (
            f"join_keys.md failed CRM hash test.\n"
            f"Missing: {result['keywords_missing']}\n"
            f"Response: {result['response_summary']}"
        )
