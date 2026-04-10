"""
Schema Introspector — Multi-Database Schema Discovery

Connects to any DAB database type (PostgreSQL, MongoDB, SQLite, DuckDB)
and returns a unified, structured schema description. This is used by
the agent's context layer to understand available tables and columns
before generating queries.

Also provides sample_data() to preview rows from any table — useful for
the agent to understand data formats before writing queries.
"""

import sqlite3
from typing import Any


class SchemaIntrospector:
    """Discovers and returns structured schema information from any supported database."""

    SUPPORTED_DB_TYPES = ("postgresql", "sqlite", "mongodb", "duckdb")

    def introspect(self, db_type: str, **connection_params) -> dict[str, Any]:
        """
        Introspect a database and return its schema.

        Args:
            db_type: One of 'postgresql', 'sqlite', 'mongodb', 'duckdb'
            **connection_params: Database-specific connection parameters:
                - postgresql: connection_string="postgresql://user:pass@host/db"
                - sqlite: path="/path/to/database.db"
                - mongodb: connection_string="mongodb://host:27017/db", db_name="mydb"
                - duckdb: path="/path/to/database.duckdb"

        Returns:
            Structured dict with db_type, tables/collections, columns, types, row counts.
        """
        db_type = db_type.lower()
        if db_type not in self.SUPPORTED_DB_TYPES:
            raise ValueError(
                f"Unsupported database type: {db_type}. "
                f"Supported: {self.SUPPORTED_DB_TYPES}"
            )

        method = getattr(self, f"_introspect_{db_type}")
        return method(**connection_params)

    def sample_data(
        self, db_type: str, table_name: str, limit: int = 5, **connection_params
    ) -> list[dict]:
        """
        Retrieve sample rows from a table/collection for data preview.

        Useful for the agent to understand actual data formats, key patterns,
        and field content before writing queries.

        Args:
            db_type: One of 'postgresql', 'sqlite', 'mongodb', 'duckdb'
            table_name: Name of the table or collection
            limit: Number of rows to return (default 5)
            **connection_params: Same as introspect()

        Returns:
            List of dicts, one per row.
        """
        db_type = db_type.lower()
        if db_type not in self.SUPPORTED_DB_TYPES:
            raise ValueError(
                f"Unsupported database type: {db_type}. "
                f"Supported: {self.SUPPORTED_DB_TYPES}"
            )

        method = getattr(self, f"_sample_{db_type}")
        return method(table_name, limit, **connection_params)

    # --- PostgreSQL ---

    def _introspect_postgresql(self, connection_string: str) -> dict[str, Any]:
        """Introspect a PostgreSQL database using information_schema."""
        import psycopg2

        conn = psycopg2.connect(connection_string)
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            table_names = [row[0] for row in cursor.fetchall()]

            tables = []
            for table_name in table_names:
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))

                columns = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                        "default": row[3],
                    }
                    for row in cursor.fetchall()
                ]

                # Use parameterized identifier quoting via psycopg2
                cursor.execute(
                    "SELECT COUNT(*) FROM {}".format(
                        psycopg2.extensions.quote_ident(table_name, conn)
                    )
                )
                row_count = cursor.fetchone()[0]

                tables.append({
                    "name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                })

            return {"db_type": "postgresql", "tables": tables}
        finally:
            conn.close()

    def _sample_postgresql(
        self, table_name: str, limit: int, connection_string: str
    ) -> list[dict]:
        import psycopg2

        conn = psycopg2.connect(connection_string)
        try:
            cursor = conn.cursor()
            quoted = psycopg2.extensions.quote_ident(table_name, conn)
            cursor.execute(f"SELECT * FROM {quoted} LIMIT %s", (limit,))
            col_names = [desc[0] for desc in cursor.description]
            return [dict(zip(col_names, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    # --- SQLite ---

    def _introspect_sqlite(self, path: str) -> dict[str, Any]:
        """Introspect a SQLite database using sqlite_master and pragma."""
        conn = sqlite3.connect(path)
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            table_names = [row[0] for row in cursor.fetchall()]

            tables = []
            for table_name in table_names:
                cursor.execute(f'PRAGMA table_info("{table_name}")')
                columns = [
                    {
                        "name": row[1],
                        "type": row[2] or "TEXT",
                        "nullable": not row[3],  # notnull flag
                        "default": row[4],
                    }
                    for row in cursor.fetchall()
                ]

                cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                row_count = cursor.fetchone()[0]

                tables.append({
                    "name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                })

            return {"db_type": "sqlite", "tables": tables}
        finally:
            conn.close()

    def _sample_sqlite(self, table_name: str, limit: int, path: str) -> list[dict]:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # --- MongoDB ---

    def _introspect_mongodb(
        self, connection_string: str, db_name: str | None = None
    ) -> dict[str, Any]:
        """
        Introspect a MongoDB database by sampling documents from each collection
        to infer the schema. Samples 100 docs to better capture sparse fields.
        """
        from pymongo import MongoClient

        client = MongoClient(connection_string)
        try:
            if db_name is None:
                from urllib.parse import urlparse
                parsed = urlparse(connection_string)
                db_name = parsed.path.lstrip("/") or "test"

            db = client[db_name]
            collection_names = db.list_collection_names()

            collections = []
            for coll_name in sorted(collection_names):
                coll = db[coll_name]
                doc_count = coll.estimated_document_count()

                # Sample more documents to catch sparse/polymorphic fields
                sample_size = min(100, doc_count) if doc_count > 0 else 0
                sample = list(coll.find().limit(sample_size))

                # Union all field names across samples
                fields = {}
                for doc in sample:
                    self._extract_mongo_fields(doc, fields, prefix="")

                columns = [
                    {"name": name, "type": dtype, "nullable": True, "default": None}
                    for name, dtype in sorted(fields.items())
                ]

                collections.append({
                    "name": coll_name,
                    "columns": columns,
                    "row_count": doc_count,
                })

            return {"db_type": "mongodb", "tables": collections}
        finally:
            client.close()

    def _extract_mongo_fields(
        self, doc: dict, fields: dict, prefix: str
    ) -> None:
        """Recursively extract field names and types from a MongoDB document."""
        for key, value in doc.items():
            full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            value_type = type(value).__name__
            if full_key not in fields:
                fields[full_key] = value_type
            # For nested dicts, also extract sub-fields (one level deep)
            if isinstance(value, dict) and not prefix:
                self._extract_mongo_fields(value, fields, prefix=key)

    def _sample_mongodb(
        self, table_name: str, limit: int,
        connection_string: str, db_name: str | None = None
    ) -> list[dict]:
        from pymongo import MongoClient

        client = MongoClient(connection_string)
        try:
            if db_name is None:
                from urllib.parse import urlparse
                parsed = urlparse(connection_string)
                db_name = parsed.path.lstrip("/") or "test"

            db = client[db_name]
            docs = list(db[table_name].find().limit(limit))
            # Convert ObjectId to string for serialization
            for doc in docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            return docs
        finally:
            client.close()

    # --- DuckDB ---

    def _introspect_duckdb(self, path: str) -> dict[str, Any]:
        """Introspect a DuckDB database using information_schema."""
        import duckdb

        conn = duckdb.connect(path, read_only=True)
        try:
            tables_result = conn.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_name
            """).fetchall()
            table_names = [row[0] for row in tables_result]

            tables = []
            for table_name in table_names:
                cols_result = conn.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'main' AND table_name = ?
                    ORDER BY ordinal_position
                """, [table_name]).fetchall()

                columns = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                        "default": None,
                    }
                    for row in cols_result
                ]

                row_count = conn.execute(
                    f'SELECT COUNT(*) FROM "{table_name}"'
                ).fetchone()[0]

                tables.append({
                    "name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                })

            return {"db_type": "duckdb", "tables": tables}
        finally:
            conn.close()

    def _sample_duckdb(self, table_name: str, limit: int, path: str) -> list[dict]:
        import duckdb

        conn = duckdb.connect(path, read_only=True)
        try:
            result = conn.execute(
                f'SELECT * FROM "{table_name}" LIMIT ?', [limit]
            ).fetchall()
            col_names = [desc[0] for desc in conn.description]
            return [dict(zip(col_names, row)) for row in result]
        finally:
            conn.close()

    # --- Formatting ---

    def format_for_context(self, schema: dict[str, Any]) -> str:
        """
        Format a schema dict as a concise markdown string suitable for
        injection into an LLM context window.
        """
        lines = [f"## {schema['db_type'].upper()} Schema\n"]
        for table in schema["tables"]:
            lines.append(f"### {table['name']} ({table['row_count']} rows)")
            for col in table["columns"]:
                nullable = "nullable" if col.get("nullable") else "NOT NULL"
                lines.append(f"- `{col['name']}` ({col['type']}, {nullable})")
            lines.append("")
        return "\n".join(lines)
