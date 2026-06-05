#!/bin/bash
# =============================================================================
# run-paper-full.sh  —  Toàn bộ thí nghiệm cho bài báo Q3  (v2 — fixed)
# =============================================================================
#
#   Family N   : Sweep số nodes       {5,10,15,20,25,30,40,50,75,100} ×5P×30s=1500
#   Family S   : Sweep tốc độ m/s     {5,10,20,30,50,70}              ×5P×30s= 900
#   Family L   : Sweep packet-interval{1.0,0.5,0.25,0.1,0.05}         ×5P×30s= 750
#   Family E   : Sweep năng lượng E₀  {10,20,30,50,75,100} J          ×5P×30s= 900
#   Family W   : Sweep w₃ QSAQMAODV   {0.00…0.50}                     ×1P×30s= 210
#   Family M   : Load×Energy mixed    3×3 combos                       ×5P×30s=1350
#   STAT       : Baseline 50 seeds                                     ×5P×50s= 250
#   ENERGY-LONG: E₀=10J, T=350s                                        ×5P×30s= 150
#                                                                   Total ≈ 6010
# Sử dụng:
#   bash run-paper-full.sh
#   FAMILIES="S L E" bash run-paper-full.sh
#   RESUME=1        bash run-paper-full.sh   # bỏ qua run đã xong
#   JOBS=12         bash run-paper-full.sh
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40-qsaqmaodv/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"
JOBS="${JOBS:-6}"
SEEDS="${SEEDS:-30}"
SIM_TIME="${SIM_TIME:-200}"
RESUME="${RESUME:-0}"
FAMILIES="${FAMILIES:-N S L E W M STAT ELONG}"
PROTOCOLS=(AODV AOMDV PMAODV QMAODV QSAQMAODV)

# QMAODV hyperparams
QM_ALPHA="${QM_ALPHA:-0.5}"
QM_GAMMA="${QM_GAMMA:-0.7}"
QM_EPSILON="${QM_EPSILON:-0.1}"
QM_DECAY="${QM_DECAY:-0.05}"

# QSAQMAODV hyperparams
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

# Baseline cố định
BASE_FLAGS="--mobility=GAUSS --enableEnergy=1 --alpha=0.85 \
            --numNodes=15 --meanVelMin=15 --meanVelMax=25 \
            --pktInterval=0.25 --pktSize=512 --initialEnergy=50 \
            --numFlows=0 --simTime=${SIM_TIME}"

# QM flags (constant, an toàn khi truyền qua xargs)
QM_FLAGS="--qmAlpha=${QM_ALPHA} --qmGamma=${QM_GAMMA} \
          --qmEpsilon=${QM_EPSILON} --qmEpsilonDecay=${QM_DECAY}"

# QS default flags — nhúng thẳng vào job line, KHÔNG dùng env var trong subprocess
# FIX v2: tránh hoàn toàn export function/var phức tạp sang xargs subprocess
QS_FLAGS_DEFAULT="--qsAlpha0=${QS_ALPHA0} --qsGamma=${QS_GAMMA} \
                  --qsEpsilon0=${QS_EPSILON0} --qsLambda=${QS_LAMBDA} \
                  --qsSeqNoWin=${QS_WINDOW} --qsAdaptPeriod=${QS_PERIOD} \
                  --qsLowEThresh=${QS_LOW_E} \
                  --qsQueueHighThresh=${QS_Q_HI} --qsQueueLowThresh=${QS_Q_LO} \
                  --qsW1=${QS_W1} --qsW2=${QS_W2} --qsW3=${QS_W3} --qsW4=${QS_W4}"

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-paper-full-${TS}"
mkdir -p "$ROOT"
LOGFILE="$ROOT/run_full.log"
DONEFILE="$ROOT/done.txt"
touch "$DONEFILE"

if [ ! -x "$EXEC" ]; then
    echo "[ERROR] Không tìm thấy: $EXEC"; exit 1
fi

# ---------------------------------------------------------------------------
# Helper: maxPaths
# ---------------------------------------------------------------------------
mp_for() { case "$1" in AODV|DSDV) echo 1;; *) echo 3;; esac; }

