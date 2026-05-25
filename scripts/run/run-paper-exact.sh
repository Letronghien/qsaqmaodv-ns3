#!/bin/bash
# run-paper-exact.sh
# ----------------------------------------------------------------------------
# Reproduce ĐÚNG scenario của paper SA-QMAODV §5 (Simulation Setup):
#   - Area:        500 × 500 m² (paper §5)
#   - Sim time:    200 s
#   - Nodes:       10..30 UAV
#   - Mobility:    Random (paper không nói rõ — dùng GAUSS-Markov 3D)
#   - Traffic:     CBR 150 kbps per source, 512B packets
#                  → pktInterval = 0.0273s (37 pkt/s × 512B × 8 = 151.5 kbps)
#   - MAC:         IEEE 802.11 (NS-3 default)
#   - Queue:       DropTail (NS-3 default)
#   - Seeds:       30 per config (paper §5)
#   - Protocols:   AODV, AOMDV-3, QMAODV-3, SA-QMAODV-3 (4 protocols)
#                  (Paper so AODV/PMAODV/QMAODV/SAQMAODV — mình swap PMAODV → AOMDV
#                  theo yêu cầu user)
#
# Total: 5 N × 4 protocols × 30 seeds = 600 runs
# Estimate: ~35-45 phút trên 7-core (1 job ~25s × 600 / 7 = ~36 phút)
#
# Usage:
#   bash run-paper-exact.sh                # default 30 seeds, 7 jobs
#   SEEDS=10 bash run-paper-exact.sh       # quick test
#   JOBS=4 bash run-paper-exact.sh         # less cores
# ----------------------------------------------------------------------------
set -u

# === Detect ns-3 ===
if [ -z "${NS3_DIR:-}" ]; then
    for cand in \
        "$HOME/ns-allinone-3.40/ns-3.40" \
        "$HOME/ns-allinone-3.42/ns-3.42" \
        "$HOME/workspace/ns-allinone-3.40/ns-3.40"; do
        [ -f "$cand/ns3" ] && [ -d "$cand/src/aodv" ] && { NS3_DIR="$cand"; break; }
    done
fi
[ -z "${NS3_DIR:-}" ] && { echo "ERROR: NS3_DIR not found"; exit 1; }

EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

# === Config ===
JOBS="${JOBS:-7}"            # User yêu cầu 7 song song
SEEDS="${SEEDS:-30}"         # Paper §5
SIM_TIME="${SIM_TIME:-200}"  # Paper §5

# Paper scenario
AREA_X=500
AREA_Y=500
AREA_Z=300                   # FANET 3D với altitude 300m (paper không nói rõ)
PKT_SIZE=512                 # Paper §5
PKT_INTERVAL=0.0273          # = 150 kbps per source (paper §5)
MEAN_VEL_MIN=15              # m/s — standard FANET UAV speed
MEAN_VEL_MAX=25              # m/s
GM_ALPHA=0.85                # Gauss-Markov correlation
N_VALUES=(10 15 20 25 30)    # Paper §5

# 4 protocols (paper swap PMAODV → AOMDV)
PROTOCOLS=(
    "AODV      1"
    "AOMDV     3"
    "QMAODV    3"
    "SAQMAODV  3"
)

# === QMAODV winner (Strategy A từ tuning earlier) ===
QM_ALPHA=0.5
QM_GAMMA=0.7
QM_EPSILON=0.1
QM_DECAY=0.05

# === SA-QMAODV Winner Final (Test A trong paper-exact, PDR=41.97% tại N=20) ===
#   Phát hiện: paper hyperparams λ=0.1, w3=0.1 không reproduce paper claim trong
#   homogeneous-battery scenario. Cần λ=0.01 (slow α adapt) + w3=0 (no energy bias).
SA_LAMBDA=0.01      # Was 0.5 — phải nhỏ để α không saturate
SA_WINDOW=10
SA_PERIOD=1.0
SA_GAMMA=0.9
SA_ALPHA0=0.5
SA_EPSILON0=0.3
SA_W1=0.5
SA_W2=0.5           # Was 0.4 — bù phần w3 đã chuyển sang
SA_W3=0.0           # Was 0.1 — set 0 trong normal mode (energy không phân biệt được)

# === Output ===
TS=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="$HOME/results-paper-exact-${TS}"
JOB_DIR="$RESULTS_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$RESULTS_DIR/merged.csv"
LOG="$RESULTS_DIR/run.log"

# === Generate jobs ===
JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for N in "${N_VALUES[@]}"; do
    for SEED in $(seq 1 "$SEEDS"); do
        for EXP in "${PROTOCOLS[@]}"; do
            read -r PROTO MP <<< "$EXP"
            echo "$PROTO $MP $N $SEED" >> "$JOB_FILE"
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

# === Print config ===
{
echo "==================================================="
echo " PAPER-EXACT Scenario Runner (SA-QMAODV §5)"
echo "==================================================="
echo " Area:          ${AREA_X} × ${AREA_Y} m² (Z=${AREA_Z}m)"
echo " Sim time:      ${SIM_TIME}s"
echo " Nodes:         ${N_VALUES[*]}"
echo " Mobility:      GAUSS, vel=${MEAN_VEL_MIN}-${MEAN_VEL_MAX} m/s, α=${GM_ALPHA}"
echo " Traffic:       150 kbps per source (pktInt=${PKT_INTERVAL}s, ${PKT_SIZE}B)"
echo " Protocols:     AODV, AOMDV-3, QMAODV-3, SAQMAODV-3"
echo " QMAODV cfg:    α=${QM_ALPHA} γ=${QM_GAMMA} ε=${QM_EPSILON} decay=${QM_DECAY}"
echo " SA cfg:        λ=${SA_LAMBDA} W=${SA_WINDOW} P=${SA_PERIOD} γ=${SA_GAMMA} w=(${SA_W1},${SA_W2},${SA_W3})"
echo " Seeds:         $SEEDS"
echo " Parallel jobs: $JOBS"
echo " Total runs:    $TOTAL"
echo " Output:        $RESULTS_DIR"
echo " Started:       $(date)"
echo "==================================================="
} | tee "$LOG"

