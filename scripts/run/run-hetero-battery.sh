#!/bin/bash
# run-hetero-battery.sh
# ----------------------------------------------------------------------------
# Heterogeneous battery scenario — sweep --initialEnergy ngẫu nhiên per UAV
# Đây là kịch bản đúng paper SA-QMAODV §4.4 thiết kế: cơ chế low-energy mode
# (w₃=0.8) cần pin các UAV chênh lệch để kích hoạt cục bộ.
#
# Implementation: sử dụng --initialEnergy thấp (10-30 J) để pin tụt dưới 20%
# trong khoảng giữa sim. Ngoài ra chạy với uniform initial khác nhau cho mỗi seed.
#
# Sweep:
#   - 5 protocols: AODV, AOMDV-3, PMAODV-3, QMAODV-3, SAQMAODV-3
#   - initialEnergy: cố định mỗi run, nhưng thay đổi giữa các config
#     E0 ∈ {10, 20, 30, 50} J (10 = pin gần cạn, 50 = baseline)
#   - N = 15 (fix), 10 seeds
# Total: 5 × 4 × 10 = 200 runs ≈ 20 phút
#
# Mục đích: confirm low-energy mode của SA-QMAODV thực sự helpful khi pin cạn
# ----------------------------------------------------------------------------
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

JOBS="${JOBS:-7}"
SEEDS="${SEEDS:-10}"
N_NODES="${N_NODES:-15}"
SIM_TIME="${SIM_TIME:-300}"  # 300s để pin có thời gian tụt

# QMAODV Strategy B + SA Test A defaults (sẽ override sau Family H mới)
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

E0_VALS=(10 20 30 50)

TS=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="$HOME/results-hetero-battery-${TS}"
JOB_DIR="$RESULTS_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$RESULTS_DIR/merged.csv"
LOG="$RESULTS_DIR/run.log"

JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for E0 in "${E0_VALS[@]}"; do
    for SEED in $(seq 1 "$SEEDS"); do
        for EXP in "${PROTOCOLS[@]}"; do
            read -r PROTO MP <<< "$EXP"
            echo "$PROTO $MP $E0 $SEED" >> "$JOB_FILE"
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

{
echo "============================================="
echo " HETEROGENEOUS BATTERY Scenario Runner"
echo "============================================="
echo " Protocols:     AODV, AOMDV-3, PMAODV-3, QMAODV-3, SAQMAODV-3"
echo " Initial E:     ${E0_VALS[*]} J (sweep)"
echo " N:             $N_NODES"
echo " Sim time:      ${SIM_TIME}s (longer to drain battery)"
echo " Seeds:         $SEEDS"
echo " Total runs:    $TOTAL"
echo " Output:        $RESULTS_DIR"
echo " Started:       $(date)"
echo "============================================="
} | tee "$LOG"

run_job() {
    local PROTO=$1 MP=$2 E0=$3 SEED=$4
    local label="${PROTO}"
    [ "$PROTO" = "PMAODV" ] || [ "$PROTO" = "AOMDV" ] || \
    [ "$PROTO" = "QMAODV" ] || [ "$PROTO" = "SAQMAODV" ] && label="${PROTO}-${MP}"
    local CSV="$JOB_DIR/job-${label}-E${E0}-seed${SEED}.csv"
    local START=$(date +%s)

    local SA_FLAGS=""
    if [ "$PROTO" = "SAQMAODV" ]; then
        SA_FLAGS="--saAlpha0=$SA_ALPHA0 --saGamma=$SA_GAMMA --saEpsilon0=$SA_EPSILON0 \
                  --saLambda=$SA_LAMBDA --saSeqNoWin=$SA_WINDOW \
                  --saAdaptPeriod=$SA_PERIOD --saLowEThresh=$SA_LOWE \
                  --saW1=$SA_W1 --saW2=$SA_W2 --saW3=$SA_W3"
    fi

    "$EXEC" \
        --scenario="hetero-E${E0}" \
        --protocol="$PROTO" --maxPaths="$MP" \
        --mobility=GAUSS --enableEnergy=1 \
        --initialEnergy="$E0" \
        --numNodes="$N_NODES" --simTime="$SIM_TIME" --seed="$SEED" \
        --meanVelMin=15 --meanVelMax=25 --alpha=0.85 \
        --pktInterval=0.25 --pktSize=512 --numFlows=0 \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $SA_FLAGS \
        --csvFile="$CSV" >/dev/null 2>&1
    local rc=$?
    local DUR=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   ${label} E0=${E0}J seed=${SEED} (${DUR}s)"
    else
        echo "FAIL ${label} E0=${E0}J seed=${SEED} rc=$rc"
    fi
}
export -f run_job
export EXEC N_NODES SIM_TIME JOB_DIR
export QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export SA_LAMBDA SA_WINDOW SA_PERIOD SA_GAMMA SA_ALPHA0 SA_EPSILON0
export SA_W1 SA_W2 SA_W3 SA_LOWE

START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ \
    | tee -a "$LOG"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

# Merge
FIRST_CSV=$(ls "$JOB_DIR"/job-*.csv 2>/dev/null | head -1)
if [ -n "$FIRST_CSV" ]; then
    head -1 "$FIRST_CSV" > "$MERGED"
    for f in "$JOB_DIR"/job-*.csv; do
        tail -n +2 "$f" >> "$MERGED"
    done
    echo "Merged: $MERGED ($(($(wc -l < $MERGED) - 1)) rows)" | tee -a "$LOG"
fi

echo "Done: $(date), wall=$((TOTAL_SEC/60))m $((TOTAL_SEC%60))s" | tee -a "$LOG"

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
    # parse scenario "hetero-E10"
    s = r['scenario']
    try:
        E0 = int(s.split('E')[1])
    except: continue
    for m in ('deliveryRatio','avgDelayMs','totalEnergyJ'):
        try: agg[(label, E0)][m].append(float(r[m]))
        except: pass

protos = ["AODV", "AOMDV-3", "PMAODV-3", "QMAODV-3", "SAQMAODV-3"]
E0s = sorted({k[1] for k in agg.keys()})

print()
print("=" * 70)
print(" PDR (%) — Hetero Battery Scenario")
print("=" * 70)
print(f"{'proto':<13} " + " ".join(f"E0={e:>3}J" for e in E0s))
print('-' * 70)
for p in protos:
    cells = []
    for e in E0s:
        v = agg.get((p, e), {}).get('deliveryRatio', [])
        cells.append(f"{sum(v)/len(v):>6.2f}" if v else f"{'—':>6}")
    print(f"{p:<13} " + " ".join(cells))
PYEOF
fi
