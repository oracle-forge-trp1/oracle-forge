#!/usr/bin/env bash
# Run full DataAgentBench in strict no-leakage mode with isolated score log.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DAB_ROOT="${DAB_ROOT:-$REPO_ROOT/DataAgentBench}"
# Default OpenRouter model (can still point to OpenAI-family via OpenRouter).
# Cost-conscious: MODEL=openai/gpt-4.1-mini
# Cheaper baseline: MODEL=openai/gpt-4o-mini
MODEL="${MODEL:-openai/gpt-4.1}"
TIMEOUT="${TIMEOUT:-240}"
# Optional agent tuning (see agent/data_agent.py): ORACLE_FORGE_MAX_ITERATIONS, ORACLE_FORGE_TOOL_PREVIEW_ROWS
SCORE_LOG="${SCORE_LOG:-$REPO_ROOT/eval/score_log_strict_no_leakage.json}"
SUMMARY_MD="${SUMMARY_MD:-$REPO_ROOT/results/score_summary_strict_no_leakage.md}"
RESET_LOG="${RESET_LOG:-1}"

export ORACLE_FORGE_STRICT_NO_LEAKAGE=1

# Prefer OpenRouter in strict mode (override with ORACLE_FORGE_LLM_PROVIDER=openai if needed)
export ORACLE_FORGE_LLM_PROVIDER="${ORACLE_FORGE_LLM_PROVIDER:-openrouter}"

# OpenRouter model selection.
export OPENROUTER_MODEL="$MODEL"

# Optional OpenAI compatibility when forcing openai provider.
# - If MODEL is "openai/<name>", export OPENAI_MODEL="<name>"
# - Otherwise, treat MODEL as a raw OpenAI model name.
if [[ "$MODEL" == openai/* ]]; then
  export OPENAI_MODEL="${MODEL#openai/}"
else
  export OPENAI_MODEL="$MODEL"
fi

# Discover datasets from DAB_ROOT/query_* folders (preserves on-disk case).
if [[ ! -d "$DAB_ROOT" ]]; then
  echo "ERROR: DAB root not found: $DAB_ROOT" >&2
  exit 1
fi
mapfile -t DATASETS < <(
  cd "$DAB_ROOT"
  for d in query_*; do
    [[ -d "$d" ]] || continue
    echo "${d#query_}"
  done | sort
)

echo "== Oracle Forge Strict Benchmark Runner =="
echo "repo:       $REPO_ROOT"
echo "dab_root:   $DAB_ROOT"
echo "model:      $MODEL"
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

for ds in "${DATASETS[@]}"; do
  echo
  echo "--- Running dataset: $ds ---"
  set +e
  python3 eval/harness.py \
    --dataset "$ds" \
    --agent-module agent.data_agent \
    --dab-root "$DAB_ROOT" \
    --timeout "$TIMEOUT" \
    --score-log "$SCORE_LOG"
  rc=$?
  set -e
  if [[ "$rc" != "0" ]]; then
    echo "[strict-runner] WARNING: harness failed for dataset '$ds' (exit=$rc). Continuing." >&2
  fi
done

echo
python3 scripts/summarize_score_log.py \
  --score-log "$SCORE_LOG" \
  --out "$SUMMARY_MD"

echo "Done. Strict no-leakage benchmark complete."
echo "Score log: $SCORE_LOG"
echo "Summary:   $SUMMARY_MD"
