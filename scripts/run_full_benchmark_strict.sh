#!/usr/bin/env bash
# Run full DataAgentBench in strict no-leakage mode with isolated score log.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DAB_ROOT="${DAB_ROOT:-$REPO_ROOT/DataAgentBench}"
# Default OpenAI model (strong planning for harder DAB queries).
# Cost-conscious: MODEL=gpt-4.1-mini
# Cheaper baseline: MODEL=gpt-4o-mini
MODEL="${MODEL:-gpt-4.1}"
TIMEOUT="${TIMEOUT:-240}"
# Optional agent tuning (see agent/data_agent.py): ORACLE_FORGE_MAX_ITERATIONS, ORACLE_FORGE_TOOL_PREVIEW_ROWS
SCORE_LOG="${SCORE_LOG:-$REPO_ROOT/eval/score_log_strict_no_leakage.json}"
SUMMARY_MD="${SUMMARY_MD:-$REPO_ROOT/results/score_summary_strict_no_leakage.md}"
RESET_LOG="${RESET_LOG:-1}"

export ORACLE_FORGE_STRICT_NO_LEAKAGE=1

# Prefer OpenAI in strict mode (override with ORACLE_FORGE_LLM_PROVIDER=openrouter if needed)
export ORACLE_FORGE_LLM_PROVIDER="${ORACLE_FORGE_LLM_PROVIDER:-openai}"
export OPENAI_MODEL="$MODEL"

# Build OPENROUTER_MODEL: if already set in env, keep it; otherwise derive from MODEL.
# Handles google/, anthropic/, openai/ prefixes correctly.
if [[ -z "${OPENROUTER_MODEL:-}" ]]; then
  if [[ "$MODEL" == */* ]]; then
    export OPENROUTER_MODEL="$MODEL"      # already has provider/model format
  else
    export OPENROUTER_MODEL="openai/$MODEL"
  fi
else
  export OPENROUTER_MODEL="$OPENROUTER_MODEL"
fi

# Strong default tuning for hard benchmark runs.
export ORACLE_FORGE_MAX_ITERATIONS="${ORACLE_FORGE_MAX_ITERATIONS:-28}"
export ORACLE_FORGE_TOOL_PREVIEW_ROWS="${ORACLE_FORGE_TOOL_PREVIEW_ROWS:-120}"

# Discover datasets from DAB_ROOT/query_* folders (preserves on-disk case).
# Override with DATASETS="yelp stockindex bookreview stockmarket" to run a subset.
if [[ ! -d "$DAB_ROOT" ]]; then
  echo "ERROR: DAB root not found: $DAB_ROOT" >&2
  exit 1
fi
if [[ -n "${DATASETS:-}" ]]; then
  read -r -a DATASETS <<< "$DATASETS"
else
  mapfile -t DATASETS < <(
    cd "$DAB_ROOT"
    for d in query_*; do
      [[ -d "$d" ]] || continue
      echo "${d#query_}"
    done | sort
  )
fi

echo "== Oracle Forge Strict Benchmark Runner =="
echo "repo:       $REPO_ROOT"
echo "dab_root:   $DAB_ROOT"
echo "model:      $MODEL  (openrouter: $OPENROUTER_MODEL, provider: $ORACLE_FORGE_LLM_PROVIDER)"
echo "timeout:    $TIMEOUT"
echo "score_log:  $SCORE_LOG"
echo "summary_md: $SUMMARY_MD"
echo "datasets:   ${DATASETS[*]}"
echo

python3 scripts/lint_kb_no_leakage.py --strict
python3 scripts/check_kb_integrity.py --strict

if [[ "$RESET_LOG" == "1" ]]; then
  echo "[]" > "$SCORE_LOG"
  echo "Reset score log: $SCORE_LOG"
fi

# Run LLM API pre-check ONCE before the dataset loop.
# Set SKIP_PRECHECK=1 to bypass (e.g. when rate-limited but key is known good).
if [[ "${SKIP_PRECHECK:-0}" == "1" ]]; then
  echo "[strict-runner] Skipping LLM API pre-check (SKIP_PRECHECK=1)."
else
  echo "[strict-runner] Running LLM API pre-check (retry up to 3×, 45s apart)..."
  precheck_rc=1
  for attempt in 1 2 3; do
    set +e
    python3 -c "
import sys, os
sys.path.insert(0, '.')
from eval.harness import _check_llm_api
err = _check_llm_api()
if err:
    print(f'LLM API pre-check failed (attempt $attempt): {err}', file=sys.stderr)
    sys.exit(1)
print('[strict-runner] LLM API pre-check: OK')
"
    precheck_rc=$?
    set -e
    if [[ "$precheck_rc" == "0" ]]; then break; fi
    if [[ "$attempt" -lt 3 ]]; then
      echo "[strict-runner] Retrying pre-check in 45s (rate-limit back-off)..."
      sleep 45
    fi
  done
  if [[ "$precheck_rc" != "0" ]]; then
    echo "[strict-runner] FATAL: LLM API unavailable after 3 attempts. Aborting." >&2
    echo "[strict-runner] TIP: Re-run with SKIP_PRECHECK=1 if key is valid but rate-limited." >&2
    exit 1
  fi
fi

# Inter-dataset sleep — default 30s for OpenRouter free-tier rate limits.
# Override: INTER_DATASET_SLEEP=60 bash scripts/run_full_benchmark_strict.sh
INTER_DATASET_SLEEP="${INTER_DATASET_SLEEP:-30}"

for ds in "${DATASETS[@]}"; do
  echo
  echo "--- Running dataset: $ds ---"
  set +e
  python3 eval/harness.py \
    --dataset "$ds" \
    --agent-module agent.data_agent \
    --dab-root "$DAB_ROOT" \
    --timeout "$TIMEOUT" \
    --score-log "$SCORE_LOG" \
    --skip-precheck
  rc=$?
  set -e
  if [[ "$rc" != "0" ]]; then
    echo "[strict-runner] WARNING: harness failed for dataset '$ds' (exit=$rc). Continuing." >&2
  fi
  if [[ "${#DATASETS[@]}" -gt 1 && "$ds" != "${DATASETS[-1]}" ]]; then
    echo "[strict-runner] Sleeping ${INTER_DATASET_SLEEP}s before next dataset (rate-limit buffer)."
    sleep "$INTER_DATASET_SLEEP"
  fi
done

echo
python3 scripts/summarize_score_log.py \
  --score-log "$SCORE_LOG" \
  --out "$SUMMARY_MD"

echo "Done. Strict no-leakage benchmark complete."
echo "Score log: $SCORE_LOG"
echo "Summary:   $SUMMARY_MD"
