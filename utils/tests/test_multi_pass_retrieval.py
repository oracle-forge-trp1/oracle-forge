from pathlib import Path

from utils.multi_pass_retrieval import MultiPassRetriever


def test_suggest_document_for_join_failure(tmp_path: Path):
    kb_root = tmp_path / "kb"
    p = kb_root / "domain" / "join_keys.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("join help", encoding="utf-8")

    retriever = MultiPassRetriever(kb_root=str(kb_root))
    doc = retriever.suggest_document("why 0 rows", "join returned zero rows due to businessid mismatch")
    assert doc == "domain/join_keys.md"


def test_retrieve_and_retry_stops_when_valid():
    retriever = MultiPassRetriever(kb_root="kb")
    calls = {"n": 0}

    def attempt_fn(_ctx: str) -> str:
        calls["n"] += 1
        return "ok"

    result = retriever.retrieve_and_retry(
        question="q",
        attempt_fn=attempt_fn,
        validate_fn=lambda ans: ans == "ok",
        max_passes=3,
    )
    assert result["succeeded"] is True
    assert calls["n"] == 1

from pathlib import Path

from utils.multi_pass_retrieval import MultiPassRetriever


def test_suggest_document_from_join_failure_signal():
    r = MultiPassRetriever(kb_root="kb")
    suggested = r.suggest_document(
        question="Why did my join return 0 rows?",
        failed_answer="join returned zero rows due to businessid/businessref mismatch",
    )
    assert suggested == "domain/join_keys.md"


def test_retrieve_reads_file(tmp_path: Path):
    kb = tmp_path / "kb"
    doc = kb / "domain" / "join_keys.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("join docs", encoding="utf-8")
    r = MultiPassRetriever(kb_root=str(kb))
    assert r.retrieve("domain/join_keys.md") == "join docs"

