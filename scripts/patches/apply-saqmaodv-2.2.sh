#!/bin/bash
# Phase SAQMAODV-2.2: copy saqmaodv-qtable.{h,cc} into src/saqmaodv/model/.
set -e

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
SRC_DIR="${SRC_DIR:-$HOME/fanet-multipath-ns3/src/saqmaodv}"

cd "$NS3_DIR"

echo "=== 1. Copy q-table files into src/saqmaodv/model/ ==="
cp "$SRC_DIR/saqmaodv-qtable.h"  src/saqmaodv/model/
cp "$SRC_DIR/saqmaodv-qtable.cc" src/saqmaodv/model/
echo "  Copied."

echo ""
echo "=== 2. Add to src/saqmaodv/CMakeLists.txt ==="
CMAKE=src/saqmaodv/CMakeLists.txt
if grep -q "saqmaodv-qtable" "$CMAKE"; then
    echo "  Already in CMakeLists.txt, skip."
else
    sed -i 's|model/saqmaodv-rtable.cc|model/saqmaodv-rtable.cc\n    model/saqmaodv-qtable.cc|' "$CMAKE"
    sed -i 's|model/saqmaodv-rtable.h|model/saqmaodv-rtable.h\n    model/saqmaodv-qtable.h|' "$CMAKE"
    echo "  Added."
fi

echo ""
echo "=== 3. Build ==="
./ns3 configure --enable-examples --enable-tests --build-profile=optimized 2>&1 | tail -5
./ns3 build 2>&1 | tail -10

echo "=========================================="
echo "  Phase SAQMAODV-2.2 done."
echo "=========================================="
