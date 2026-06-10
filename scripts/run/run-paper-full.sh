#!/bin/bash
# =============================================================================
# run-paper-full.sh  —  Toàn bộ thí nghiệm cho bài báo Q3  (v4 — bugfix)
# =============================================================================
# FIXES so với v3:
#   [FIX-1] dispatch(): bỏ xargs -P (stdout race condition → mất OK lines)
#           → dùng background jobs (&) + throttle bằng jobs -rp
#           → run_one chạy trong subshell con, không cần export -f
#   [FIX-2] grep -c bug: grep trả về exit 1 khi 0 matches
#           → "|| echo 0" fire cả hai → FAIL_C="0\n0" → bash error line 316
#           → fix: tách thành 2 lệnh, dùng ${VAR:-0}
#   [FIX-3] CSV header race condition: nhiều process đồng thời check stat()
#           và ghi header → duplicate headers trong CSV
#           → fix: pre-create CSV với header trước khi dispatch
# =============================================================================
# Usage:
#   bash run-paper-full.sh
#   FAMILIES="S L E" bash run-paper-full.sh
#   RESUME=1 bash run-paper-full.sh
#   JOBS=3   bash run-paper-full.sh
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40-qsaqmaodv/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"
JOBS="${JOBS:-6}"
SEEDS="${SEEDS:-30}"
SIM_TIME="${SIM_TIME:-200}"
RESUME="${RESUME:-0}"
FAMILIES="${FAMILIES:-N S L E W M STAT ELONG}"
PROTOCOLS=(AODV AOMDV PMAODV QMAODV QSAQMAODV)

# QMAODV params
QM_ALPHA="${QM_ALPHA:-0.5}"
QM_GAMMA="${QM_GAMMA:-0.7}"
QM_EPSILON="${QM_EPSILON:-0.1}"
QM_DECAY="${QM_DECAY:-0.05}"

# QSAQMAODV params
QS_ALPHA0="${QS_ALPHA0:-0.5}"
QS_GAMMA="${QS_GAMMA:-0.9}"
QS_EPSILON0="${QS_EPSILON0:-0.3}"
QS_LAMBDA="${QS_LAMBDA:-0.1}"
QS_WINDOW="${QS_WINDOW:-5}"
QS_PERIOD="${QS_PERIOD:-10.0}"
QS_LOW_E="${QS_LOW_E:-0.20}"
QS_Q_HI="${QS_Q_HI:-0.70}"
QS_Q_LO="${QS_Q_LO:-0.30}"
QS_W1="${QS_W1:-0.40}"
QS_W2="${QS_W2:-0.30}"
QS_W3="${QS_W3:-0.10}"
QS_W4="${QS_W4:-0.20}"

# ---------------------------------------------------------------------------
# Flag strings — PHẢI là 1 dòng, không có \ + newline
# ---------------------------------------------------------------------------
BASE_FLAGS="--mobility=GAUSS --enableEnergy=1 --alpha=0.85 --numNodes=15 --meanVelMin=15 --meanVelMax=25 --pktInterval=0.25 --pktSize=512 --initialEnergy=50 --numFlows=0 --simTime=${SIM_TIME}"

QM_FLAGS="--qmAlpha=${QM_ALPHA} --qmGamma=${QM_GAMMA} --qmEpsilon=${QM_EPSILON} --qmEpsilonDecay=${QM_DECAY}"

# ---------------------------------------------------------------------------
# CSV header — dùng chung cho tất cả family (FIX-3)
# ---------------------------------------------------------------------------
CSV_HEADER="scenario,protocol,mobility,maxPaths,numNodes,numFlows,meanVelMin,meanVelMax,pktInterval,simTime,seed,deliveryRatio,avgDelayMs,throughputMbps,routingOverhead,totalEnergyJ,nodesDead"

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-paper-full-${TS}"
mkdir -p "$ROOT"
LOGFILE="$ROOT/run_full.log"
DONEFILE="$ROOT/done.txt"
LOCKFILE="$ROOT/log.lock"
touch "$DONEFILE" "$LOCKFILE"

[ ! -x "$EXEC" ] && echo "[ERROR] Không tìm thấy: $EXEC" && exit 1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
mp_for() { case "$1" in AODV|DSDV) echo 1;; *) echo 3;; esac; }

qs_flags_for() {
    [ "$1" != "QSAQMAODV" ] && return
    local W3="${2:-${QS_W3}}"
    local W12; W12=$(awk -v w="$W3" 'BEGIN{printf "%.4f",(1-w)/2}')
    echo "--qsAlpha0=${QS_ALPHA0} --qsGamma=${QS_GAMMA} --qsEpsilon0=${QS_EPSILON0} --qsLambda=${QS_LAMBDA} --qsSeqNoWin=${QS_WINDOW} --qsAdaptPeriod=${QS_PERIOD} --qsLowEThresh=${QS_LOW_E} --qsQueueHighThresh=${QS_Q_HI} --qsQueueLowThresh=${QS_Q_LO} --qsW1=${W12} --qsW2=${W12} --qsW3=${W3} --qsW4=${QS_W4}"
}

