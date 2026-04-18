from pathlib import Path

from utils.injection_tester import InjectionTester


def test_batch_handles_missing_document(tmp_path: Path):
    tests_file = tmp_path / "tests.json"
    tests_file.write_text(
        '[{"document":"missing.md","question":"q","expected_keywords":["x"]}]',
        encoding="utf-8",
    )
    tester = InjectionTester()
    results = tester.test_batch(str(tmp_path), str(tests_file))
    assert len(results) == 1
    assert results[0]["passed"] is False
    assert "Document not found" in results[0]["error"]


def test_generate_report_contains_summary():
    tester = InjectionTester()
    md = tester.generate_report(
        [
            {
                "document": "doc.md",
                "question": "q",
                "passed": True,
                "needs_manual_test": False,
                "keywords_found": ["a"],
                "keywords_missing": [],
                "response_summary": "ok",
            }
        ]
    )
    assert "Results: 1/1 passed" in md
    assert "doc.md" in md

"""Tests for InjectionTester utility."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from injection_tester import InjectionTester


@pytest.fixture
def tester():
    """Create a tester instance (no API key — will trigger manual test mode)."""
    return InjectionTester(provider="openai", model="test-model", api_key=None)


@pytest.fixture
def sample_kb_doc():
    """Create a temporary KB document for testing."""
    content = """# Test Domain Terms

## Active Customer
- **Correct definition:** A customer who made at least one purchase in the last 90 days
- **Naive interpretation:** Any customer row in the database

## Churn
- **Definition (retail):** No purchase activity in the last 30 days
- **Definition (telecom):** No calls, data usage, or payments in the last 90 days
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        path = f.name

    yield path
    os.unlink(path)


@pytest.fixture
def sample_test_cases(sample_kb_doc):
    """Create a temporary test cases JSON file."""
    doc_name = os.path.basename(sample_kb_doc)
    cases = [
        {
            "document": doc_name,
            "question": "What is the correct definition of active customer?",
            "expected_keywords": ["90 days", "purchase"],
        }
    ]
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(cases, f)
        path = f.name

    yield path
    os.unlink(path)


