#!/bin/bash
# tune-saqmaodv-family-h.sh
# ----------------------------------------------------------------------------
# Family H cho SA-QMAODV — sweep siêu tham số adaptive để tìm optimal config
# (tương tự Family H của QMAODV nhưng cho SA-specific params).
#
# Sweep 4 params chính (tham số adaptive đặc thù của SA):
#   λ (lambda Eq.1)        ∈ {0.01, 0.05, 0.1, 0.2, 0.5}  — 5 values
#   adaptPeriod (s)        ∈ {0.5, 1.0, 2.0}              — 3 values
#   w3 (energy weight)     ∈ {0.0, 0.1, 0.2}              — 3 values
#   lowEThresh             ∈ {0.2, 0.5}                   — 2 values
# Fixed: α₀=0.5, γ=0.9, ε₀=0.3, seqNoWindow=10
#
# Total: 5 × 3 × 3 × 2 × 3 seeds tại N=15 = 270 runs ≈ 25-30 phút trên 7 cores
#
# Usage:
#   bash tune-saqmaodv-family-h.sh
#   SEEDS=5 bash tune-saqmaodv-family-h.sh   # nhiều seed hơn cho ổn định
# ----------------------------------------------------------------------------
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

NPROC=$(nproc 2>/dev/null || echo 4)
JOBS="${JOBS:-$((NPROC * 3 / 4))}"
[ "$JOBS" -lt 1 ] && JOBS=1

SEEDS="${SEEDS:-3}"
N_NODES="${N_NODES:-15}"
SIM_TIME="${SIM_TIME:-200}"

# Output
TS=$(date +%Y%m%d-%H%M%S)
OUT_DIR="$HOME/results-saqmaodv-family-h-${TS}"
JOB_DIR="$OUT_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$OUT_DIR/family_H_sa_hyper.csv"
LOG="$OUT_DIR/run.log"

# Param grids
LAMBDAS=(0.01 0.05 0.1 0.2 0.5)
PERIODS=(0.5 1.0 2.0)
W3_VALS=(0.0 0.1 0.2)
LOWE_VALS=(0.2 0.5)

# Generate jobs
JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for lam in "${LAMBDAS[@]}"; do
    for per in "${PERIODS[@]}"; do
        for w3 in "${W3_VALS[@]}"; do
            for lowe in "${LOWE_VALS[@]}"; do
                # w2 = 0.5 - w3 to keep w1+w2+w3=1 with w1=0.5
                w2=$(awk -v w3=$w3 'BEGIN{printf "%.2f", 0.5 - w3}')
                [ "$(awk -v w=$w2 'BEGIN{print (w<0)?1:0}')" = "1" ] && continue
                for seed in $(seq 1 "$SEEDS"); do
                    tag="L${lam}-P${per}-W3${w3}-LE${lowe}"
                    echo "$tag $lam $per $w2 $w3 $lowe $seed" >> "$JOB_FILE"
                done
            done
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

{
echo "==========================================="
echo " SA-QMAODV Family H Hyperparameter Sweep"
echo "==========================================="
echo " Lambda:        ${LAMBDAS[*]}"
echo " AdaptPeriod:   ${PERIODS[*]}"
echo " w3 (energy):   ${W3_VALS[*]}"
echo " lowEThresh:    ${LOWE_VALS[*]}"
echo " Seeds:         $SEEDS"
echo " N nodes:       $N_NODES"
echo " Sim time:      ${SIM_TIME}s"
echo " Parallel jobs: $JOBS"
echo " Total runs:    $TOTAL"
echo " Output:        $OUT_DIR"
echo " Started:       $(date)"
echo "==========================================="
} | tee "$LOG"

run_job() {
    local tag=$1 lam=$2 per=$3 w2=$4 w3=$5 lowe=$6 seed=$7
    local CSV="$JOB_DIR/job-${tag}-seed${seed}.csv"
    local START=$(date +%s)

    "$EXEC" \
        --protocol=SAQMAODV --maxPaths=3 \
        --numNodes="$N_NODES" --simTime="$SIM_TIME" --seed="$seed" \
        --mobility=GAUSS --enableEnergy=1 \
        --meanVelMin=15 --meanVelMax=25 --alpha=0.85 \
        --pktInterval=0.25 --pktSize=512 --numFlows=0 \
        --saAlpha0=0.5 --saGamma=0.9 --saEpsilon0=0.3 \
        --saLambda="$lam" --saSeqNoWin=10 \
        --saAdaptPeriod="$per" \
        --saLowEThresh="$lowe" \
        --saW1=0.5 --saW2="$w2" --saW3="$w3" \
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

START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ \
    | tee -a "$LOG"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

# Merge CSVs
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
echo "Done: $(date), wall=$((TOTAL_SEC/60))m"
echo ""
echo "Next: python3 scripts/plot/analyze-saqmaodv-family-h.py $MERGED"
} | tee -a "$LOG"

# Top-15 + marginal
if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(list)
for r in rows:
    cfg = r['scenario'].replace('tune-', '')
    try:
        agg[cfg].append({
            'pdr':   float(r['deliveryRatio']),
            'delay': float(r['avgDelayMs']),
        })
    except: continue

ranked = []
for cfg, vals in agg.items():
    n = len(vals)
    ranked.append({
        'cfg':   cfg,
        'pdr':   sum(v['pdr']   for v in vals)/n,
        'delay': sum(v['delay'] for v in vals)/n,
    })
ranked.sort(key=lambda x: -x['pdr'])

print()
print("=" * 80)
print(" Top-15 SA-QMAODV config theo PDR")
print("=" * 80)
print(f"{'rank':<5} {'config':<28} {'PDR(%)':>8} {'delay(ms)':>10}")
print('-' * 80)
for i, r in enumerate(ranked[:15], 1):
    print(f"{i:<5} {r['cfg']:<28} {r['pdr']:>8.2f} {r['delay']:>10.1f}")
PYEOF
fi
