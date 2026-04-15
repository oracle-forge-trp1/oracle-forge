"""
Injection Tester — KB Document Validation

Automates the Karpathy injection test protocol:
1. Load a KB document
2. Start a fresh LLM session with ONLY that document as context
3. Ask a test question
4. Check if the response contains expected keywords/concepts
5. Grade: PASS if keywords found, FAIL if missing

Supports multiple LLM providers: OpenAI, Anthropic, Google, or OpenRouter.
Falls back to manual test mode if no API key is available.
"""

import json
import os
from pathlib import Path
from typing import Any


class InjectionTester:
    """
    Validates KB documents by testing whether an LLM can correctly answer
    questions when provided only the document as context.
    """

    SUPPORTED_PROVIDERS = ("openai", "anthropic", "google", "openrouter")

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
    ):
        """
        Initialize the tester.

        Args:
            provider: LLM provider — 'openai', 'anthropic', 'google', or 'openrouter'
            model: Model name (defaults per provider if not set)
            api_key: API key (reads from env var if not provided)
        """
        self.provider = provider.lower()
        self.api_key = api_key

        # Default models per provider
        default_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "google": "gemini-2.0-flash",
            "openrouter": "anthropic/claude-sonnet-4-20250514",
        }
        self.model = model or default_models.get(self.provider, "gpt-4o-mini")

    def _get_api_key(self) -> str | None:
        """Resolve API key from init param or environment."""
        if self.api_key:
            return self.api_key

        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        env_var = env_vars.get(self.provider, "OPENAI_API_KEY")
        return os.environ.get(env_var)

    def _call_llm(self, system_context: str, question: str) -> str:
        """
        Call an LLM with the document as system context and the question as user input.
        """
        api_key = self._get_api_key()
        if not api_key:
            return (
                "[MANUAL TEST REQUIRED] No API key available. "
                "Please test this document manually by pasting it into a fresh "
                "LLM session and asking the test question."
            )

        if self.provider == "openai":
            return self._call_openai(api_key, system_context, question)
        elif self.provider == "anthropic":
            return self._call_anthropic(api_key, system_context, question)
        elif self.provider == "google":
            return self._call_google(api_key, system_context, question)
        elif self.provider == "openrouter":
            return self._call_openrouter(api_key, system_context, question)
        else:
            return f"[ERROR] Unsupported provider: {self.provider}"

    def _call_openai(self, api_key: str, context: str, question: str) -> str:
        try:
            import openai

            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. Answer the user's question "
                            "based ONLY on the following document. If the document "
                            "does not contain the answer, say 'NOT FOUND IN DOCUMENT'.\n\n"
                            f"---\n{context}\n---"
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                temperature=0,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except ImportError:
            return (
                "[MANUAL TEST REQUIRED] openai package not installed. "
                "Install with: pip install openai"
            )
        except Exception as e:
            return f"[ERROR] OpenAI call failed: {e}"

    def _call_anthropic(self, api_key: str, context: str, question: str) -> str:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                system=(
                    "You are a helpful assistant. Answer the user's question "
                    "based ONLY on the following document. If the document "
                    "does not contain the answer, say 'NOT FOUND IN DOCUMENT'.\n\n"
                    f"---\n{context}\n---"
                ),
                messages=[{"role": "user", "content": question}],
            )
            return response.content[0].text
        except ImportError:
            return (
                "[MANUAL TEST REQUIRED] anthropic package not installed. "
                "Install with: pip install anthropic"
            )
        except Exception as e:
            return f"[ERROR] Anthropic call failed: {e}"

    def _call_google(self, api_key: str, context: str, question: str) -> str:
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model)
            prompt = (
                "You are a helpful assistant. Answer the question "
                "based ONLY on the following document. If the document "
                "does not contain the answer, say 'NOT FOUND IN DOCUMENT'.\n\n"
                f"---\n{context}\n---\n\n"
                f"Question: {question}"
            )
            response = model.generate_content(prompt)
            return response.text
        except ImportError:
            return (
                "[MANUAL TEST REQUIRED] google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )
        except Exception as e:
            return f"[ERROR] Google AI call failed: {e}"

    def _call_openrouter(self, api_key: str, context: str, question: str) -> str:
        """Call OpenRouter API (OpenAI-compatible with custom base_url)."""
        try:
            import openai

            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. Answer the user's question "
                            "based ONLY on the following document. If the document "
                            "does not contain the answer, say 'NOT FOUND IN DOCUMENT'.\n\n"
                            f"---\n{context}\n---"
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                temperature=0,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except ImportError:
            return (
                "[MANUAL TEST REQUIRED] openai package not installed. "
                "OpenRouter uses the OpenAI SDK. Install with: pip install openai"
            )
        except Exception as e:
            return f"[ERROR] OpenRouter call failed: {e}"

    def test(
        self,
        document_path: str,
        question: str,
        expected_keywords: list[str],
        case_sensitive: bool = False,
    ) -> dict[str, Any]:
        """
        Test a single KB document.

        Args:
            document_path: Path to the markdown document
            question: Test question to ask
            expected_keywords: Keywords/phrases that should appear in the response
            case_sensitive: Whether keyword matching is case-sensitive

        Returns:
            Test result dict with pass/fail, response, keywords found/missing
        """
        doc_content = Path(document_path).read_text(encoding="utf-8")

        response = self._call_llm(doc_content, question)

        check_response = response if case_sensitive else response.lower()
        found = []
        missing = []
        for keyword in expected_keywords:
            check_keyword = keyword if case_sensitive else keyword.lower()
            if check_keyword in check_response:
                found.append(keyword)
            else:
                missing.append(keyword)

        passed = len(missing) == 0 and "[MANUAL TEST REQUIRED]" not in response
        needs_manual = "[MANUAL TEST REQUIRED]" in response

        return {
            "document": Path(document_path).name,
            "question": question,
            "passed": passed,
            "needs_manual_test": needs_manual,
            "response_summary": response[:300],
            "keywords_found": found,
            "keywords_missing": missing,
        }

    def test_batch(
        self, kb_directory: str, tests_file: str
    ) -> list[dict[str, Any]]:
        """
        Run injection tests for all documents in a directory using a test definition file.

        Args:
            kb_directory: Path to the KB subdirectory (e.g., "kb/domain/")
            tests_file: Path to JSON file with test definitions

        Returns:
            List of test result dicts

        Test file format:
        [
            {
                "document": "join_keys.md",
                "question": "What data quality issues affect crmarenapro join keys?",
                "expected_keywords": ["#", "whitespace", "strip"]
            }
        ]
        """
        tests = json.loads(Path(tests_file).read_text(encoding="utf-8"))
        kb_dir = Path(kb_directory)

        results = []
        for test_def in tests:
            doc_path = kb_dir / test_def["document"]
            if not doc_path.exists():
                results.append({
                    "document": test_def["document"],
                    "question": test_def["question"],
                    "passed": False,
                    "error": f"Document not found: {doc_path}",
                })
                continue

            result = self.test(
                document_path=str(doc_path),
                question=test_def["question"],
                expected_keywords=test_def["expected_keywords"],
            )
            results.append(result)

        return results

    def generate_report(
        self, results: list[dict[str, Any]], output_path: str | None = None
    ) -> str:
        """
        Generate a markdown report from test results.

        Args:
            results: List of test result dicts
            output_path: Optional path to write the report

        Returns:
            Markdown-formatted report string
        """
        lines = ["# Injection Test Report\n"]
        passed_count = sum(1 for r in results if r.get("passed"))
        total = len(results)

        lines.append(f"**Results: {passed_count}/{total} passed**\n")

        for r in results:
            status = "PASS" if r.get("passed") else "FAIL"
            if r.get("needs_manual_test"):
                status = "MANUAL TEST NEEDED"
            lines.append(f"## {r['document']} — {status}\n")
            lines.append(f"**Question:** {r['question']}\n")
            if r.get("error"):
                lines.append(f"**Error:** {r['error']}\n")
            else:
                if r.get("keywords_found"):
                    lines.append(f"**Keywords found:** {', '.join(r['keywords_found'])}")
                if r.get("keywords_missing"):
                    lines.append(f"**Keywords missing:** {', '.join(r['keywords_missing'])}")
                lines.append(f"\n**Response preview:** {r.get('response_summary', 'N/A')}\n")
            lines.append("---\n")

        report = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(report, encoding="utf-8")

        return report