add_job() {
    local JF="$1" CSV="$2" P="$3" S="$4" TAG="$5" SW="${6:-}"
    local MP; MP=$(mp_for "$P")
    local PF; PF=$(qs_flags_for "$P" "${7:-}")
    printf '%s\n' "$CSV $P $MP $S $TAG $BASE_FLAGS $QM_FLAGS $SW $PF" | tr -s ' ' >> "$JF"
}

# ---------------------------------------------------------------------------
# run_one — chạy 1 simulation
# Gọi bằng background job (&) nên không cần export -f
# ---------------------------------------------------------------------------
run_one() {
    local CSV="$1" PROTO="$2" MP="$3" SEED="$4" TAG="$5"
    shift 5
    local EXTRA="$*"
    local KEY="${TAG}_${PROTO}_s${SEED}"

    if [ "${RESUME:-0}" = "1" ] && grep -qF "$KEY" "${DONEFILE}" 2>/dev/null; then
        echo "SKIP $KEY"; return 0
    fi

    local T0; T0=$(date +%s)
    # shellcheck disable=SC2086
    "$EXEC" --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
            --scenario="$TAG" --csvFile="$CSV" $EXTRA > /dev/null 2>&1
    local RC=$? DUR=$(( $(date +%s) - T0 ))

    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        echo "$KEY" >> "$DONEFILE"
        echo "OK   $KEY (${DUR}s)"
    else
        echo "FAIL $KEY rc=$RC"
    fi
}

# ---------------------------------------------------------------------------
# [FIX-1] dispatch — background jobs thay vì xargs -P
# Tránh stdout race condition: run_one là bash function trong cùng process
# tree → stdout của mỗi background job được OS serialise qua pipe.
# ---------------------------------------------------------------------------
dispatch() {
    local JF="$1" LABEL="$2"
    echo "  → ${LABEL}: $(wc -l < "$JF") jobs"
    while IFS= read -r line; do
        # Throttle: đợi nếu đã có JOBS process đang chạy
        while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do
            sleep 0.2
        done
        # shellcheck disable=SC2086
        run_one $line &
    done < "$JF"
    wait  # đợi tất cả job trong family xong
}

# ---------------------------------------------------------------------------
# FAMILY N
# ---------------------------------------------------------------------------
family_N() {
    echo "=== Family N — sweep số nodes ==="
    local CSV="$ROOT/family_N_nodes.csv" JF="$ROOT/jobs_N.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"          # [FIX-3] pre-create header
    for N in 5 10 15 20 25 30 40 50 75 100; do
        for P in "${PROTOCOLS[@]}"; do
            for S in $(seq 1 "$SEEDS"); do
                add_job "$JF" "$CSV" "$P" "$S" "N${N}" "--numNodes=${N}"
            done
        done
    done
    dispatch "$JF" "Family N"
}

# ---------------------------------------------------------------------------
# FAMILY S
# ---------------------------------------------------------------------------
family_S() {
    echo "=== Family S — sweep tốc độ ==="
    local CSV="$ROOT/family_S_speed.csv" JF="$ROOT/jobs_S.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for VMAX in 5 10 20 30 50 70; do
        local VMIN; VMIN=$(awk -v v="$VMAX" 'BEGIN{printf "%.1f",v/2}')
        for P in "${PROTOCOLS[@]}"; do
            for S in $(seq 1 "$SEEDS"); do
                add_job "$JF" "$CSV" "$P" "$S" "V${VMAX}" "--meanVelMin=${VMIN} --meanVelMax=${VMAX}"
            done
        done
    done
    dispatch "$JF" "Family S"
}

# ---------------------------------------------------------------------------
# FAMILY L
# ---------------------------------------------------------------------------
family_L() {
    echo "=== Family L — sweep traffic load ==="
    local CSV="$ROOT/family_L_load.csv" JF="$ROOT/jobs_L.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for PI in 1.0 0.5 0.25 0.1 0.05; do
        for P in "${PROTOCOLS[@]}"; do
            for S in $(seq 1 "$SEEDS"); do
                add_job "$JF" "$CSV" "$P" "$S" "I${PI}" "--pktInterval=${PI}"
            done
        done
    done
    dispatch "$JF" "Family L"
}

# ---------------------------------------------------------------------------
# FAMILY E
# ---------------------------------------------------------------------------
family_E() {
    echo "=== Family E — sweep initial energy ==="
    local CSV="$ROOT/family_E_energy.csv" JF="$ROOT/jobs_E.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for E0 in 10 20 30 50 75 100; do
        for P in "${PROTOCOLS[@]}"; do
            for S in $(seq 1 "$SEEDS"); do
                add_job "$JF" "$CSV" "$P" "$S" "E${E0}" "--initialEnergy=${E0}"
            done
        done
    done
    dispatch "$JF" "Family E"
}