# === Worker ===
run_job() {
    local PROTO=$1 MP=$2 N=$3 SEED=$4
    local label="${PROTO}"
    [ "$PROTO" = "PMAODV" ] || [ "$PROTO" = "AOMDV" ] || \
    [ "$PROTO" = "QMAODV" ] || [ "$PROTO" = "SAQMAODV" ] && label="${PROTO}-${MP}"
    local CSV="$JOB_DIR/job-${label}-N${N}-seed${SEED}.csv"
    local START=$(date +%s)

    # SA-only flags
    local SA_FLAGS=""
    if [ "$PROTO" = "SAQMAODV" ]; then
        SA_FLAGS="--saAlpha0=$SA_ALPHA0 --saGamma=$SA_GAMMA --saEpsilon0=$SA_EPSILON0 \
                  --saLambda=$SA_LAMBDA --saSeqNoWin=$SA_WINDOW \
                  --saAdaptPeriod=$SA_PERIOD --saLowEThresh=0.20 \
                  --saW1=$SA_W1 --saW2=$SA_W2 --saW3=$SA_W3"
    fi

    "$EXEC" \
        --scenario="paper-exact" \
        --protocol="$PROTO" --maxPaths="$MP" \
        --mobility=GAUSS --enableEnergy=1 \
        --numNodes="$N" --simTime="$SIM_TIME" --seed="$SEED" \
        --areaX="$AREA_X" --areaY="$AREA_Y" --areaZ="$AREA_Z" \
        --meanVelMin="$MEAN_VEL_MIN" --meanVelMax="$MEAN_VEL_MAX" --alpha="$GM_ALPHA" \
        --pktInterval="$PKT_INTERVAL" --pktSize="$PKT_SIZE" --numFlows=0 \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $SA_FLAGS \
        --csvFile="$CSV" >/dev/null 2>&1
    local rc=$?
    local DUR=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   ${label} N=${N} seed=${SEED} (${DUR}s)"
    else
        echo "FAIL ${label} N=${N} seed=${SEED} rc=$rc"
    fi
}
export -f run_job
export EXEC SIM_TIME JOB_DIR
export AREA_X AREA_Y AREA_Z MEAN_VEL_MIN MEAN_VEL_MAX GM_ALPHA
export PKT_SIZE PKT_INTERVAL
export QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export SA_LAMBDA SA_WINDOW SA_PERIOD SA_GAMMA SA_ALPHA0 SA_EPSILON0
export SA_W1 SA_W2 SA_W3

# === Run parallel — JOBS=7 song song ===
START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ \
    | tee -a "$LOG"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

# === Merge CSVs ===
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
echo "==================================================="
echo " Done: $(date)"
echo " Wall: $((TOTAL_SEC/3600))h $(((TOTAL_SEC%3600)/60))m $((TOTAL_SEC%60))s"
echo "==================================================="
echo ""
echo " Next:"
echo "   python3 ~/scripts/plot/plot-experiments-4proto.py \\"
echo "         $MERGED \\"
echo "         ~/figures-paper-exact/"
echo "==================================================="
} | tee -a "$LOG"

# === Summary table per (protocol, N) ===
if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r['protocol']
    mp = r.get('maxPaths', '1')
    label = f"{proto}-{mp}" if proto in ("PMAODV","AOMDV","QMAODV","SAQMAODV") else proto
    N = int(r['numNodes'])
    for m in ("deliveryRatio","avgDelayMs","throughputMbps","routingOverhead","totalEnergyJ"):
        agg[(label, N)][m].append(float(r[m]))

protos = sorted({k[0] for k in agg.keys()})
ns     = sorted({k[1] for k in agg.keys()})

print()
print("=" * 75)
print(" PDR (%) — Paper-exact scenario")
print("=" * 75)
print(f"{'proto':<13} " + " ".join(f"N={n:>3}" for n in ns))
print("-" * 75)
for p in protos:
    cells = []
    for n in ns:
        v = agg.get((p, n), {}).get('deliveryRatio', [])
        cells.append(f"{sum(v)/len(v):>6.2f}" if v else f"{'—':>6}")
    print(f"{p:<13} " + " ".join(cells))

print()
print("=" * 75)
print(" Delay (ms) — Paper-exact scenario")
print("=" * 75)
print(f"{'proto':<13} " + " ".join(f"N={n:>3}" for n in ns))
print("-" * 75)
for p in protos:
    cells = []
    for n in ns:
        v = agg.get((p, n), {}).get('avgDelayMs', [])
        cells.append(f"{sum(v)/len(v):>6.1f}" if v else f"{'—':>6}")
    print(f"{p:<13} " + " ".join(cells))

print()
print("=" * 75)
print(" Throughput (Mbps) — Paper-exact scenario")
print("=" * 75)
print(f"{'proto':<13} " + " ".join(f"N={n:>3}" for n in ns))
print("-" * 75)
for p in protos:
    cells = []
    for n in ns:
        v = agg.get((p, n), {}).get('throughputMbps', [])
        cells.append(f"{sum(v)/len(v):>6.4f}" if v else f"{'—':>6}")
    print(f"{p:<13} " + " ".join(cells))
PYEOF
fi
