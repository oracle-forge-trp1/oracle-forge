# Shared Utility Library

Reusable modules for the Oracle Forge data agent. Any team member can use these.

## Modules

### 1. `schema_introspector.py` — Database Schema Discovery
Connects to any DAB database type (PostgreSQL, MongoDB, SQLite, DuckDB) and returns a structured schema description. Also provides `sample_data()` to preview rows.

**Usage:**
```python
from utils.schema_introspector import SchemaIntrospector

introspector = SchemaIntrospector()

# Introspect a SQLite database (e.g., DAB stockinfo)
schema = introspector.introspect("sqlite", path="query_dataset/stockinfo_query.db")

# Introspect a DuckDB database (e.g., DAB stocktrade)
schema = introspector.introspect("duckdb", path="query_dataset/stocktrade_query.db")

# Introspect PostgreSQL (e.g., DAB CRM support)
schema = introspector.introspect("postgresql", connection_string="postgresql://user:pass@host/crm_support")

# Introspect MongoDB (e.g., DAB yelp business)
schema = introspector.introspect("mongodb", connection_string="mongodb://host:27017", db_name="yelp_db")

# Format for LLM context injection
context_md = introspector.format_for_context(schema)

# Preview sample data from a table
rows = introspector.sample_data("sqlite", "stock_info", limit=3, path="query_dataset/stockinfo_query.db")
```

**Returns:**
```python
{
    "db_type": "sqlite",
    "tables": [
        {
            "name": "stock_info",
            "columns": [
                {"name": "ticker", "type": "TEXT", "nullable": True},
                {"name": "market_category", "type": "TEXT", "nullable": True}
            ],
            "row_count": 2754
        }
    ]
}
```

### 2. `join_key_resolver.py` — Cross-Database Key Normalization
Detects and resolves format mismatches in join keys across databases. Handles DAB-specific patterns:

- **yelp**: `businessid_X` vs `businessref_X` prefix mismatch
- **crmarenapro**: Leading `#` prefix corruption, trailing whitespace
- **bookreview**: Different column names (`book_id` vs `purchase_id`)
- Generic: prefixed strings, zero-padded integers, type casting

**Usage:**
```python
from utils.join_key_resolver import JoinKeyResolver

resolver = JoinKeyResolver()

# Detect format of yelp business keys
format_info = resolver.detect_format(["businessid_1", "businessid_2", "businessid_3"])
# Returns: {"type": "prefixed_string", "prefix": "businessid_", ...}

# Normalize keys for joining
resolver.normalize("businessid_42")    # Returns: 42
resolver.normalize("businessref_42")   # Returns: 42
resolver.normalize("#001Wt00000PFj4z") # Returns: "001Wt00000PFj4z" (CRM # stripped)
resolver.normalize("  Name  ")         # Returns: "Name" (whitespace stripped)

# Join yelp MongoDB business data with DuckDB review data
merged = resolver.join(
    left_data=mongo_businesses,      # has 'business_id' = 'businessid_1'
    right_data=duckdb_reviews,       # has 'business_ref' = 'businessref_1'
    left_key="business_id",
    right_key="business_ref",
    how="inner",
    target_type="integer"
)

# Diagnose why a join returned 0 rows
diagnosis = resolver.diagnose_join_failure(left_data, right_data, "id", "id")
# Returns: format_mismatch, whitespace_issue, hash_corruption, suggestion
```

### 3. `injection_tester.py` — KB Document Validation
Automates the Karpathy injection test protocol. Supports OpenAI, Anthropic, Google, and OpenRouter as LLM providers.

**Usage:**
```python
from utils.injection_tester import InjectionTester

# Use Anthropic Claude
tester = InjectionTester(provider="anthropic")

# Or OpenAI
tester = InjectionTester(provider="openai", model="gpt-4o-mini")

# Or Google Gemini
tester = InjectionTester(provider="google")

# Or OpenRouter (access 200+ models via one API key)
tester = InjectionTester(provider="openrouter", model="anthropic/claude-sonnet-4-20250514")
# Any OpenRouter model works: google/gemini-2.0-flash-001, meta-llama/llama-3-70b, etc.

# Test a single document
result = tester.test(
    document_path="kb/domain/join_keys.md",
    question="What data quality issues affect crmarenapro join keys?",
    expected_keywords=["#", "whitespace", "strip", "25%"]
)

# Batch test all documents from a JSON definition
results = tester.test_batch("kb/domain/", "kb/domain/injection_tests/test_cases.json")

# Generate markdown report
report = tester.generate_report(results, output_path="test_report.md")
```

**Environment variables for API keys:**
- `OPENAI_API_KEY` — for OpenAI provider
- `ANTHROPIC_API_KEY` — for Anthropic provider
- `GOOGLE_API_KEY` — for Google provider
- `OPENROUTER_API_KEY` — for OpenRouter provider (uses OpenAI SDK under the hood)

## Installation

```bash
pip install -r utils/requirements.txt
```

Note: You only need to install the LLM provider package you'll use for injection testing. The core utilities (schema_introspector, join_key_resolver) work without any LLM packages.

## Running Tests

```bash
pytest utils/tests/ -v
```
