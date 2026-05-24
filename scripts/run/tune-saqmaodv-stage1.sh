#!/bin/bash
# tune-saqmaodv-stage1.sh
# Stage 1: Sweep param quan trọng nhất của SA-QMAODV.
#   λ (lambda)          ∈ {0.05, 0.1, 0.2, 0.5}    — sensitivity Eq.1
#   seqNoWindow (s)     ∈ {2, 5, 10}              — short time window
#   periodicAdapt (s)   ∈ {0.5, 1.0, 2.0}         — tick frequency
# Fixed: epsilon0=0.3, alpha0=0.5, gamma=0.9, N=15, scenario=default
# Total: 4 × 3 × 3 × 3 seeds = 108 runs ≈ 20 phút trên 6-core
#
# Usage: bash tune-saqmaodv-stage1.sh

set -u

# ---- Auto-detect ns-3 ----
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

NPROC=$(nproc 2>/dev/null || echo 4)
JOBS="${JOBS:-$((NPROC * 3 / 4))}"
[ "$JOBS" -lt 1 ] && JOBS=1

SEEDS="${SEEDS:-3}"
N_NODES="${N_NODES:-15}"
SIM_TIME="${SIM_TIME:-200}"

# ---- Output ----
TS=$(date +%Y%m%d-%H%M%S)
OUT_DIR="$HOME/results-saqmaodv-tune-stage1-${TS}"
JOB_DIR="$OUT_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$OUT_DIR/merged.csv"
LOG="$OUT_DIR/run.log"

# ---- Param grids ----
LAMBDAS=(0.05 0.1 0.2 0.5)
WINDOWS=(2 5 10)
PERIODS=(0.5 1.0 2.0)

# ---- Generate jobs ----
JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for lam in "${LAMBDAS[@]}"; do
    for win in "${WINDOWS[@]}"; do
        for per in "${PERIODS[@]}"; do
            for seed in $(seq 1 "$SEEDS"); do
                tag="L${lam}-W${win}-P${per}"
                echo "$tag $lam $win $per $seed" >> "$JOB_FILE"
            done
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

# ---- Print config ----
{
echo "==========================================="
echo " SA-QMAODV Stage 1 Hyperparameter Sweep"
echo "==========================================="
echo " Lambda:        ${LAMBDAS[*]}"
echo " SeqNo window:  ${WINDOWS[*]}"
echo " Adapt period:  ${PERIODS[*]}"
echo " Seeds:         $SEEDS"
echo " N nodes:       $N_NODES"
echo " Sim time:      ${SIM_TIME}s"
echo " Parallel jobs: $JOBS"
echo " Total runs:    $TOTAL"
echo " Output:        $OUT_DIR"
echo " Started:       $(date)"
echo "==========================================="
} | tee "$LOG"

# ---- Worker ----
run_job() {
    local tag=$1 lam=$2 win=$3 per=$4 seed=$5
    local CSV="$JOB_DIR/job-${tag}-seed${seed}.csv"
    local START=$(date +%s)

    "$EXEC" \
        --protocol=SAQMAODV --maxPaths=3 \
        --numNodes="$N_NODES" --simTime="$SIM_TIME" --seed="$seed" \
        --mobility=GAUSS --enableEnergy=1 \
        --meanVelMin=15 --meanVelMax=25 --alpha=0.85 \
        --pktInterval=0.25 --pktSize=512 --numFlows=0 \
        --saAlpha0=0.5 --saGamma=0.9 --saEpsilon0=0.3 \
        --saLambda="$lam" --saSeqNoWin="$win" \
        --saAdaptPeriod="$per" \
        --saLowEThresh=0.20 \
        --saW1=0.5 --saW2=0.4 --saW3=0.1 \
        --scenario="tune-$tag" \
        --csvFile="$CSV" >/dev/null 2>&1
    local rc=$?
    local DUR=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   $tag seed=$seed (${DUR}s)"
    else
        echo "FAIL $tag seed=$seed rc=$rc"
    fi
}
export -f run_job
export EXEC N_NODES SIM_TIME JOB_DIR

# ---- Run parallel ----
START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ \
    | tee -a "$LOG"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

# ---- Merge CSVs ----
FIRST_CSV=$(ls "$JOB_DIR"/job-*.csv 2>/dev/null | head -1)
if [ -n "$FIRST_CSV" ]; then
    head -1 "$FIRST_CSV" > "$MERGED"
    for f in "$JOB_DIR"/job-*.csv; do
        tail -n +2 "$f" >> "$MERGED"
    done
    ROWS=$(($(wc -l < "$MERGED") - 1))
    echo "Merged: $MERGED ($ROWS rows)" | tee -a "$LOG"
fi

{
echo ""
echo "==========================================="
echo " Done: $(date)"
echo " Total: $((TOTAL_SEC/60))m $((TOTAL_SEC%60))s"
echo " Aggregate top-K with: python3 ~/scripts/plot/aggregate-saqmaodv-tune.py $MERGED"
echo "==========================================="
} | tee -a "$LOG"

# ---- Quick top-5 summary ----
if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(list)
for r in rows:
    cfg = r['scenario'].replace('tune-', '')
    agg[cfg].append({
        'pdr':   float(r['deliveryRatio']),
        'delay': float(r['avgDelayMs']),
        'thr':   float(r['throughputMbps']),
        'over':  int(float(r['routingOverhead'])),
    })
ranked = []
for cfg, vals in agg.items():
    n = len(vals)
    ranked.append((cfg,
        sum(v['pdr']   for v in vals)/n,
        sum(v['delay'] for v in vals)/n,
        sum(v['thr']   for v in vals)/n,
        sum(v['over']  for v in vals)/n))
ranked.sort(key=lambda x: -x[1])
print()
print(f"{'rank':<5} {'config':<24} {'PDR(%)':>7} {'delay(ms)':>10} {'thr(Mbps)':>10} {'overhead':>10}")
print('-' * 70)
for i, (cfg, pdr, d, t, o) in enumerate(ranked[:10], 1):
    print(f"{i:<5} {cfg:<24} {pdr:>7.2f} {d:>10.1f} {t:>10.4f} {o:>10.0f}")
PYEOF
fi
