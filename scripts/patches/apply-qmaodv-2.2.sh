#!/bin/bash
# Phase QMAODV-2.2: copy q-table.{h,cc} into src/qmaodv/model/ and update CMakeLists.
# Mirrors PMAODV apply-phase-2.2.sh.
# Usage: cd ~/workspace/ns-allinone-3.40/ns-3.40 && bash apply-qmaodv-2.2.sh

set -e

NS3_DIR="${NS3_DIR:-$HOME/workspace/ns-allinone-3.40/ns-3.40}"
# Where the project ships the q-table source files. Override with:
#   SRC_DIR=/path/to/fanet-multipath-ns3/src/qmaodv bash apply-qmaodv-2.2.sh
SRC_DIR="${SRC_DIR:-/mnt/e/CODE/QMADOV/QMAODV/fanet-multipath-ns3/src/qmaodv}"

cd "$NS3_DIR"

echo "=== 1. Copy q-table files into src/qmaodv/model/ ==="
cp "$SRC_DIR/qmaodv-qtable.h"  src/qmaodv/model/
cp "$SRC_DIR/qmaodv-qtable.cc" src/qmaodv/model/
echo "  Copied."

echo ""
echo "=== 2. Add to src/qmaodv/CMakeLists.txt ==="
CMAKE=src/qmaodv/CMakeLists.txt

if grep -q "qmaodv-qtable" "$CMAKE"; then
    echo "  Already in CMakeLists.txt, skip."
else
    # Insert .cc after qmaodv-rtable.cc in SOURCE_FILES
    sed -i 's|model/qmaodv-rtable.cc|model/qmaodv-rtable.cc\n    model/qmaodv-qtable.cc|' "$CMAKE"
    # Insert .h after qmaodv-rtable.h in HEADER_FILES
    sed -i 's|model/qmaodv-rtable.h|model/qmaodv-rtable.h\n    model/qmaodv-qtable.h|' "$CMAKE"
    echo "  Added to CMakeLists.txt."
fi

echo ""
echo "=== 3. Verify CMakeLists.txt ==="
grep -E "qmaodv-qtable" "$CMAKE" || echo "  WARNING: not found in CMakeLists!"

echo ""
echo "=== 4. Reconfigure + build ==="
./ns3 configure --enable-examples --enable-tests --build-profile=debug 2>&1 | tail -5
./ns3 build 2>&1 | tail -10

echo ""
echo "=== 5. Verify q-table header exposed ==="
ls -la build/include/ns3/qmaodv-qtable.h 2>&1

echo ""
echo "=========================================="
echo "  Phase QMAODV-2.2 done. QMAODV behaves identically to AODV until"
echo "  the Q-learning logic is wired in by 2.3.a/b/c/d patches."
echo "=========================================="
