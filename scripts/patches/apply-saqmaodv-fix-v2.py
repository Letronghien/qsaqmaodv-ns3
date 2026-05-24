#!/usr/bin/env python3
"""
SAQMAODV fix-v2 — three hooks for the Self-Adaptive Controller:

(A) Per-packet Q-update in RouteOutput (Bug-#2 from QMAODV) — also passes
    current energy fraction so the 3-term reward picks up live battery.
(B) RERR-triggered ε bump (§4.2) — call m_qtable.OnRouteError() from RecvError.
(C) Negative Q-update on RERR for the failed action.
"""
import os, re, shutil, sys
NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC = os.path.join(NS3, "src/saqmaodv/model/saqmaodv-routing-protocol.cc")

if not os.path.exists(CC): print(f"ERROR: {CC}"); sys.exit(1)
shutil.copy(CC, CC + ".bak-safixv2")
with open(CC) as f: c = f.read()
orig = c

# (A) Per-packet update in RouteOutput
if "// SAQMAODV-FIX-V2: per-packet" not in c:
    anchor = "m_qtable.SelectEpsilonGreedy(rt, chosenRt, &m_routingTable);"
    if anchor in c:
        inject = (anchor
            + "\n        // SAQMAODV-FIX-V2: per-packet SA-Q-update with neighbour-freshness reward.\n"
            + "        {\n"
            + "            RoutingTableEntry nbrCheck;\n"
            + "            bool fresh = m_routingTable.LookupRoute(chosenRt.GetNextHop(), nbrCheck)\n"
            + "                         && nbrCheck.GetFlag() == VALID\n"
            + "                         && nbrCheck.GetLifeTime() > Seconds(0);\n"
            + "            double ack    = fresh ? 1.0 : 0.0;\n"
            + "            double delayS = fresh ? 0.005 : 1.0;\n"
            + "            double eFrac  = GetEnergyFraction();\n"
            + "            m_qtable.UpdateQValueOrCreate(chosenRt, ack, delayS, eFrac);\n"
            + "        }"
        )
        c = c.replace(anchor, inject, 1)
        print("  [RouteOutput] + per-packet SA Q-update")
    else:
        print("  ! [RouteOutput] anchor missing (2.3.b not applied?)")

# (B) + (C) RERR hook — bump ε and apply negative Q-update
if "// SAQMAODV-FIX-V2: RERR ε bump" not in c:
    patterns = [
        "    m_routingTable.SetEntryState(un.first, INVALID);",
        "        m_routingTable.SetEntryState(un.first, INVALID);",
    ]
    for p in patterns:
        if p in c:
            new_p = (p +
                "\n    // SAQMAODV-FIX-V2: RERR ε bump (§4.2) + penalty Q-update.\n"
                "    m_qtable.OnRouteError();\n"
                "    m_qtable.UpdateQValue(un.first, src, /*ack=*/0.0,\n"
                "                          /*delaySec=*/5.0, GetEnergyFraction());\n"
            )
            c = c.replace(p, new_p, 1)
            print("  [RecvError] + ε bump + penalty update")
            break
    else:
        print("  [RecvError] no anchor matched (skip)")

if c != orig:
    with open(CC, "w") as f: f.write(c)
    print("Done.")
else:
    print("(no changes)")
