#!/usr/bin/env python3
"""
QMAODV Phase 2.3.b — RouteOutput() uses Q-table ε-greedy selection.

Mirrors PMAODV apply-phase-2.3b.py but replaces SelectProbabilisticWithPrimary
with SelectEpsilonGreedy, passing &m_routingTable for Fix-Level-2 validation.

When the Q-table is empty (before 2.3.c/d wire in alternates), the selection
falls through to the primary route → QMAODV behaves identically to AODV.
"""

import os
import shutil
import sys

NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC = os.path.join(NS3, "src/qmaodv/model/qmaodv-routing-protocol.cc")

if not os.path.exists(CC):
    print(f"ERROR: {CC} not found")
    sys.exit(1)

shutil.copy(CC, CC + ".bak-q23b")

with open(CC) as f:
    c = f.read()

if "// QMAODV: ε-greedy selection" in c:
    print("Already applied, skip.")
    sys.exit(0)

old = """    if (m_routingTable.LookupValidRoute(dst, rt))
    {
        route = rt.GetRoute();
        NS_ASSERT(route);"""

new = """    if (m_routingTable.LookupValidRoute(dst, rt))
    {
        // QMAODV: ε-greedy selection over primary + Q-learned alternates.
        // mainTable=&m_routingTable enables Fix-Level-2 nextHop revalidation.
        RoutingTableEntry chosenRt = rt;
        m_qtable.SelectEpsilonGreedy(rt, chosenRt, &m_routingTable);
        route = chosenRt.GetRoute();
        NS_ASSERT(route);"""

if old not in c:
    print("ERROR: RouteOutput primary-lookup pattern not found.")
    print("Pattern expected:")
    print(old)
    sys.exit(1)

c = c.replace(old, new, 1)

with open(CC, "w") as f:
    f.write(c)

print("RouteOutput patched: Q-learning ε-greedy selection wired in.")
print("Run: ./ns3 build")