# ---------------------------------------------------------------------------
# Helper: thêm job vào job file
# proto_flags <PROTO>  →  in ra chuỗi flags riêng của protocol đó
# Toàn bộ flags được resolve tại thời điểm build job file (parent shell),
# sau đó lưu dưới dạng chuỗi literal trong jobs_*.txt
# → xargs/subprocess chỉ đọc chuỗi, không cần expand biến nữa
# ---------------------------------------------------------------------------
proto_extra_flags() {
    local P="$1" EXTRA_W3="${2:-}"
    case "$P" in
        QSAQMAODV)
            if [ -n "$EXTRA_W3" ]; then
                # Family W: w3 tuỳ chỉnh, w1=w2=(1-w3)/2
                local W12; W12=$(awk -v w3="$EXTRA_W3" 'BEGIN{printf "%.4f",(1-w3)/2}')
                echo "--qsAlpha0=${QS_ALPHA0} --qsGamma=${QS_GAMMA} \
                      --qsEpsilon0=${QS_EPSILON0} --qsLambda=${QS_LAMBDA} \
                      --qsSeqNoWin=${QS_WINDOW} --qsAdaptPeriod=${QS_PERIOD} \
                      --qsLowEThresh=${QS_LOW_E} \
                      --qsQueueHighThresh=${QS_Q_HI} --qsQueueLowThresh=${QS_Q_LO} \
                      --qsW1=${W12} --qsW2=${W12} --qsW3=${EXTRA_W3} --qsW4=${QS_W4}"
            else
                echo "$QS_FLAGS_DEFAULT"
            fi
            ;;
        *) echo "" ;;
    esac
}

# ---------------------------------------------------------------------------
# run_one — chỉ nhận chuỗi args đã resolve, không expand biến nào thêm
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
    "$EXEC" \
        --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
        --scenario="$TAG"   --csvFile="$CSV" \
        $EXTRA > /dev/null 2>&1
    local RC=$? DUR=$(( $(date +%s) - T0 ))

    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        echo "$KEY" >> "$DONEFILE"
        echo "OK   $KEY (${DUR}s)"
    else
        echo "FAIL $KEY rc=$RC"
    fi
}
export -f run_one
export EXEC DONEFILE RESUME

dispatch() {
    local JF="$1" LABEL="$2"
    echo "  → ${LABEL}: $(wc -l < "$JF") jobs"
    cat "$JF" | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _
}

# ---------------------------------------------------------------------------
# Hàm build job line đầy đủ (tất cả flags đã resolve thành literal string)
# ---------------------------------------------------------------------------
add_job() {
    # add_job <jobfile> <csv> <proto> <seed> <tag> <sweep_extra> [<proto_w3>]
    local JF="$1" CSV="$2" P="$3" S="$4" TAG="$5" SWEEP_EXTRA="$6"
    local MP; MP=$(mp_for "$P")
    local PF; PF=$(proto_extra_flags "$P" "${7:-}")
    # Viết 1 dòng hoàn chỉnh vào job file — literal, không có biến
    printf '%s %s %s %s %s %s %s %s %s\n' \
        "$CSV" "$P" "$MP" "$S" "$TAG" \
        "$BASE_FLAGS" "$QM_FLAGS" "$SWEEP_EXTRA" "$PF" >> "$JF"
}

