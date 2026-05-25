#!/usr/bin/env python3
"""
Phase 2.3.c — Modify RecvRequest để store alternate reverse route từ duplicate RREQ.

Logic (paper Section 3.1):
  Khi RREQ duplicate đến (same origin+id, qua sender khác → reverse path khác):
    AODV gốc: drop ngay.
    PMAODV: nếu m_multipathTable[origin] chưa đầy → add alternate reverse route
            qua sender mới với cost = rreqHeader.GetHopCount() + 1, rồi mới drop.
            (KHÔNG forward duplicate để tránh broadcast storm)

Sau Phase 2.3.c, intermediate nodes sẽ có nhiều reverse path tới origin.
Khi destination send RREP, RREP có thể đi nhiều đường về source → source nhận
nhiều RREP → multiple forward routes ở source (qua RecvReply, chưa modify ở 2.3.c này).
"""

import os
import shutil
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")
CC = os.path.join(NS3, "src/pmaodv/model/pmaodv-routing-protocol.cc")

shutil.copy(CC, CC + ".bak-23c")

with open(CC) as f:
    c = f.read()

if "PMAODV: store alternate reverse route from duplicate RREQ" in c:
    print("Already applied, skip.")
    sys.exit(0)

old = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate");
        return;
    }"""

new = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        // PMAODV: store alternate reverse route from duplicate RREQ.
        // Cùng RREQ đến lần thứ 2+ qua sender khác → đường về origin khác → alternate path.
        if (!m_multipathTable.IsFull(origin))
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
                /*lifetime=*/Time((2 * m_netTraversalTime - 2 * altHop * m_nodeTraversalTime)));
            alt.SetFlag(VALID);
            m_multipathTable.AddRoute(alt);
        }
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate (alt path saved if room)");
        return;
    }"""

if old not in c:
    print("ERROR: Không tìm thấy pattern duplicate-RREQ check.")
    print("Pattern tìm:")
    print(old)
    sys.exit(1)

c = c.replace(old, new, 1)

with open(CC, "w") as f:
    f.write(c)

print("RecvRequest modified for PMAODV multipath reverse routes.")
print("Run: ./ns3 build")
