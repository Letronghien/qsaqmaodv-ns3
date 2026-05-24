#!/usr/bin/env python3
"""
SAQMAODV Phase 2.3.d — RecvReply hooks:
  (1) Store alternate forward route via SA-Q-table (with EnsureRecord, fix-v2 style)
  (2) Apply positive Q-update with current adaptive (α_t, w_t)
  (3) RECORD SeqNo update event — drives α_t adaptation (§4.3)
"""
import os, shutil, sys
NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC = os.path.join(NS3, "src/saqmaodv/model/saqmaodv-routing-protocol.cc")

if not os.path.exists(CC): print(f"ERROR: {CC}"); sys.exit(1)
shutil.copy(CC, CC + ".bak-sa23d")
with open(CC) as f: c = f.read()

if "SAQMAODV: SA-Q-update on RREP" in c:
    print("Already applied"); sys.exit(0)

old = """    else
    {
        // The forward route for this destination is created if it does not already exist.
        NS_LOG_LOGIC("add new route");
        m_routingTable.AddRoute(newEntry);
    }
    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

new = """    else
    {
        // The forward route for this destination is created if it does not already exist.
        NS_LOG_LOGIC("add new route");
        m_routingTable.AddRoute(newEntry);
    }

    // SAQMAODV: SA-Q-update on RREP + SeqNo tracking.
    {
        // (1) Record destination SeqNo update → drives α_t adaptation (§4.3)
        m_qtable.RecordSeqNoUpdate();
        // (2) Add new route + apply positive Q-update with the current adaptive
        //     α_t and 3-term reward including residual energy fraction.
        double eFrac = GetEnergyFraction();
        m_qtable.UpdateQValueOrCreate(newEntry, /*ack=*/1.0, /*delaySec=*/0.005, eFrac);
    }

    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

if old not in c:
    print("ERROR: RecvReply anchor not found — manual fix may be required"); sys.exit(1)

c = c.replace(old, new, 1)
with open(CC, "w") as f: f.write(c)
print("Patched: SA-Q-update + SeqNo tracking on RREP.")
