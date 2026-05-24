#!/bin/bash
# apply-qsaqmaodv-all.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
export NS3_DIR

echo "=================================================="
echo " QS-QMAODV — Applying NS-3 Patches"
echo "=================================================="
echo " NS3_DIR: $NS3_DIR"

if [ ! -d "$NS3_DIR/src/saqmaodv" ]; then
    echo "ERROR: saqmaodv module not found. Run base SA-QMAODV setup first."
    exit 1
fi

echo "[1/2] Creating qsaqmaodv NS-3 module..."
python3 "$SCRIPT_DIR/apply-qsaqmaodv-module.py"

echo ""
echo "[2/2] Patching fanet-sim.cc..."
python3 "$SCRIPT_DIR/apply-qsaqmaodv-fanet.py"

echo ""
echo "=================================================="
echo " Done. Now build:"
echo "   cd \$NS3_DIR && ./ns3 build"
echo "=================================================="