class TestInjectionTester:
    """Test suite for InjectionTester."""

    def test_test_without_api_key(self, tester, sample_kb_doc):
        """Test returns manual test required when no API key is available."""
        result = tester.test(
            document_path=sample_kb_doc,
            question="What is an active customer?",
            expected_keywords=["90 days", "purchase"],
        )

        assert result["document"] == os.path.basename(sample_kb_doc)
        assert result["needs_manual_test"] is True
        assert result["passed"] is False

    def test_test_result_structure(self, tester, sample_kb_doc):
        """Verify test result dict has all required fields."""
        result = tester.test(
            document_path=sample_kb_doc,
            question="test question",
            expected_keywords=["test"],
        )

        assert "document" in result
        assert "question" in result
        assert "passed" in result
        assert "response_summary" in result
        assert "keywords_found" in result
        assert "keywords_missing" in result

    def test_generate_report(self, tester):
        """Generate a markdown report from results."""
        mock_results = [
            {
                "document": "test.md",
                "question": "test?",
                "passed": True,
                "needs_manual_test": False,
                "response_summary": "answer",
                "keywords_found": ["key1"],
                "keywords_missing": [],
            },
            {
                "document": "test2.md",
                "question": "test2?",
                "passed": False,
                "needs_manual_test": False,
                "response_summary": "wrong",
                "keywords_found": [],
                "keywords_missing": ["key2"],
            },
        ]

        report = tester.generate_report(mock_results)

        assert "# Injection Test Report" in report
        assert "1/2 passed" in report
        assert "PASS" in report
        assert "FAIL" in report

    def test_generate_report_to_file(self, tester):
        """Write report to a file."""
        mock_results = [
            {
                "document": "test.md",
                "question": "test?",
                "passed": True,
                "needs_manual_test": False,
                "response_summary": "ok",
                "keywords_found": ["k"],
                "keywords_missing": [],
            }
        ]

        with tempfile.NamedTemporaryFile(
            suffix=".md", delete=False, mode="w"
        ) as f:
            path = f.name

        try:
            tester.generate_report(mock_results, output_path=path)
            content = open(path, encoding="utf-8").read()
            assert "# Injection Test Report" in content
        finally:
            os.unlink(path)

    def test_batch_missing_document(self, tester):
        """Batch test handles missing documents gracefully."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                [
                    {
                        "document": "nonexistent.md",
                        "question": "test",
                        "expected_keywords": ["x"],
                    }
                ],
                f,
            )
            tests_path = f.name

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = tester.test_batch(tmpdir, tests_path)
                assert len(results) == 1
                assert results[0]["passed"] is False
                assert "not found" in results[0].get("error", "").lower()
        finally:
            os.unlink(tests_path)

    # --- Multi-provider tests ---

    def test_supported_providers(self):
        """Verify all three providers are supported."""
        assert "openai" in InjectionTester.SUPPORTED_PROVIDERS
        assert "anthropic" in InjectionTester.SUPPORTED_PROVIDERS
        assert "google" in InjectionTester.SUPPORTED_PROVIDERS

    def test_default_model_openai(self):
        """OpenAI provider defaults to gpt-4o-mini."""
        tester = InjectionTester(provider="openai")
        assert tester.model == "gpt-4o-mini"

    def test_default_model_anthropic(self):
        """Anthropic provider defaults to claude-sonnet."""
        tester = InjectionTester(provider="anthropic")
        assert "claude" in tester.model

    def test_default_model_google(self):
        """Google provider defaults to gemini."""
        tester = InjectionTester(provider="google")
        assert "gemini" in tester.model

    def test_custom_model_override(self):
        """Custom model overrides the default."""
        tester = InjectionTester(provider="openai", model="gpt-4o")
        assert tester.model == "gpt-4o"

    def test_anthropic_no_api_key(self, sample_kb_doc):
        """Anthropic provider without key returns manual test required."""
        tester = InjectionTester(provider="anthropic", api_key=None)
        # Clear env var to ensure no key
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = tester.test(
                document_path=sample_kb_doc,
                question="test",
                expected_keywords=["test"],
            )
            assert result["needs_manual_test"] is True
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_google_no_api_key(self, sample_kb_doc):
        """Google provider without key returns manual test required."""
        tester = InjectionTester(provider="google", api_key=None)
        old_key = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            result = tester.test(
                document_path=sample_kb_doc,
                question="test",
                expected_keywords=["test"],
            )
            assert result["needs_manual_test"] is True
        finally:
            if old_key:
                os.environ["GOOGLE_API_KEY"] = old_key

    # --- OpenRouter tests ---

    def test_default_model_openrouter(self):
        """OpenRouter provider defaults to anthropic/claude-sonnet."""
        tester = InjectionTester(provider="openrouter")
        assert "anthropic/" in tester.model or "claude" in tester.model

    def test_openrouter_custom_model(self):
        """OpenRouter accepts any model string (provider/model format)."""
        tester = InjectionTester(provider="openrouter", model="google/gemini-2.0-flash-001")
        assert tester.model == "google/gemini-2.0-flash-001"

    def test_openrouter_no_api_key(self, sample_kb_doc):
        """OpenRouter without key returns manual test required."""
        tester = InjectionTester(provider="openrouter", api_key=None)
        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            result = tester.test(
                document_path=sample_kb_doc,
                question="test",
                expected_keywords=["test"],
            )
            assert result["needs_manual_test"] is True
        finally:
            if old_key:
                os.environ["OPENROUTER_API_KEY"] = old_key

    def test_openrouter_in_supported_providers(self):
        """OpenRouter is listed as a supported provider."""
        assert "openrouter" in InjectionTester.SUPPORTED_PROVIDERS
