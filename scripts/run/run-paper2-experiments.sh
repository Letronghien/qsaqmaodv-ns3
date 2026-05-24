#!/bin/bash
# run-paper2-experiments.sh
# ----------------------------------------------------------------------------
# Paper 2 — QS-QMAODV Experiment Runner
#
# Families:
#   W  — w4 weight sensitivity (key: confirm queue term helps)
#   L  — traffic load sweep (KEY scenario: high-load congestion)
#   N  — node density
#   S  — mobility speed
#   E  — heterogeneous battery
#
# Protocols: AODV, AOMDV-3, QMAODV-3, SAQMAODV-3, QSAQMAODV-3
#
# Usage:
#   FAMILIES="W L N S E" SEEDS=10 JOBS=8 bash run-paper2-experiments.sh
# ----------------------------------------------------------------------------
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found in $NS3_DIR/build"; exit 1; }

JOBS="${JOBS:-7}"
SEEDS="${SEEDS:-10}"
FAMILIES="${FAMILIES:-W L N S E}"

# -------- Shared hyper-parameters -------------------------------------------
QM_ALPHA=0.7;   QM_GAMMA=0.6;  QM_EPSILON=0.3; QM_DECAY=0.1

SA_ALPHA0=0.5;  SA_GAMMA=0.9;  SA_EPSILON0=0.3
SA_LAMBDA=0.01; SA_WINDOW=10;  SA_PERIOD=1.0;   SA_LOWE=0.20
SA_W1=0.4;      SA_W2=0.3;     SA_W3=0.1

# QS-QMAODV default w4 and queue thresholds
QS_W4="${QS_W4:-0.2}"
QS_Q_HIGH="${QS_Q_HIGH:-0.7}"
QS_Q_LOW="${QS_Q_LOW:-0.3}"

# -------- Results dir -------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="$HOME/results-paper2-${TS}"
JOB_DIR="$RESULTS_DIR/jobs"
mkdir -p "$JOB_DIR"
LOG="$RESULTS_DIR/run.log"

echo "======================================================" | tee "$LOG"
echo " QS-QMAODV Paper 2 — Experiment Runner"              | tee -a "$LOG"
echo "======================================================" | tee -a "$LOG"
echo " Families:  $FAMILIES"                               | tee -a "$LOG"
echo " Seeds:     $SEEDS"                                  | tee -a "$LOG"
echo " Jobs:      $JOBS"                                   | tee -a "$LOG"
echo " QS w4:     $QS_W4  q_high=$QS_Q_HIGH  q_low=$QS_Q_LOW" | tee -a "$LOG"
echo " Output:    $RESULTS_DIR"                            | tee -a "$LOG"
echo " Started:   $(date)"                                 | tee -a "$LOG"
echo "======================================================" | tee -a "$LOG"

PROTOCOLS=(
    "AODV       1"
    "AOMDV      3"
    "QMAODV     3"
    "SAQMAODV   3"
    "QSAQMAODV  3"
)

JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"

# W family — w4 sensitivity (QSAQMAODV vs SAQMAODV at high load)
if echo "$FAMILIES" | grep -qw W; then
    for W4 in 0.0 0.1 0.2 0.3 0.4; do
        for SEED in $(seq 1 "$SEEDS"); do
            # Compare QSAQMAODV with varying w4 against SAQMAODV baseline
            echo "W QSAQMAODV 3 $SEED numNodes=15 simTime=200 speed=20 pktInterval=0.1 w4=$W4" >> "$JOB_FILE"
            echo "W SAQMAODV  3 $SEED numNodes=15 simTime=200 speed=20 pktInterval=0.1 w4=0" >> "$JOB_FILE"
        done
    done
fi

# L family — traffic load (KEY scenario)
if echo "$FAMILIES" | grep -qw L; then
    for PKT in 1.0 0.5 0.25 0.1 0.05; do
        for SEED in $(seq 1 "$SEEDS"); do
            for EXP in "${PROTOCOLS[@]}"; do
                read -r PROTO MP <<< "$EXP"
                echo "L $PROTO $MP $SEED numNodes=15 simTime=200 speed=20 pktInterval=$PKT" >> "$JOB_FILE"
            done
        done
    done
fi

# N family — node density
if echo "$FAMILIES" | grep -qw N; then
    for N in 5 10 15 20 25 30; do
        for SEED in $(seq 1 "$SEEDS"); do
            for EXP in "${PROTOCOLS[@]}"; do
                read -r PROTO MP <<< "$EXP"
                echo "N $PROTO $MP $SEED numNodes=$N simTime=200 speed=20 pktInterval=0.1" >> "$JOB_FILE"
            done
        done
    done
fi

# S family — speed
if echo "$FAMILIES" | grep -qw S; then
    for SPEED in 5 15 25 50; do
        for SEED in $(seq 1 "$SEEDS"); do
            for EXP in "${PROTOCOLS[@]}"; do
                read -r PROTO MP <<< "$EXP"
                echo "S $PROTO $MP $SEED numNodes=15 simTime=200 speed=$SPEED pktInterval=0.1" >> "$JOB_FILE"
            done
        done
    done
fi

# E family — energy
if echo "$FAMILIES" | grep -qw E; then
    for E0 in 10 20 30 50; do
        for SEED in $(seq 1 "$SEEDS"); do
            for EXP in "${PROTOCOLS[@]}"; do
                read -r PROTO MP <<< "$EXP"
                echo "E $PROTO $MP $SEED numNodes=15 simTime=200 speed=20 pktInterval=0.25 e0=$E0" >> "$JOB_FILE"
            done
        done
    done
fi

