#!/usr/bin/env python3
"""
apply-qsaqmaodv-module.py
─────────────────────────────────────────────────────────────────────────────
Creates NS-3 module src/qsaqmaodv/ from SA-QMAODV sources,
replacing only the Q-table with the 4-term reward version.

Usage:
    NS3_DIR=/path/to/ns-3.40 python3 apply-qsaqmaodv-module.py
"""

import os, sys, shutil, re
from pathlib import Path

NS3_DIR  = Path(os.environ.get('NS3_DIR', Path.home() / 'ns-allinone-3.40/ns-3.40'))
PROJ_DIR = Path(__file__).resolve().parents[3]

SRC_SA   = NS3_DIR / 'src' / 'saqmaodv'
DST_QS   = NS3_DIR / 'src' / 'qsaqmaodv'
FILES_DIR = PROJ_DIR / 'paper2-qsaqmaodv' / 'files'

def die(msg): print(f"ERROR: {msg}", file=sys.stderr); sys.exit(1)
def info(msg): print(f"  [qsaqmaodv-module] {msg}")

if not NS3_DIR.exists(): die(f"NS3_DIR not found: {NS3_DIR}")
if not SRC_SA.exists():  die(f"saqmaodv module not found at {SRC_SA}")
if not (FILES_DIR / 'qsaqmaodv-qtable.h').exists():
    die(f"qsaqmaodv-qtable.h not found at {FILES_DIR}")

for sub in ['model', 'helper', 'doc']:
    (DST_QS / sub).mkdir(parents=True, exist_ok=True)

SA_SHARED = [
    'model/saqmaodv-rtable.h',  'model/saqmaodv-rtable.cc',
    'model/saqmaodv-rqueue.h',  'model/saqmaodv-rqueue.cc',
    'model/saqmaodv-packet.h',  'model/saqmaodv-packet.cc',
    'model/saqmaodv-routing-protocol.h', 'model/saqmaodv-routing-protocol.cc',
    'helper/saqmaodv-helper.h', 'helper/saqmaodv-helper.cc',
]

for rel in SA_SHARED:
    src = SRC_SA / rel
    if not src.exists(): continue
    new_name = src.name.replace('saqmaodv', 'qsaqmaodv')
    dst = DST_QS / Path(rel).parent / new_name
    shutil.copy2(src, dst)
    info(f"  copied {rel} → {new_name}")

for fname in ['qsaqmaodv-qtable.h', 'qsaqmaodv-qtable.cc']:
    shutil.copy2(FILES_DIR / fname, DST_QS / 'model' / fname)
    info(f"  copied {fname}")

def patch_file(path):
    text = path.read_text(encoding='utf-8')
    text = text.replace('namespace saqmaodv', 'namespace qsaqmaodv')
    text = text.replace('ns3::saqmaodv::', 'ns3::qsaqmaodv::')
    text = text.replace('SAQMAODV_', 'QSAQMAODV_')
    text = re.sub(r'#include "saqmaodv-qtable\.h"', '#include "qsaqmaodv-qtable.h"', text)
    text = re.sub(r'#include "saqmaodv-', '#include "qsaqmaodv-', text)
    path.write_text(text, encoding='utf-8')

info("Patching namespaces...")
for p in list(DST_QS.rglob('*.cc')) + list(DST_QS.rglob('*.h')):
    patch_file(p)

cmake = """\
build_lib(
  LIBNAME qsaqmaodv
  SOURCE_FILES
    model/qsaqmaodv-rtable.cc
    model/qsaqmaodv-rqueue.cc
    model/qsaqmaodv-packet.cc
    model/qsaqmaodv-qtable.cc
    model/qsaqmaodv-routing-protocol.cc
    helper/qsaqmaodv-helper.cc
  HEADER_FILES
    model/qsaqmaodv-rtable.h
    model/qsaqmaodv-rqueue.h
    model/qsaqmaodv-packet.h
    model/qsaqmaodv-qtable.h
    model/qsaqmaodv-routing-protocol.h
    helper/qsaqmaodv-helper.h
  LIBRARIES_TO_LINK
    ${libcore} ${libnetwork} ${libinternet}
    ${libwifi} ${libenergy} ${libmobility} ${libsaqmaodv}
)
"""
(DST_QS / 'CMakeLists.txt').write_text(cmake)
info("  wrote CMakeLists.txt")

cmake_lists = NS3_DIR / 'CMakeLists.txt'
if cmake_lists.exists():
    content = cmake_lists.read_text()
    if 'src/qsaqmaodv' not in content:
        anchor = 'add_subdirectory(src/saqmaodv)'
        if anchor in content:
            content = content.replace(anchor, anchor + '\nadd_subdirectory(src/qsaqmaodv)')
        else:
            content += '\nadd_subdirectory(src/qsaqmaodv)\n'
        cmake_lists.write_text(content)
        info("  patched top-level CMakeLists.txt")

print("\n✓ qsaqmaodv module created at:", DST_QS)
