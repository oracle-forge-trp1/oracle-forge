"""Tests for SchemaIntrospector utility."""

import os
import sqlite3
import tempfile

import pytest

sys_path_added = False
import sys
if not sys_path_added:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys_path_added = True

from schema_introspector import SchemaIntrospector


@pytest.fixture
def introspector():
    """Create a fresh SchemaIntrospector instance."""
    return SchemaIntrospector()


@pytest.fixture
def sample_sqlite_db():
    """Create a temporary SQLite database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            segment TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date TEXT,
            total_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)

    cursor.executemany(
        "INSERT INTO customers (customer_id, name, email, segment) VALUES (?, ?, ?, ?)",
        [
            (1, "Alice", "alice@example.com", "premium"),
            (2, "Bob", "bob@example.com", "standard"),
            (3, "Charlie", "charlie@example.com", "premium"),
        ],
    )
    cursor.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, total_amount) VALUES (?, ?, ?, ?)",
        [
            (101, 1, "2024-01-15", 99.99),
            (102, 1, "2024-02-20", 149.50),
            (103, 2, "2024-01-10", 25.00),
        ],
    )

    conn.commit()
    conn.close()

    yield db_path

    os.unlink(db_path)


class TestSchemaIntrospector:
    """Test suite for SchemaIntrospector."""

    def test_unsupported_db_type(self, introspector):
        """Reject unsupported database types."""
        with pytest.raises(ValueError, match="Unsupported database type"):
            introspector.introspect("oracle")

    def test_sqlite_introspection(self, introspector, sample_sqlite_db):
        """Introspect a SQLite database and verify schema structure."""
        schema = introspector.introspect("sqlite", path=sample_sqlite_db)

        assert schema["db_type"] == "sqlite"
        assert len(schema["tables"]) == 2

        customers = next(t for t in schema["tables"] if t["name"] == "customers")
        assert customers["row_count"] == 3
        assert len(customers["columns"]) == 4

        col_names = [c["name"] for c in customers["columns"]]
        assert "customer_id" in col_names
        assert "name" in col_names
        assert "email" in col_names

    def test_sqlite_column_types(self, introspector, sample_sqlite_db):
        """Verify column types are correctly detected."""
        schema = introspector.introspect("sqlite", path=sample_sqlite_db)

        orders = next(t for t in schema["tables"] if t["name"] == "orders")
        col_types = {c["name"]: c["type"] for c in orders["columns"]}

        assert col_types["order_id"] == "INTEGER"
        assert col_types["total_amount"] == "REAL"
        assert col_types["order_date"] == "TEXT"

    def test_format_for_context(self, introspector, sample_sqlite_db):
        """Format schema as markdown for LLM context injection."""
        schema = introspector.introspect("sqlite", path=sample_sqlite_db)
        context = introspector.format_for_context(schema)

        assert "## SQLITE Schema" in context
        assert "### customers (3 rows)" in context
        assert "`customer_id`" in context
        assert "INTEGER" in context

    def test_supported_db_types(self, introspector):
        """Verify all DAB database types are supported."""
        assert "postgresql" in introspector.SUPPORTED_DB_TYPES
        assert "sqlite" in introspector.SUPPORTED_DB_TYPES
        assert "mongodb" in introspector.SUPPORTED_DB_TYPES
        assert "duckdb" in introspector.SUPPORTED_DB_TYPES

    # --- sample_data tests ---

    def test_sample_data_sqlite(self, introspector, sample_sqlite_db):
        """Sample rows from a SQLite table."""
        rows = introspector.sample_data("sqlite", "customers", limit=2, path=sample_sqlite_db)

        assert len(rows) == 2
        assert "customer_id" in rows[0]
        assert "name" in rows[0]
        assert "email" in rows[0]

    def test_sample_data_returns_dicts(self, introspector, sample_sqlite_db):
        """Sample data returns list of dicts with column names as keys."""
        rows = introspector.sample_data("sqlite", "orders", limit=3, path=sample_sqlite_db)

        assert len(rows) == 3
        assert isinstance(rows[0], dict)
        assert rows[0]["order_id"] == 101
        assert rows[0]["total_amount"] == 99.99

    def test_sample_data_limit(self, introspector, sample_sqlite_db):
        """Limit parameter controls number of rows returned."""
        rows = introspector.sample_data("sqlite", "customers", limit=1, path=sample_sqlite_db)
        assert len(rows) == 1

    def test_sample_data_unsupported_type(self, introspector):
        """Reject unsupported database type for sample_data."""
        with pytest.raises(ValueError, match="Unsupported database type"):
            introspector.sample_data("oracle", "table")
