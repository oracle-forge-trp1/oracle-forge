# GitHub Repos Dataset — Domain Knowledge

This document is injected into the agent's Domain Knowledge context layer before any GitHub Repos query is answered. All facts here are specific to this dataset — do not assume they apply to other DAB datasets.

---

## Dataset Overview

Two active databases. Repository metadata lives in SQLite, repository artifacts (files, commits, contents) live in DuckDB.

| Database | Format | What it contains |
|----------|--------|-----------------|
| `metadata_database` | SQLite | Languages, licenses, watch counts per repo |
| `artifacts_database` | DuckDB | File contents, commits, file-level metadata |

---

## Schema Reference

### SQLite — `metadata_database`

#### `languages` table
| Field | Type | Notes |
|-------|------|-------|
| `repo_name` | str | `owner/repo` format |
| `language_description` | str | Natural language — may list multiple languages |

#### `licenses` table
| Field | Type | Notes |
|-------|------|-------|
| `repo_name` | str | `owner/repo` format |
| `license` | str | e.g. `apache-2.0`, `mit` |

#### `repos` table
| Field | Type | Notes |
|-------|------|-------|
| `repo_name` | str | `owner/repo` format |
| `watch_count` | int | Number of watchers |

### DuckDB — `artifacts_database`

#### `contents` table
| Field | Type | Notes |
|-------|------|-------|
| `id` | str | File blob identifier |
| `content` | str | File content — may be truncated for large or binary files |
| `sample_repo_name` | str | `owner/repo` format |
| `sample_ref` | str | Branch or commit SHA |
| `sample_path` | str | File path within repo |
| `sample_symlink_target` | str | Symlink target if applicable |
| `repo_data_description` | str | Natural language metadata — derived from size, binary, copies, mode |

#### `commits` table
| Field | Type | Notes |
|-------|------|-------|
| `commit` | str | Commit SHA |
| `tree` | str | Tree SHA |
| `parent` | str | JSON-like parent commit SHAs |
| `author` | str | JSON-like object — name, email, timestamp |
| `committer` | str | JSON-like object — name, email, timestamp |
| `subject` | str | Short commit message subject line |
| `message` | str | Full commit message |
| `trailer` | str | JSON-like additional metadata |
| `difference` | str | JSON-like file changes in this commit |
| `difference_truncated` | bool | Whether difference data is truncated |
| `repo_name` | str | `owner/repo` format |
| `encoding` | str | Encoding format if applicable |

#### `files` table
| Field | Type | Notes |
|-------|------|-------|
| `repo_name` | str | `owner/repo` format |
| `ref` | str | Branch or commit SHA |
| `path` | str | File path within repo |
| `mode` | int | File mode (normal, executable, symlink) |
| `id` | str | File blob identifier — links to `contents.id` |
| `symlink_target` | str | Symlink target if applicable |

---

## Cross-Database Join Keys

- Across all tables: `repo_name` (SQLite) = `sample_repo_name` (DuckDB contents) = `repo_name` (DuckDB commits/files)
- `files.id` = `contents.id` to get file content from file metadata

---

## Data Semantics

### Primary Language Detection
`languages.language_description` lists multiple languages per repo in natural language. To find the primary language, compare the relative byte count across languages mentioned — the one with the highest byte count is the primary language.

### File Content May Be Truncated
`contents.content` may contain placeholders for large or binary files. Do not assume full file content is always available.

### Commit Author vs Committer
`author` and `committer` are JSON-like strings. Parse to extract name, email, or timestamp. Author = who wrote the code, committer = who applied the commit (may differ in rebased or merged commits).

### repo_data_description
`contents.repo_data_description` is a natural language field derived from file attributes (size, binary, copies, mode). Use substring or regex matching to filter on file attributes — not direct field access.

---

## Query Strategy Playbook

### 1) Repository-level metadata + artifact joins
1. Start from a canonical repo set (`owner/repo`) from `repos` or `licenses`.
2. Join metadata tables on `repo_name`.
3. Join artifact tables via `repo_name`/`sample_repo_name`.
4. Use `files.id -> contents.id` only when file-level content is required.

### 2) Commit activity analysis
1. Parse `author` / `committer` JSON-like fields into structured columns.
2. Distinguish commit author time from committer time if temporal metrics are requested.
3. Guard against truncated diff payloads (`difference_truncated`).

### 3) Code-content filtering
1. Filter candidate files by `path`/`mode` before loading content.
2. Exclude known binary/truncated content markers from semantic analyses.
3. Keep per-repo caps to avoid bias from very large repositories.

---

## Common Pitfalls

- Joining metadata and artifacts without normalizing repo key format.
- Counting files after joining contents in a way that duplicates rows.
- Treating truncated `content` as complete source text.
- Confusing `watch_count` semantics with stars/forks.
- Ignoring `difference_truncated` and over-trusting commit-level change statistics.

---

## Validation Checklist

- Key alignment: percentage of repos present in both metadata and artifacts sources.
- Join cardinality: verify row count before/after each join stage.
- Content quality: share of rows flagged as truncated/binary-like.
- Commit payload quality: rate of `difference_truncated = true`.
- Metric sanity: sample-check top-ranked repos/files against raw rows.

---

## Leakage-Safe Policy

- No query-specific expected outputs or hardcoded benchmark answers.
- Keep guidance reusable across arbitrary repository-analysis questions.
- Store only durable tactics: key normalization, join sequencing, parsing, and validation.