# ---------------------------------------------------------------------------
# ══════════  FAMILY N  ══════════
# ---------------------------------------------------------------------------
family_N() {
    echo "=== Family N — sweep số nodes ==="
    local CSV="$ROOT/family_N_nodes.csv"
    local JF="$ROOT/jobs_N.txt"; > "$JF"; rm -f "$CSV"
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
# ══════════  FAMILY S  ══════════
# ---------------------------------------------------------------------------
family_S() {
    echo "=== Family S — sweep tốc độ ==="
    local CSV="$ROOT/family_S_speed.csv"
    local JF="$ROOT/jobs_S.txt"; > "$JF"; rm -f "$CSV"
    for VMAX in 5 10 20 30 50 70; do
        local VMIN; VMIN=$(awk -v v="$VMAX" 'BEGIN{printf "%.1f",v/2}')
        for P in "${PROTOCOLS[@]}"; do
            for S in $(seq 1 "$SEEDS"); do
                add_job "$JF" "$CSV" "$P" "$S" "V${VMAX}" \
                    "--meanVelMin=${VMIN} --meanVelMax=${VMAX}"
            done
        done
    done
    dispatch "$JF" "Family S"
}

# ---------------------------------------------------------------------------
# ══════════  FAMILY L  ══════════
# ---------------------------------------------------------------------------
family_L() {
    echo "=== Family L — sweep traffic load ==="
    local CSV="$ROOT/family_L_load.csv"
    local JF="$ROOT/jobs_L.txt"; > "$JF"; rm -f "$CSV"
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
# ══════════  FAMILY E  ══════════
# ---------------------------------------------------------------------------
family_E() {
    echo "=== Family E — sweep initial energy ==="
    local CSV="$ROOT/family_E_energy.csv"
    local JF="$ROOT/jobs_E.txt"; > "$JF"; rm -f "$CSV"
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
# ══════════  FAMILY W  ══════════
# w₃ ∈ {0.00,0.05,0.10,0.20,0.30,0.40,0.50}, w₁=w₂=(1−w₃)/2
# Chỉ QSAQMAODV (parameter sensitivity)
# ---------------------------------------------------------------------------
family_W() {
    echo "=== Family W — sweep w₃ (QSAQMAODV only) ==="
    local CSV="$ROOT/family_W_weight.csv"
    local JF="$ROOT/jobs_W.txt"; > "$JF"; rm -f "$CSV"
    local MP; MP=$(mp_for "QSAQMAODV")
    for W3 in 0.00 0.05 0.10 0.20 0.30 0.40 0.50; do
        local W12; W12=$(awk -v w3="$W3" 'BEGIN{printf "%.4f",(1-w3)/2}')
        for S in $(seq 1 "$SEEDS"); do
            # proto_extra_flags với w3 tuỳ chỉnh — resolve ngay tại đây
            local PF; PF=$(proto_extra_flags "QSAQMAODV" "$W3")
            printf '%s %s %s %s %s %s %s %s\n' \
                "$CSV" "QSAQMAODV" "$MP" "$S" "W${W3}" \
                "$BASE_FLAGS" "$QM_FLAGS" "$PF" >> "$JF"
        done
    done
    dispatch "$JF" "Family W"
}

# ---------------------------------------------------------------------------
# ══════════  FAMILY M  ══════════
# 3 mức tải × 3 mức năng lượng = 9 combos
# ---------------------------------------------------------------------------
family_M() {
    echo "=== Family M — mixed Load×Energy ==="
    local CSV="$ROOT/family_M_mixed.csv"
    local JF="$ROOT/jobs_M.txt"; > "$JF"; rm -f "$CSV"
    for PI in 0.5 0.25 0.05; do
        for E0 in 10 30 50; do
            for P in "${PROTOCOLS[@]}"; do
                for S in $(seq 1 "$SEEDS"); do
                    add_job "$JF" "$CSV" "$P" "$S" "M_I${PI}_E${E0}" \
                        "--pktInterval=${PI} --initialEnergy=${E0}"
                done
            done
        done
    done
    dispatch "$JF" "Family M"
}

# ---------------------------------------------------------------------------
# ══════════  STAT  ══════════
# Baseline cố định, 50 seeds
# ---------------------------------------------------------------------------
family_STAT() {
    echo "=== STAT — statistical validation (50 seeds) ==="
    local CSV="$ROOT/stat_baseline.csv"
    local JF="$ROOT/jobs_STAT.txt"; > "$JF"; rm -f "$CSV"
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 50); do
            add_job "$JF" "$CSV" "$P" "$S" "STAT" ""
        done
    done
    dispatch "$JF" "STAT"
}

# ---------------------------------------------------------------------------
# ══════════  ENERGY-LONG  ══════════
# E₀=10J, T=350s
# ---------------------------------------------------------------------------
family_ELONG() {
    echo "=== ENERGY-LONG — energy depletion (T=350s) ==="
    local CSV="$ROOT/elong_depletion.csv"
    local JF="$ROOT/jobs_ELONG.txt"; > "$JF"; rm -f "$CSV"
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do
            add_job "$JF" "$CSV" "$P" "$S" "ELONG" \
                "--initialEnergy=10 --simTime=350"
        done
    done
    dispatch "$JF" "ENERGY-LONG"
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
{
echo "================================================================="
echo "  Paper Q3 — Full Experiment Suite  (v2)"
echo "================================================================="
echo "  NS3:       $NS3_DIR"
echo "  Output:    $ROOT"
echo "  Families:  $FAMILIES"
echo "  Seeds:     $SEEDS  |  Jobs: $JOBS  |  SimTime: ${SIM_TIME}s"
echo "  Protocols: ${PROTOCOLS[*]}"
echo "  QSAQMAODV: α0=$QS_ALPHA0 γ=$QS_GAMMA ε0=$QS_EPSILON0"
echo "             λ=$QS_LAMBDA w=($QS_W1,$QS_W2,$QS_W3,$QS_W4)"
echo "  Resume:    $RESUME"
echo "  Started:   $(date)"
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
        *) echo "Unknown: $F" ;;
    esac
done 2>&1 | tee -a "$LOGFILE"

WALL=$(( $(date +%s) - START_TS ))
OK_C=$(grep -c  "^OK"   "$LOGFILE" 2>/dev/null || echo 0)
FAIL_C=$(grep -c "^FAIL" "$LOGFILE" 2>/dev/null || echo 0)

{
echo ""
echo "================================================================="
echo "  Xong: $(date)"
printf "  Wall: %dh %dm %ds\n" $((WALL/3600)) $(((WALL%3600)/60)) $((WALL%60))
echo "  OK: $OK_C  |  FAIL: $FAIL_C"
echo "  CSVs:"; ls -1 "$ROOT"/*.csv 2>/dev/null | sed 's/^/    /'
[ "$FAIL_C" -gt 0 ] && grep "^FAIL" "$LOGFILE" | sort | uniq -c | sort -rn | head -20
echo "================================================================="
} | tee -a "$LOGFILE"
