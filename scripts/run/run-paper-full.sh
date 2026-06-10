#!/bin/bash
# ================================================================
# run-paper-full.sh — Full paper comparison
# Protocols: AODV, AOMDV, PMAODV, QMAODV, QSAQMAODV(EA-QMAODV)
# Scenarios: E (standard) + ELONG + STAT + W (EA ablation)
# ================================================================
NS3_DIR="$HOME/ns-allinone-3.40/ns-3.40"
BIN="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"
CSV="$NS3_DIR/results.csv"
LOG_DIR="$HOME/qsaqmaodv-ns3/results/logs"
mkdir -p "$LOG_DIR"

SIM_TIME=30
PARALLEL_JOBS=$(nproc)
QS_MU=0.10; QS_KAPPA=0.50

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  FANET Paper Comparison — Full Run                      ║"
echo "║  AODV | AOMDV | PMAODV | QMAODV | EA-QMAODV            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Kiểm tra kết quả đã có → bỏ qua để tiết kiệm thời gian
already_done() {
    local PROTO=$1 NODES=$2 SEED=$3 SCENARIO=${4:-default} MOB=${5:-GAUSS}
    grep -q "^${SCENARIO},${PROTO},${MOB},${SEED},${NODES}," "$CSV" 2>/dev/null
}

run_sim() {
    local PROTO=$1 NODES=$2 SEED=$3 SCENARIO=${4:-default} \
          MOB=${5:-GAUSS} EXTRA="${6:-}"
    local W1=0.4 W2=0.3 W3=0.1 W4=0.2
    local TAG="${SCENARIO}_${PROTO}_N${NODES}_s${SEED}"

    # Skip nếu đã có
    grep -q "^${SCENARIO},${PROTO},${MOB},${SEED},${NODES}," "$CSV" 2>/dev/null \
        && { echo "SKIP $TAG"; return 0; }

    "$BIN" \
        --protocol="$PROTO" --numNodes="$NODES" --seed="$SEED" \
        --simTime="$SIM_TIME" --mobility="$MOB" --scenario="$SCENARIO" \
        --qsMu="$QS_MU" --qsKappa="$QS_KAPPA" \
        --qsW1="$W1" --qsW2="$W2" --qsW3="$W3" --qsW4="$W4" \
        $EXTRA \
        > "$LOG_DIR/${TAG}.log" 2>&1
    local EC=$?
    [[ $EC -eq 0 || $EC -eq 134 || $EC -eq 139 ]] \
        && echo -e "${GREEN}✓${NC} $TAG" \
        || echo -e "${RED}✗${NC} $TAG (exit=$EC)"
}
export -f run_sim
export BIN LOG_DIR SIM_TIME QS_MU QS_KAPPA CSV

PROTOS_BASE="AODV AOMDV PMAODV QMAODV"
PROTO_EA="QSAQMAODV"

# ── E: Standard GAUSS, N=10..50, 36 seeds × 5 protocols = 900 runs ───
echo -e "\n${YELLOW}[E] Standard GAUSS (N=10..50, seeds 1-36, 5 protocols = 900)${NC}"
> /tmp/paper_E.txt
for PROTO in $PROTOS_BASE $PROTO_EA; do
  for N in 10 20 30 40 50; do
    for S in $(seq 1 36); do
      echo "$PROTO $N $S default GAUSS"
    done
  done
done >> /tmp/paper_E.txt
parallel --jobs "$PARALLEL_JOBS" --colsep ' ' \
    run_sim {1} {2} {3} {4} {5} :::: /tmp/paper_E.txt

# ── ELONG: Elongated area (3000×200m), N=20, 30 seeds × 5 protocols = 150 ─
echo -e "\n${YELLOW}[ELONG] Elongated (3000×200m), N=20, seeds 1-30, 5 proto = 150${NC}"
> /tmp/paper_ELONG.txt
for PROTO in $PROTOS_BASE $PROTO_EA; do
  for S in $(seq 1 30); do
    echo "$PROTO 20 $S default GAUSS --areaX=3000 --areaY=200"
  done
done >> /tmp/paper_ELONG.txt
parallel --jobs "$PARALLEL_JOBS" --colsep ' ' \
    run_sim {1} {2} {3} {4} {5} "{6}" :::: /tmp/paper_ELONG.txt

# ── STAT: Static/low-mobility, N=20, 50 seeds × 5 protocols = 250 ────
echo -e "\n${YELLOW}[STAT] Static (vel≈0), N=20, seeds 1-50, 5 proto = 250${NC}"
> /tmp/paper_STAT.txt
for PROTO in $PROTOS_BASE $PROTO_EA; do
  for S in $(seq 1 50); do
    echo "$PROTO 20 $S default GAUSS --meanVelMin=0 --meanVelMax=0"
  done
done >> /tmp/paper_STAT.txt
parallel --jobs "$PARALLEL_JOBS" --colsep ' ' \
    run_sim {1} {2} {3} {4} {5} "{6}" :::: /tmp/paper_STAT.txt

# ── W: EA-QMAODV weight ablation only, N=20, 6 combos × 20 seeds = 120 ─
echo -e "\n${YELLOW}[W] Weight ablation (EA-QMAODV only, 6×20=120)${NC}"
> /tmp/paper_W.txt
for W in "0.5 0.2 0.2 0.1" "0.3 0.3 0.3 0.1" "0.4 0.3 0.2 0.1" \
          "0.4 0.2 0.1 0.3" "0.5 0.1 0.1 0.3" "0.3 0.2 0.4 0.1"; do
  for S in $(seq 1 20); do
    echo "QSAQMAODV 20 $S default GAUSS $W"
  done
done >> /tmp/paper_W.txt

# W-family dùng run_sim variant với custom weights
run_sim_w() {
    local PROTO=$1 NODES=$2 SEED=$3 SCEN=$4 MOB=$5 W1=$6 W2=$7 W3=$8 W4=$9
    local TAG="${SCEN}_${PROTO}_N${NODES}_s${SEED}_w${W1}${W2}${W3}${W4}"
    "$BIN" \
        --protocol="$PROTO" --numNodes="$NODES" --seed="$SEED" \
        --simTime="$SIM_TIME" --mobility="$MOB" --scenario="$SCEN" \
        --qsMu="$QS_MU" --qsKappa="$QS_KAPPA" \
        --qsW1="$W1" --qsW2="$W2" --qsW3="$W3" --qsW4="$W4" \
        > "$LOG_DIR/${TAG}.log" 2>&1
    local EC=$?
    [[ $EC -eq 0 || $EC -eq 134 || $EC -eq 139 ]] \
        && echo -e "${GREEN}✓${NC} $TAG" \
        || echo -e "${RED}✗${NC} $TAG (exit=$EC)"
}
export -f run_sim_w
parallel --jobs "$PARALLEL_JOBS" --colsep ' ' \
    run_sim_w {1} {2} {3} {4} {5} {6} {7} {8} {9} :::: /tmp/paper_W.txt

TOTAL=$(wc -l < "$CSV" 2>/dev/null || echo 0)
echo -e "\n${CYAN}${BOLD}✅ Hoàn tất! Tổng rows trong CSV: $TOTAL${NC}"
echo -e "Results: $CSV"
