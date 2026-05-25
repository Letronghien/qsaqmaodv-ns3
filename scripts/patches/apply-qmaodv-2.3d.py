#!/usr/bin/env python3
"""
QMAODV Phase 2.3.d — RecvReply stores alternate forward route AND fires the
Q-learning update.

Two changes:

(1) In RecvReply, after the stock AODV branch that AddRoutes(newEntry):
      - If newEntry's nextHop differs from current primary's nextHop, add the
        alternate to m_qtable.
      - Compute the one-hop delay observed for this newly-validated path and
        call m_qtable.UpdateQValue(dst, nextHop, ackSuccess=1.0, delaySec).
        The reward formula r = w1·ACK + w2·1/(delay+1) is applied inside the
        Q-table.  RREP arrival is treated as positive feedback (the route just
        proved itself end-to-end).

(2) In RecvError (or whenever a route is invalidated), call
        m_qtable.UpdateQValue(dst, nextHop, ackSuccess=0.0, delaySec=largeDelay)
    so the failed action gets penalised.  We do (2) opportunistically — if the
    RecvError pattern isn't matched, we just skip it (the lifetime+revalidation
    fixes still keep behaviour correct).
"""

import os
import shutil
import sys
import re

NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC  = os.path.join(NS3, "src/qmaodv/model/qmaodv-routing-protocol.cc")

if not os.path.exists(CC):
    print(f"ERROR: {CC} not found")
    sys.exit(1)

shutil.copy(CC, CC + ".bak-q23d")

with open(CC) as f:
    c = f.read()

did_any = False

# ---- (1) RecvReply: add alt + Q-update on successful RREP ----
if "QMAODV: store alternate forward route" in c:
    print("[RecvReply] Already applied.")
else:
    old_rp = """    else
    {
        // The forward route for this destination is created if it does not already exist.
        NS_LOG_LOGIC("add new route");
        m_routingTable.AddRoute(newEntry);
    }
    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

    new_rp = """    else
    {
        // The forward route for this destination is created if it does not already exist.
        NS_LOG_LOGIC("add new route");
        m_routingTable.AddRoute(newEntry);
    }

    // QMAODV: store alternate forward route + apply positive Q-learning update.
    // RREP just proved end-to-end reachability via newEntry.GetNextHop().
    {
        RoutingTableEntry curPrim;
        if (m_routingTable.LookupRoute(dst, curPrim) &&
            curPrim.GetNextHop() != newEntry.GetNextHop())
        {
            m_qtable.AddRoute(newEntry);
        }
        // Reward: ACK_success=1.0, delay = (RREP round-trip / 2) approximation.
        double delaySec = (Simulator::Now() - m_lastBcastTime).GetSeconds() / 2.0;
        if (delaySec < 0.0 || delaySec > 5.0) delaySec = 0.005;   // fallback
        m_qtable.UpdateQValue(dst, newEntry.GetNextHop(), /*ack=*/1.0, delaySec);
    }

    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

    if old_rp not in c:
        print("[RecvReply] ! pattern not matched — skipping (already a different layout?).")
    else:
        c = c.replace(old_rp, new_rp, 1)
        print("[RecvReply] patched: alt store + Q-update.")
        did_any = True

# ---- (2) RecvError: punish failed path ----
if "QMAODV: negative Q-update on RERR" not in c:
    # Heuristic: hook right after the SendRequest()/dropping-route logic in RecvError.
    # We try a couple of common patterns; if none match, this step is silently skipped.
    candidates = [
        ("    m_routingTable.SetEntryState(un.first, INVALID);",
         "    m_routingTable.SetEntryState(un.first, INVALID);\n"
         "    // QMAODV: negative Q-update on RERR (failed path observed).\n"
         "    m_qtable.UpdateQValue(un.first, src, /*ack=*/0.0, /*delaySec=*/5.0);"),
        ("        m_routingTable.SetEntryState(un.first, INVALID);",
         "        m_routingTable.SetEntryState(un.first, INVALID);\n"
         "        // QMAODV: negative Q-update on RERR (failed path observed).\n"
         "        m_qtable.UpdateQValue(un.first, src, /*ack=*/0.0, /*delaySec=*/5.0);"),
    ]
    for a, b in candidates:
        if a in c:
            c = c.replace(a, b, 1)
            print("[RecvError] patched: negative Q-update on RERR.")
            did_any = True
            break
    else:
        print("[RecvError] (no matching pattern) — skip; lifetime + revalidation still apply.")

# ---- Ensure m_lastBcastTime exists ----
if "m_lastBcastTime" not in c:
    # Add member declaration into header AND default-init in constructor.
    H = os.path.join(NS3, "src/qmaodv/model/qmaodv-routing-protocol.h")
    if os.path.exists(H):
        with open(H) as f: h = f.read()
        if "m_lastBcastTime" not in h:
            h = h.replace(
                "EventId m_epsilonDecayEvent;",
                "EventId m_epsilonDecayEvent;\n"
                "  /// QMAODV: last broadcast time (used to estimate RREP RTT)\n"
                "  Time m_lastBcastTime{Seconds(0)};",
                1,
            )
            with open(H, "w") as f: f.write(h)
            print("[hdr] added m_lastBcastTime")

    # Bump m_lastBcastTime when we send an RREQ. Conservative: hook a known
    # broadcast site if present.
    if "// QMAODV: stamp broadcast time" not in c:
        anchor = "socket->SendTo(packet, 0, destination);"
        repl = ("// QMAODV: stamp broadcast time for RREP RTT estimation\n"
                "      m_lastBcastTime = Simulator::Now();\n"
                "      socket->SendTo(packet, 0, destination);")
        if anchor in c:
            c = c.replace(anchor, repl, 1)
            print("[ctrl] stamped m_lastBcastTime on broadcast")

with open(CC, "w") as f:
    f.write(c)

print("Done." if did_any else "Done (nothing matched — verify .cc layout if needed).")
print("Run: ./ns3 build")
