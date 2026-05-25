#!/usr/bin/env python3
"""
Fix Phase 2.3.a: Append SetMaxPaths/GetMaxPaths method definitions.

Bug trong apply-phase-2.3a.py: check `"RoutingProtocol::SetMaxPaths" not in c`
quá lỏng — chuỗi này tồn tại sau khi đã thêm vào TypeId attribute
(MakeUintegerAccessor(&RoutingProtocol::SetMaxPaths, ...)), nên append bị skip.

Script này check chính xác bằng pattern method body, và insert TRONG namespace
hiện có thay vì re-open ở cuối file (sạch hơn).
"""

import os
import re
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")
CC = os.path.join(NS3, "src/pmaodv/model/pmaodv-routing-protocol.cc")

with open(CC) as f:
    c = f.read()

# Strict check: look for actual method body, not just qualified name
HAS_DEF = "m_multipathTable.SetMaxPaths(mp);" in c

if HAS_DEF:
    print("Definitions đã có rồi, skip.")
    sys.exit(0)

# Remove any partial/broken append from previous run (re-opened namespace at end)
c = re.sub(
    r"\nnamespace\s+ns3\s*\n\{\s*\nnamespace\s+pmaodv\s*\n\{[\s\S]*?\}\s*//\s*namespace\s+ns3\s*\n*$",
    "",
    c,
)

# The proper place to insert: just before the FINAL "} // namespace pmaodv"
# (so methods are inside the existing pmaodv namespace).
methods = """
void
RoutingProtocol::SetMaxPaths(uint32_t mp)
{
    m_maxPaths = mp;
    m_multipathTable.SetMaxPaths(mp);
}

uint32_t
RoutingProtocol::GetMaxPaths() const
{
    return m_maxPaths;
}

"""

# Find last `} // namespace pmaodv` with flexible spacing/comments
patterns = [
    r"\}\s*//\s*namespace\s+pmaodv\b[^\n]*\n",
    r"\}\s*//\s*pmaodv\b[^\n]*\n",
    r"\}\s*/\*\s*namespace\s+pmaodv[^\n]*\n",
]

match = None
match_pat = None
for pat in patterns:
    matches = list(re.finditer(pat, c))
    if matches:
        match = matches[-1]
        match_pat = pat
        break

if not match:
    # Fallback: append at end with re-opened namespace (less clean but works)
    print("Không tìm thấy '} // namespace pmaodv', dùng fallback append at end")
    c = c.rstrip() + (
        "\n\n"
        "namespace ns3\n"
        "{\n"
        "namespace pmaodv\n"
        "{\n"
        + methods +
        "} // namespace pmaodv\n"
        "} // namespace ns3\n"
    )
else:
    print(f"Insert methods trước line: {c[match.start():match.end()].strip()}")
    c = c[: match.start()] + methods + c[match.start():]

with open(CC, "w") as f:
    f.write(c)

print("Done. SetMaxPaths/GetMaxPaths definitions added.")
print("Run: ./ns3 build")
