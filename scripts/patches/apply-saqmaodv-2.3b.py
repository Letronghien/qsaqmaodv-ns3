#!/usr/bin/env python3
"""SAQMAODV Phase 2.3.b — RouteOutput uses ε-greedy from SA-Q-Table."""
import os, shutil, sys
NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC = os.path.join(NS3, "src/saqmaodv/model/saqmaodv-routing-protocol.cc")

if not os.path.exists(CC): print(f"ERROR: {CC} not found"); sys.exit(1)
shutil.copy(CC, CC + ".bak-sa23b")
with open(CC) as f: c = f.read()

if "// SAQMAODV: ε-greedy" in c:
    print("Already applied"); sys.exit(0)

old = """    if (m_routingTable.LookupValidRoute(dst, rt))
    {
        route = rt.GetRoute();
        NS_ASSERT(route);"""

new = """    if (m_routingTable.LookupValidRoute(dst, rt))
    {
        // SAQMAODV: ε-greedy selection over primary + SA-Q-learned alternates.
        RoutingTableEntry chosenRt = rt;
        m_qtable.SelectEpsilonGreedy(rt, chosenRt, &m_routingTable);
        route = chosenRt.GetRoute();
        NS_ASSERT(route);"""

if old not in c:
    print("ERROR: anchor not found"); sys.exit(1)
c = c.replace(old, new, 1)
with open(CC, "w") as f: f.write(c)
print("Patched.")
