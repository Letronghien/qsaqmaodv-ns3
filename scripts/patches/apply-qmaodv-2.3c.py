#!/usr/bin/env python3
"""
QMAODV Phase 2.3.c — RecvRequest stores alternate reverse route from duplicate RREQ.

Identical structure to PMAODV apply-phase-2.3c.py, but stores the alternate in
m_qtable (not m_multipathTable). The Q-table's AddRoute() will automatically
seed an initial Q-value via Eq. 1 of the QMAODV paper (normalized inverse HC).
"""

import os
import shutil
import sys

NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC = os.path.join(NS3, "src/qmaodv/model/qmaodv-routing-protocol.cc")

if not os.path.exists(CC):
    print(f"ERROR: {CC} not found")
    sys.exit(1)

shutil.copy(CC, CC + ".bak-q23c")

with open(CC) as f:
    c = f.read()

if "QMAODV: store alternate reverse route from duplicate RREQ" in c:
    print("Already applied, skip.")
    sys.exit(0)

old = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate");
        return;
    }"""

new = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        // QMAODV: store alternate reverse route from duplicate RREQ.
        // Different sender for the same (origin, id) ⇒ different reverse path
        // ⇒ a new candidate for the Q-table action set.
        if (!m_qtable.IsFull(origin))
        {
            uint8_t altHop = rreqHeader.GetHopCount() + 1;
            Ptr<NetDevice> dev =
                m_ipv4->GetNetDevice(m_ipv4->GetInterfaceForAddress(receiver));
            RoutingTableEntry alt(
                /*dev=*/dev,
                /*dst=*/origin,
                /*vSeqNo=*/true,
                /*seqNo=*/rreqHeader.GetOriginSeqno(),
                /*iface=*/m_ipv4->GetAddress(m_ipv4->GetInterfaceForAddress(receiver), 0),
                /*hops=*/altHop,
                /*nextHop=*/src,
                /*lifetime=*/m_activeRouteTimeout);
            alt.SetFlag(VALID);
            m_qtable.AddRoute(alt);
        }
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate (Q-table alt saved if room)");
        return;
    }"""

if old not in c:
    print("ERROR: duplicate-RREQ check pattern not found.")
    print("Pattern expected:")
    print(old)
    sys.exit(1)

c = c.replace(old, new, 1)

with open(CC, "w") as f:
    f.write(c)

print("RecvRequest patched: alternate reverse route → Q-table.")
print("Run: ./ns3 build")
