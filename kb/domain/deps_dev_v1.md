# deps.dev v1 Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any deps.dev query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

## Dataset Overview

Two active databases. Package metadata lives in SQLite, project information and package-to-project mappings live in DuckDB.

| Database | Format | What it contains |
|----------|--------|-----------------|
| `package_database` | SQLite | Software package metadata — licenses, versions, dependencies, advisories |
| `project_database` | DuckDB | GitHub project info and package-to-project mappings |

---

## Schema Reference

### SQLite — `package_database`

#### `packageinfo` table
| Field | Type | Notes |
|-------|------|-------|
| `System` | str | Package ecosystem e.g. `NPM`, `Maven` |
| `Name` | str | Package name |
| `Version` | str | Version string |
| `Licenses` | str | JSON-like array of licenses |
| `Links` | str | JSON-like list of links (origin, docs, source) |
| `Advisories` | str | JSON-like list of security advisories |
| `VersionInfo` | str | JSON-like object — `IsRelease`, `Ordinal` |
| `Hashes` | str | JSON-like list of file hashes |
| `DependenciesProcessed` | bool | Whether dependencies were processed |
| `DependencyError` | bool | Whether a dependency error occurred |
| `UpstreamPublishedAt` | float | Unix timestamp in milliseconds |
| `Registries` | str | JSON-like list of registries |
| `SLSAProvenance` | float | SLSA provenance level if available |
| `UpstreamIdentifiers` | str | JSON-like list of upstream identifiers |
| `Purl` | float | Package URL in purl format if available |

### DuckDB — `project_database`

#### `project_packageversion` table
| Field | Type | Notes |
|-------|------|-------|
| `System` | str | Package ecosystem |
| `Name` | str | Package name |
| `Version` | str | Package version string |
| `ProjectType` | str | e.g. `GITHUB` |
| `ProjectName` | str | Repository path in `owner/repo` format |
| `RelationProvenance` | str | Provenance of the relationship |
| `RelationType` | str | Type of relationship e.g. source repository |

#### `project_info` table
| Field | Type | Notes |
|-------|------|-------|
| `Project_Information` | str | Natural language — includes project name, GitHub stars, fork count, other details |
| `Licenses` | str | JSON-like array of licenses |
| `Description` | str | Project description |
| `Homepage` | str | Homepage URL |
| `OSSFuzz` | float | OSSFuzz status indicator |

---

## Cross-Database Join Keys

Queries require joining across all three tables in order:

```
packageinfo (SQLite)
    → match on System + Name + Version →
project_packageversion (DuckDB)
    → match on ProjectName →
project_info (DuckDB)
```

1. Get `System`, `Name`, `Version` from `packageinfo`
2. Find matching row in `project_packageversion` using all three fields
3. Take `ProjectName` from that row
4. Look up `project_info` using `ProjectName`

Do not skip steps — there is no direct link between `packageinfo` and `project_info`.

---

## Data Semantics

### GitHub Stars and Fork Count
Stars and fork count are embedded inside `project_info.Project_Information` as natural language text — they are not separate columns. Use regex to extract numeric values.

### Timestamps
`UpstreamPublishedAt` is a Unix timestamp in **milliseconds** — divide by 1000 to get seconds before converting to a date.

### JSON-like String Fields
`Licenses`, `Advisories`, `Links`, `Hashes`, `Registries` in `packageinfo` are stored as JSON-like array strings. Use `json_extract` or parse with Python before filtering.

### Security Advisories
`Advisories` field contains security advisory records. A package with an empty or null `Advisories` field has no known vulnerabilities.

---

## Query Strategy Playbook

### 1) Package-to-project attribution
1. Normalize `(System, Name, Version)` in both sources (trim/case policy).
2. Join `packageinfo` to `project_packageversion` on all three fields.
3. Join resulting `ProjectName` to `project_info`.
4. Track unmatched package versions separately.

### 2) Security and license analysis
1. Parse JSON-like `Advisories` and `Licenses` fields into arrays.
2. Distinguish null, empty array, and malformed payloads.
3. Aggregate at package-version level before rolling up to project level.

### 3) Freshness/time-window analysis
1. Convert `UpstreamPublishedAt` from milliseconds to timestamp.
2. Validate converted year range to catch unit mistakes.
3. Use publication windows only after conversion checks pass.

---

## Common Pitfalls

- Joining by `Name` only and ignoring `System` (ecosystem collisions).
- Dropping `Version` in joins and creating false many-to-many matches.
- Treating JSON-like text fields as plain strings for exact equality filters.
- Forgetting ms→s conversion for `UpstreamPublishedAt`.
- Aggregating project metrics without first deduplicating package-version rows.

---

## Validation Checklist

- Key completeness: null-rate for `System`, `Name`, `Version` in both joined tables.
- Join quality: matched vs unmatched package-version counts.
- Timestamp sanity: min/max converted dates are plausible.
- Advisory parsing: malformed JSON-like row count reported.
- Rollup sanity: verify project-level totals against sampled package-version detail.

---

## Leakage-Safe Policy

- Keep only schema/join/parsing methodology and quality checks.
- Do not encode expected leaderboard outcomes, per-query final numbers, or canned answers.
- Prefer robust procedural guidance over benchmark-specific heuristics.
