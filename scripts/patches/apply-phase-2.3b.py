#!/usr/bin/env python3
"""
Phase 2.3.b — Modify RouteOutput() để probabilistic forwarding.

Thay đổi: sau khi lookup primary route, gọi MultipathTable::SelectProbabilisticWithPrimary
để chọn route theo xác suất p_i = (1/HC_i) / Σ(1/HC_k).

Khi MultipathTable chưa có alternate (Phase 2.3.c chưa làm), select trả về primary
→ PMAODV behavior identical AODV. Phase 2.3.c sẽ populate alternates.
"""

import os
import shutil
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")
CC = os.path.join(NS3, "src/pmaodv/model/pmaodv-routing-protocol.cc")

shutil.copy(CC, CC + ".bak-23b")

with open(CC) as f:
    c = f.read()

if "// PMAODV: probabilistic selection" in c:
    print("Already applied, skip.")
    sys.exit(0)

# Match the exact section in RouteOutput where primary is looked up.
# AODV stock pattern:
old = """    if (m_routingTable.LookupValidRoute(dst, rt))
    {
        route = rt.GetRoute();
        NS_ASSERT(route);"""

new = """    if (m_routingTable.LookupValidRoute(dst, rt))
    {
        // PMAODV: probabilistic selection from primary + alternates
        RoutingTableEntry chosenRt = rt;
        m_multipathTable.SelectProbabilisticWithPrimary(rt, chosenRt);
        route = chosenRt.GetRoute();
        NS_ASSERT(route);"""

if old not in c:
    print("ERROR: Không tìm thấy pattern RouteOutput. Có thể format hơi khác.")
    print("Pattern tìm:")
    print(old)
    sys.exit(1)

c = c.replace(old, new, 1)

with open(CC, "w") as f:
    f.write(c)

print("RouteOutput đã modify cho probabilistic forwarding.")
print("Chạy: ./ns3 build")
