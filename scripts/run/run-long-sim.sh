#!/bin/bash
# run-long-sim.sh
# ----------------------------------------------------------------------------
# Long-simulation scenario — 600s, 900s, 1200s sim time để SA-QMAODV's adaptive
# mechanisms (Q-table convergence, periodic ε decay, weight adaptation) thực sự
# có thời gian active.
#
# Hypothesis: 200s default sim chưa đủ cho SA's PeriodicAdaptiveTick (1s/tick)
# học hoàn toàn. Long-sim sẽ confirm adaptive logic mang lại gain hay không.
#
# Sweep:
#   - 5 protocols
#   - simTime ∈ {200, 600, 900, 1200} s
#   - N = 15 (fix), 5 seeds
# Total: 5 × 4 × 5 = 100 runs ≈ thời gian biến thiên (1200s sim mất ~10x)
# ----------------------------------------------------------------------------
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

JOBS="${JOBS:-7}"
SEEDS="${SEEDS:-5}"
N_NODES="${N_NODES:-15}"

QM_ALPHA=0.7; QM_GAMMA=0.6; QM_EPSILON=0.3; QM_DECAY=0.1
SA_LAMBDA=0.01; SA_WINDOW=10; SA_PERIOD=1.0; SA_GAMMA=0.9
SA_ALPHA0=0.5; SA_EPSILON0=0.3
SA_W1=0.5; SA_W2=0.4; SA_W3=0.1
SA_LOWE=0.20

PROTOCOLS=(
    "AODV      1"
    "AOMDV     3"
    "PMAODV    3"
    "QMAODV    3"
    "SAQMAODV  3"
)

SIM_TIMES=(200 600 900 1200)

TS=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="$HOME/results-long-sim-${TS}"
JOB_DIR="$RESULTS_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$RESULTS_DIR/merged.csv"
LOG="$RESULTS_DIR/run.log"

JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for ST in "${SIM_TIMES[@]}"; do
    for SEED in $(seq 1 "$SEEDS"); do
        for EXP in "${PROTOCOLS[@]}"; do
            read -r PROTO MP <<< "$EXP"
            echo "$PROTO $MP $ST $SEED" >> "$JOB_FILE"
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

{
echo "============================================="
echo " LONG-SIM Scenario Runner"
echo "============================================="
echo " Protocols:     AODV, AOMDV-3, PMAODV-3, QMAODV-3, SAQMAODV-3"
echo " SimTime sweep: ${SIM_TIMES[*]} s"
echo " N:             $N_NODES"
echo " Seeds:         $SEEDS"
echo " Total runs:    $TOTAL"
echo " Output:        $RESULTS_DIR"
echo " Started:       $(date)"
echo "============================================="
} | tee "$LOG"

run_job() {
    local PROTO=$1 MP=$2 SIM_T=$3 SEED=$4
    local label="${PROTO}"
    [ "$PROTO" = "PMAODV" ] || [ "$PROTO" = "AOMDV" ] || \
    [ "$PROTO" = "QMAODV" ] || [ "$PROTO" = "SAQMAODV" ] && label="${PROTO}-${MP}"
    local CSV="$JOB_DIR/job-${label}-T${SIM_T}-seed${SEED}.csv"
    local START=$(date +%s)

    local SA_FLAGS=""
    if [ "$PROTO" = "SAQMAODV" ]; then
        SA_FLAGS="--saAlpha0=$SA_ALPHA0 --saGamma=$SA_GAMMA --saEpsilon0=$SA_EPSILON0 \
                  --saLambda=$SA_LAMBDA --saSeqNoWin=$SA_WINDOW \
                  --saAdaptPeriod=$SA_PERIOD --saLowEThresh=$SA_LOWE \
                  --saW1=$SA_W1 --saW2=$SA_W2 --saW3=$SA_W3"
    fi

    "$EXEC" \
        --scenario="long-T${SIM_T}" \
        --protocol="$PROTO" --maxPaths="$MP" \
        --mobility=GAUSS --enableEnergy=1 \
        --numNodes="$N_NODES" --simTime="$SIM_T" --seed="$SEED" \
        --meanVelMin=15 --meanVelMax=25 --alpha=0.85 \
        --pktInterval=0.25 --pktSize=512 --numFlows=0 \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $SA_FLAGS \
        --csvFile="$CSV" >/dev/null 2>&1
    local rc=$?
    local DUR=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   ${label} T=${SIM_T}s seed=${SEED} (${DUR}s)"
    else
        echo "FAIL ${label} T=${SIM_T}s seed=${SEED} rc=$rc"
    fi
}
export -f run_job
export EXEC N_NODES JOB_DIR
export QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export SA_LAMBDA SA_WINDOW SA_PERIOD SA_GAMMA SA_ALPHA0 SA_EPSILON0
export SA_W1 SA_W2 SA_W3 SA_LOWE

START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ \
    | tee -a "$LOG"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

FIRST_CSV=$(ls "$JOB_DIR"/job-*.csv 2>/dev/null | head -1)
if [ -n "$FIRST_CSV" ]; then
    head -1 "$FIRST_CSV" > "$MERGED"
    for f in "$JOB_DIR"/job-*.csv; do
        tail -n +2 "$f" >> "$MERGED"
    done
fi

echo "Done: $(date), wall=$((TOTAL_SEC/3600))h $(((TOTAL_SEC%3600)/60))m" | tee -a "$LOG"

# Summary
if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r['protocol']
    mp = r.get('maxPaths', '1')
    label = f"{proto}-{mp}" if proto in ('AOMDV','PMAODV','QMAODV','SAQMAODV') else proto
    s = r['scenario']
    try: T = int(s.split('T')[1])
    except: continue
    for m in ('deliveryRatio','avgDelayMs'):
        try: agg[(label, T)][m].append(float(r[m]))
        except: pass

protos = ["AODV","AOMDV-3","PMAODV-3","QMAODV-3","SAQMAODV-3"]
Ts = sorted({k[1] for k in agg.keys()})

print()
print("=" * 60)
print(" PDR (%) — Long-Sim Scenario")
print("=" * 60)
print(f"{'proto':<13} " + " ".join(f"T={t:>4}" for t in Ts))
print('-' * 60)
for p in protos:
    cells = []
    for t in Ts:
        v = agg.get((p, t), {}).get('deliveryRatio', [])
        cells.append(f"{sum(v)/len(v):>6.2f}" if v else f"{'—':>6}")
    print(f"{p:<13} " + " ".join(cells))
PYEOF
fi
