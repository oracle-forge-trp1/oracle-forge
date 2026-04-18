"""SchemaIntrospector import smoke test (no live DB required)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def test_schema_introspector_import() -> None:
    from utils.schema_introspector import SchemaIntrospector

    s = SchemaIntrospector()
    assert hasattr(s, "introspect")
    assert hasattr(s, "format_for_context")
