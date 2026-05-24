#!/usr/bin/env python3
"""
apply-qsaqmaodv-fanet.py
─────────────────────────────────────────────────────────────────────────────
Patches fanet-sim.cc to add QSAQMAODV protocol:
  - Include qsaqmaodv-helper.h
  - CLI args: --qsW4, --qsQueueHigh, --qsQueueLow
  - Protocol block for "QSAQMAODV"

Usage:
    NS3_DIR=/path/to/ns-3.40 python3 apply-qsaqmaodv-fanet.py
"""

import os, sys
from pathlib import Path

NS3_DIR = Path(os.environ.get('NS3_DIR', Path.home() / 'ns-allinone-3.40/ns-3.40'))
FANET   = NS3_DIR / 'scratch' / 'fanet-sim.cc'

def die(msg): print(f"ERROR: {msg}", file=sys.stderr); sys.exit(1)
def info(msg): print(f"  [qsaqmaodv-fanet] {msg}")

if not FANET.exists(): die(f"fanet-sim.cc not found at {FANET}")

text = FANET.read_text(encoding='utf-8')
original = text

# 1. Include
INCLUDE_SA = '#include "ns3/saqmaodv-helper.h"'
INCLUDE_QS = '#include "ns3/qsaqmaodv-helper.h"'
if INCLUDE_QS not in text:
    if INCLUDE_SA in text:
        text = text.replace(INCLUDE_SA, INCLUDE_SA + '\n' + INCLUDE_QS)
        info("Added qsaqmaodv-helper.h include")
    else:
        die(f"Cannot find anchor '{INCLUDE_SA}'")

# 2. CLI args
QS_CLI = '''
  // QS-QMAODV queue-state parameters
  double   qsW4       = 0.2;
  double   qsQueueHigh = 0.7;
  double   qsQueueLow  = 0.3;
  cmd.AddValue ("qsW4",        "QS-QMAODV queue reward weight w4",        qsW4);
  cmd.AddValue ("qsQueueHigh", "QS-QMAODV queue ratio HIGH_LOAD trigger", qsQueueHigh);
  cmd.AddValue ("qsQueueLow",  "QS-QMAODV queue ratio recovery threshold",qsQueueLow);
'''
SA_CLI_ANCHOR = 'cmd.AddValue ("saW3"'
if 'qsW4' not in text:
    if SA_CLI_ANCHOR in text:
        idx = text.find(SA_CLI_ANCHOR)
        line_end = text.find('\n', idx) + 1
        text = text[:line_end] + QS_CLI + text[line_end:]
        info("Added --qsW4 / --qsQueueHigh / --qsQueueLow CLI args")

# 3. Protocol block
if 'protocol == "QSAQMAODV"' not in text:
    saqmaodv_if = text.find('protocol == "SAQMAODV"')
    if saqmaodv_if != -1:
        routing_set = text.find('internet.SetRoutingHelper', saqmaodv_if)
        if routing_set != -1:
            line_end = text.find('\n', routing_set) + 1
            close_brace = text.find('\n  }', line_end)
            if close_brace != -1:
                insert_at = close_brace + 4
                qs_block = (
                    ' else if (protocol == "QSAQMAODV") {\n'
                    '    ns3::qsaqmaodv::QsaqmaodvHelper qsHelper;\n'
                    '    qsHelper.Set ("W4",         DoubleValue (qsW4));\n'
                    '    qsHelper.Set ("QueueHigh",  DoubleValue (qsQueueHigh));\n'
                    '    qsHelper.Set ("QueueLow",   DoubleValue (qsQueueLow));\n'
                    '    qsHelper.Set ("Alpha0",     DoubleValue (saAlpha0));\n'
                    '    qsHelper.Set ("Gamma",      DoubleValue (saGamma));\n'
                    '    qsHelper.Set ("Epsilon0",   DoubleValue (saEpsilon0));\n'
                    '    qsHelper.Set ("Lambda",     DoubleValue (saLambda));\n'
                    '    qsHelper.Set ("W1",         DoubleValue (saW1));\n'
                    '    qsHelper.Set ("W2",         DoubleValue (saW2));\n'
                    '    qsHelper.Set ("W3",         DoubleValue (saW3));\n'
                    '    qsHelper.Set ("MaxPaths",   UintegerValue (maxPaths));\n'
                    '    internet.SetRoutingHelper (qsHelper);\n'
                    '  }'
                )
                text = text[:insert_at] + qs_block + text[insert_at:]
                info("Injected QSAQMAODV protocol block")

if text != original:
    backup = FANET.with_suffix('.cc.bak.qsaqmaodv')
    backup.write_text(original, encoding='utf-8')
    FANET.write_text(text, encoding='utf-8')
    info(f"Patched fanet-sim.cc (backup: {backup.name})")
else:
    info("No changes needed")

print("\n✓ fanet-sim.cc patched for QSAQMAODV")