# ---------------------------------------------------------------------------
# FAMILY W  (chỉ QSAQMAODV, w1=w2=(1-w3)/2)
# ---------------------------------------------------------------------------
family_W() {
    echo "=== Family W — sweep w3 (QSAQMAODV only) ==="
    local CSV="$ROOT/family_W_weight.csv" JF="$ROOT/jobs_W.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for W3 in 0.00 0.05 0.10 0.20 0.30 0.40 0.50; do
        for S in $(seq 1 "$SEEDS"); do
            add_job "$JF" "$CSV" "QSAQMAODV" "$S" "W${W3}" "" "$W3"
        done
    done
    dispatch "$JF" "Family W"
}

# ---------------------------------------------------------------------------
# FAMILY M  (3 load × 3 energy)
# ---------------------------------------------------------------------------
family_M() {
    echo "=== Family M — mixed Load×Energy ==="
    local CSV="$ROOT/family_M_mixed.csv" JF="$ROOT/jobs_M.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for PI in 0.5 0.25 0.05; do
        for E0 in 10 30 50; do
            for P in "${PROTOCOLS[@]}"; do
                for S in $(seq 1 "$SEEDS"); do
                    add_job "$JF" "$CSV" "$P" "$S" "M_I${PI}_E${E0}" "--pktInterval=${PI} --initialEnergy=${E0}"
                done
            done
        done
    done
    dispatch "$JF" "Family M"
}

# ---------------------------------------------------------------------------
# STAT  (50 seeds, baseline)
# ---------------------------------------------------------------------------
family_STAT() {
    echo "=== STAT — statistical validation (50 seeds) ==="
    local CSV="$ROOT/stat_baseline.csv" JF="$ROOT/jobs_STAT.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 50); do
            add_job "$JF" "$CSV" "$P" "$S" "STAT" ""
        done
    done
    dispatch "$JF" "STAT"
}

# ---------------------------------------------------------------------------
# ENERGY-LONG  (E0=10J, T=350s)
# ---------------------------------------------------------------------------
family_ELONG() {
    echo "=== ENERGY-LONG — energy depletion (T=350s) ==="
    local CSV="$ROOT/elong_depletion.csv" JF="$ROOT/jobs_ELONG.txt"
    > "$JF"
    echo "$CSV_HEADER" > "$CSV"
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do
            add_job "$JF" "$CSV" "$P" "$S" "ELONG" "--initialEnergy=3 --simTime=350"
        done
    done
    dispatch "$JF" "ENERGY-LONG"
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
{
echo "================================================================="
echo "  Paper Q3 — Full Experiment Suite (v4 — bugfix)"
echo "================================================================="
echo "  NS3:      $NS3_DIR"
echo "  Output:   $ROOT"
echo "  Families: $FAMILIES"
echo "  Seeds: $SEEDS | Jobs: $JOBS | SimTime: ${SIM_TIME}s"
echo "  Protocols: ${PROTOCOLS[*]}"
echo "  QSAQMAODV: w=($QS_W1,$QS_W2,$QS_W3,$QS_W4) λ=$QS_LAMBDA"
echo "  Resume: $RESUME | Started: $(date)"
echo "================================================================="
} | tee "$LOGFILE"

# ---------------------------------------------------------------------------
# Chạy
# ---------------------------------------------------------------------------
START_TS=$(date +%s)
for F in $FAMILIES; do
    case "$F" in
        N)     family_N    ;;
        S)     family_S    ;;
        L)     family_L    ;;
        E)     family_E    ;;
        W)     family_W    ;;
        M)     family_M    ;;
        STAT)  family_STAT ;;
        ELONG) family_ELONG ;;
        *) echo "Unknown family: $F" ;;
    esac
done 2>&1 | tee -a "$LOGFILE"

WALL=$(( $(date +%s) - START_TS ))

# [FIX-2] grep -c trả về exit 1 khi 0 matches → || echo 0 fire → "0\n0"
# Fix: tách thành 2 lệnh riêng, dùng ${VAR:-0} làm fallback
OK_C=$(grep -c   "^OK"   "$LOGFILE" 2>/dev/null); OK_C=${OK_C:-0}
FAIL_C=$(grep -c "^FAIL" "$LOGFILE" 2>/dev/null); FAIL_C=${FAIL_C:-0}

{
echo ""
echo "================================================================="
echo "  Xong: $(date)"
printf "  Wall: %dh %dm %ds\n" $((WALL/3600)) $(((WALL%3600)/60)) $((WALL%60))
echo "  OK: $OK_C  |  FAIL: $FAIL_C"
echo "  CSVs:"; ls -1 "$ROOT"/*.csv 2>/dev/null | sed 's/^/    /'
if [ "$FAIL_C" -gt 0 ]; then
    echo "  Top FAILs:"
    grep "^FAIL" "$LOGFILE" | sed 's/_s[0-9]*//' | sort | uniq -c | sort -rn | head -15
fi
echo "================================================================="
} | tee -a "$LOGFILE"
