#!/bin/bash
# =============================================================================
# run-and-plot.sh  —  Setup swap + chạy từng family + vẽ đồ thị
# =============================================================================
# Usage:
#   bash run-and-plot.sh              # chạy tất cả family
#   FAMILIES="S E" bash run-and-plot.sh  # chỉ chạy S và E
# =============================================================================

REPO=~/qsaqmaodv-ns3
JOBS="${JOBS:-3}"
SEEDS="${SEEDS:-30}"
SIM_TIME="${SIM_TIME:-200}"
FAMILIES="${FAMILIES:-S E W M STAT ELONG}"

# ---------------------------------------------------------------------------
# Bước 1: Tạo swap 16GB (chỉ cần làm 1 lần)
# ---------------------------------------------------------------------------
setup_swap() {
    if swapon --show | grep -q swapfile; then
        echo "[SWAP] Đã có swap: $(free -h | grep Swap)"
        return
    fi
    echo "[SWAP] Tạo 16GB swap..."
    sudo fallocate -l 16G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    # Persist qua reboot
    grep -q /swapfile /etc/fstab || \
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "[SWAP] Xong: $(free -h | grep Swap)"
}

# ---------------------------------------------------------------------------
# Bước 2: Chạy 1 family
# ---------------------------------------------------------------------------
run_family() {
    local F="$1"
    echo ""
    echo "══════════════════════════════════════════"
    echo "  Chạy Family $F  (SEEDS=$SEEDS, SIM_TIME=$SIM_TIME, JOBS=$JOBS)"
    echo "══════════════════════════════════════════"
    ulimit -c 0
    FAMILIES="$F" SEEDS="$SEEDS" SIM_TIME="$SIM_TIME" JOBS="$JOBS" \
        bash "$REPO/scripts/run/run-paper-full.sh"
}

# ---------------------------------------------------------------------------
# Bước 3: Vẽ đồ thị sau khi family xong
# ---------------------------------------------------------------------------
plot_family() {
    local F="$1"
    local RDIR; RDIR=$(ls -dt ~/results-paper-full-* | head -1)
    local FIGDIR=~/figures/$F
    mkdir -p "$FIGDIR"

    case "$F" in
        N)
            echo "[PLOT] Family N → plot-family-N.py"
            python3 "$REPO/scripts/plot/plot-family-N.py" \
                "$RDIR/family_N_nodes.csv" "$FIGDIR/" ;;
        S)
            echo "[PLOT] Family S → plot-family-S.py"
            python3 "$REPO/scripts/plot/plot-family-S.py" \
                "$RDIR/family_S_speed.csv" "$FIGDIR/" ;;
        L)
            echo "[PLOT] Family L → plot-family-L.py"
            python3 "$REPO/scripts/plot/plot-family-L.py" \
                "$RDIR/family_L_load.csv" "$FIGDIR/" ;;
        E)
            echo "[PLOT] Family E → plot-family-E.py"
            python3 "$REPO/scripts/plot/plot-family-E.py" \
                "$RDIR/family_E_energy.csv" "$FIGDIR/" ;;
        W)
            echo "[PLOT] Family W → plot-family-W.py"
            python3 "$REPO/scripts/plot/plot-family-W.py" \
                "$RDIR/family_W_weight.csv" "$FIGDIR/" ;;
        M)
            echo "[PLOT] Family M → plot-family-M.py"
            python3 "$REPO/scripts/plot/plot-family-M.py" \
                "$RDIR/family_M_mixed.csv" "$FIGDIR/" ;;
        STAT)
            echo "[PLOT] STAT → plot-family-STAT.py"
            python3 "$REPO/scripts/plot/plot-family-STAT.py" \
                "$RDIR/stat_baseline.csv" "$FIGDIR/" ;;
        ELONG)
            echo "[PLOT] ELONG → plot-family-E.py (reuse)"
            python3 "$REPO/scripts/plot/plot-family-E.py" \
                "$RDIR/elong_depletion.csv" "$FIGDIR/" ;;
    esac

    echo "[PLOT] Figures saved: $FIGDIR"
    ls "$FIGDIR"/*.png 2>/dev/null | sed 's/^/  /'
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo "================================================================="
echo "  run-and-plot.sh"
echo "  FAMILIES=$FAMILIES | SEEDS=$SEEDS | SIM_TIME=$SIM_TIME | JOBS=$JOBS"
echo "================================================================="

setup_swap

for F in $FAMILIES; do
    run_family "$F"
    plot_family "$F"
done

echo ""
echo "✓ Xong! Figures tại ~/figures/"
ls ~/figures/*/Fig_*.png 2>/dev/null | head -30