TOTAL=$(wc -l < "$JOB_FILE")
echo " Total jobs: $TOTAL" | tee -a "$LOG"

# -------- Job runner --------------------------------------------------------
run_job() {
    local FAMILY=$1 PROTO=$2 MP=$3 SEED=$4
    shift 4
    local EXTRA_ARGS="$*"

    local NUM_NODES=15 SIM_TIME=200 SPEED=20 E0=0 PKT_INTERVAL=0.25 W4="$QS_W4"
    for kv in $EXTRA_ARGS; do
        case "$kv" in
            numNodes=*)    NUM_NODES="${kv#*=}"    ;;
            simTime=*)     SIM_TIME="${kv#*=}"     ;;
            speed=*)       SPEED="${kv#*=}"        ;;
            e0=*)          E0="${kv#*=}"           ;;
            pktInterval=*) PKT_INTERVAL="${kv#*=}" ;;
            w4=*)          W4="${kv#*=}"           ;;
        esac
    done

    local LABEL="${PROTO}"
    [[ "$PROTO" != "AODV" ]] && LABEL="${PROTO}-${MP}"

    local SCENARIO="${FAMILY}-N${NUM_NODES}-V${SPEED}-T${SIM_TIME}-E${E0}-pkt${PKT_INTERVAL}"
    local CSV="$JOB_DIR/job-${FAMILY}-${LABEL}-N${NUM_NODES}-V${SPEED}-pkt${PKT_INTERVAL}-E${E0}-seed${SEED}.csv"
    local START=$(date +%s)

    local SA_FLAGS=""
    if [ "$PROTO" = "SAQMAODV" ] || [ "$PROTO" = "QSAQMAODV" ]; then
        SA_FLAGS="--saAlpha0=$SA_ALPHA0 --saGamma=$SA_GAMMA --saEpsilon0=$SA_EPSILON0 \
                  --saLambda=$SA_LAMBDA --saSeqNoWin=$SA_WINDOW \
                  --saAdaptPeriod=$SA_PERIOD --saLowEThresh=$SA_LOWE \
                  --saW1=$SA_W1 --saW2=$SA_W2 --saW3=$SA_W3"
    fi

    local QS_FLAGS=""
    if [ "$PROTO" = "QSAQMAODV" ]; then
        QS_FLAGS="--qsW4=$W4 --qsQueueHigh=$QS_Q_HIGH --qsQueueLow=$QS_Q_LOW"
    fi

    local ENERGY_FLAGS="--enableEnergy=1"
    [ "${E0:-0}" -gt 0 ] 2>/dev/null && ENERGY_FLAGS="--enableEnergy=1 --initialEnergy=$E0"

    "$EXEC" \
        --scenario="$SCENARIO" \
        --protocol="$PROTO" --maxPaths="$MP" \
        --mobility=GAUSS $ENERGY_FLAGS \
        --numNodes="$NUM_NODES" --simTime="$SIM_TIME" --seed="$SEED" \
        --meanVelMin="$SPEED" --meanVelMax="$SPEED" --alpha=0.85 \
        --pktInterval="$PKT_INTERVAL" --pktSize=512 --numFlows=0 \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $SA_FLAGS $QS_FLAGS \
        --csvFile="$CSV" >/dev/null 2>&1
    local RC=$? DUR=$(( $(date +%s) - START ))
    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        echo "OK   [$FAMILY] ${LABEL} N=${NUM_NODES} pkt=${PKT_INTERVAL} seed=${SEED} (${DUR}s)"
    else
        echo "FAIL [$FAMILY] ${LABEL} rc=$RC"
    fi
}
export -f run_job
export EXEC JOB_DIR
export QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export SA_ALPHA0 SA_GAMMA SA_EPSILON0 SA_LAMBDA SA_WINDOW SA_PERIOD SA_LOWE SA_W1 SA_W2 SA_W3
export QS_W4 QS_Q_HIGH QS_Q_LOW

START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ | tee -a "$LOG"
END_TS=$(date +%s)
WALL=$(( END_TS - START_TS ))

# Merge
MERGED="$RESULTS_DIR/merged.csv"
FIRST_CSV=$(ls "$JOB_DIR"/job-*.csv 2>/dev/null | head -1)
if [ -n "$FIRST_CSV" ]; then
    head -1 "$FIRST_CSV" > "$MERGED"
    for f in "$JOB_DIR"/job-*.csv; do tail -n +2 "$f" >> "$MERGED"; done
    echo "Merged CSV: $MERGED" | tee -a "$LOG"
fi

echo "Done: $(date), wall=$((WALL/3600))h $(((WALL%3600)/60))m" | tee -a "$LOG"

if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(list)
for r in rows:
    proto = r.get('protocol', '')
    mp    = r.get('maxPaths', '1')
    label = f"{proto}-{mp}" if proto not in ('AODV',) else proto
    fam   = r.get('scenario', '').split('-')[0]
    try: pdr = float(r['deliveryRatio'])
    except: continue
    agg[(fam, label)].append(pdr)

families = sorted({k[0] for k in agg})
protos   = ["AODV","AOMDV-3","QMAODV-3","SAQMAODV-3","QSAQMAODV-3"]

print()
print("=" * 65)
print(" PDR SUMMARY — Paper 2 QS-QMAODV")
print("=" * 65)
for fam in families:
    print(f"\n  [{fam}]")
    for p in protos:
        v = agg.get((fam, p), [])
        if v:
            print(f"  {p:<18} {sum(v)/len(v):>8.2%}  (n={len(v)})")
PYEOF
fi

echo ""
echo "To plot: python3 scripts/plot/plot-paper2.py $MERGED"
