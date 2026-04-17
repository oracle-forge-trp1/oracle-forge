#!/usr/bin/env bash
# Run full DataAgentBench in strict no-leakage mode with isolated score log.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DAB_ROOT="${DAB_ROOT:-$REPO_ROOT/DataAgentBench}"
MODEL="${MODEL:-openai/gpt-4o-mini}"
TIMEOUT="${TIMEOUT:-240}"
SCORE_LOG="${SCORE_LOG:-$REPO_ROOT/eval/score_log_strict_no_leakage.json}"
SUMMARY_MD="${SUMMARY_MD:-$REPO_ROOT/results/score_summary_strict_no_leakage.md}"
RESET_LOG="${RESET_LOG:-1}"

DATASETS=(
  agnews
  bookreview
  crmarenapro
  DEPS_DEV_V1
  GITHUB_REPOS
  googlelocal
  music_brainz_20k
  PANCANCER_ATLAS
  PATENTS
  stockindex
  stockmarket
  yelp
)

export ORACLE_FORGE_STRICT_NO_LEAKAGE=1
export OPENROUTER_MODEL="$MODEL"

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
  python3 eval/harness.py \
    --dataset "$ds" \
    --agent-module agent.data_agent \
    --dab-root "$DAB_ROOT" \
    --timeout "$TIMEOUT" \
    --score-log "$SCORE_LOG"
done

echo
python3 scripts/summarize_score_log.py \
  --score-log "$SCORE_LOG" \
  --out "$SUMMARY_MD"

echo "Done. Strict no-leakage benchmark complete."
echo "Score log: $SCORE_LOG"
echo "Summary:   $SUMMARY_MD"
