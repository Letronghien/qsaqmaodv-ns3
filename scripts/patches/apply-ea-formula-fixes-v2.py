#!/usr/bin/env python3
"""
apply-ea-formula-fixes-v2.py
============================
v2: Robust patterns, diagnostic output, handles partial v1 application.
Fixes missing from v1 run:
  - fanet-sim.cc (Step 3): regex-based, avoids unicode encoding issues
  - qtable.cc  (Step 2): flexible regex for E², constructor, UpdateQValue
  - qtable.h   (Step 1): finish m_lambda → new members replacement

SAFETY: Only modifies qsaqmaodv-* files and the QSAQMAODV block in fanet-sim.cc.
        SA-QMAODV, QMAODV, AODV, AOMDV, PMAODV are NOT touched.

Usage:
    python3 scripts/patches/apply-ea-formula-fixes-v2.py
    VERBOSE=1 python3 scripts/patches/apply-ea-formula-fixes-v2.py
"""
import os, re, shutil, sys

VERBOSE    = os.environ.get("VERBOSE", "1") == "1"
NS3_DIR    = os.environ.get("NS3_DIR", os.path.expanduser("~/ns-allinone-3.40/ns-3.40"))
QS_MODEL   = os.environ.get("QSAQMAODV_MODEL",
                 os.path.join(NS3_DIR, "src", "qsaqmaodv", "model"))

QT_H      = os.path.join(QS_MODEL, "qsaqmaodv-qtable.h")
QT_CC     = os.path.join(QS_MODEL, "qsaqmaodv-qtable.cc")
PROTO_CC  = os.path.join(QS_MODEL, "qsaqmaodv-routing-protocol.cc")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def backup(p):
    bp = p + ".bak-ea-v2"
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"    backup -> {os.path.basename(bp)}")

def v(msg):
    if VERBOSE:
        print(f"    [dbg] {msg}")

def do_replace(c, old, new, label, changed):
    """Exact string replace — idempotent (skip if new already present)."""
    if new in c:
        v(f"skip (already present): {label}")
        return c
    if old in c:
        c = c.replace(old, new, 1)
        changed.append(label)
    else:
        v(f"miss (exact): {label}")
    return c

def do_re(c, pattern, repl, label, changed, flags=re.DOTALL):
    """Regex replace — skip if repl marker already in text."""
    if re.search(pattern, c, flags):
        c2 = re.sub(pattern, repl, c, count=1, flags=flags)
        if c2 != c:
            changed.append(label)
            return c2
        v(f"regex matched but no change: {label}")
    else:
        v(f"miss (regex): {label}  pat={pattern[:60]}")
    return c

# ---------------------------------------------------------------------------
# Step 1 — qsaqmaodv-qtable.h  (finish what v1 missed)
# ---------------------------------------------------------------------------
def patch_header():
    print("\n=== 1. qsaqmaodv-qtable.h ===")
    if not os.path.exists(QT_H):
        print(f"  ERROR: not found: {QT_H}"); return
    with open(QT_H) as f:
        c = f.read()
    orig = c
    changed = []

    # 1a. m_lambda → TD-error members
    if "m_lambda" in c and "m_muTdError" not in c:
        c = do_re(c,
            r'double\s+m_lambda\s*;[^\n]*',
            ('double      m_muTdError;    ///< EMA smoothing factor mu (default 0.10)\n'
             '  double      m_kappaTdError;  ///< Saturation constant  kappa (default 0.50)\n'
             '  double      m_tdErrorEma;   ///< Running EMA of |TD-error|'),
            "m_lambda → m_muTdError/m_kappaTdError/m_tdErrorEma", changed, re.MULTILINE)
    elif "m_muTdError" in c:
        print("  (m_lambda already replaced)")

    # 1b. SetSensitivityLambda declaration → SetTdErrorParams
    if "SetSensitivityLambda" in c and "SetTdErrorParams" not in c:
        c = do_re(c,
            r'void\s+SetSensitivityLambda\s*\([^)]*\)\s*;',
            'void SetTdErrorParams(double mu, double kappa);',
            "SetSensitivityLambda decl → SetTdErrorParams", changed, re.MULTILINE)

    # 1c. UpdateTdErrorEma declaration (before RecomputeAdaptiveAlpha)
    if "UpdateTdErrorEma" not in c:
        c = do_re(c,
            r'(void\s+RecomputeAdaptiveAlpha\s*\(\)\s*;)',
            'void UpdateTdErrorEma(double tdError);\n  \\1',
            "add UpdateTdErrorEma() declaration", changed, re.MULTILINE)

    # 1d. m_seqEvents deque (safe to remove)
    for old in ["std::deque<Time>  m_seqEvents;", "std::deque<Time> m_seqEvents;"]:
        if old in c:
            c = c.replace(old, "// [EA-fix] m_seqEvents removed")
            changed.append("removed m_seqEvents deque"); break

    if c != orig:
        backup(QT_H)
        with open(QT_H, "w") as f: f.write(c)
        for ch in changed: print(f"  ✓ {ch}")
    else:
        print("  Nothing new to patch.")

# ---------------------------------------------------------------------------
# Step 2 — qsaqmaodv-qtable.cc
# ---------------------------------------------------------------------------
def patch_impl():
    print("\n=== 2. qsaqmaodv-qtable.cc ===")
    if not os.path.exists(QT_CC):
        print(f"  ERROR: not found: {QT_CC}"); return
    with open(QT_CC) as f:
        c = f.read()
    orig = c
    changed = []

    # ── Fix 2: E → E² in ComputeReward ────────────────────────────────────
    if "energyFrac * energyFrac" not in c and "EnergyFrac * EnergyFrac" not in c:
        # Try the most common patterns first
        matched = False
        for old, new in [
            ("m_w3 * energyFrac;",    "m_w3 * energyFrac * energyFrac;"),
            ("m_w3 * energyFrac\n",   "m_w3 * energyFrac * energyFrac\n"),
            ("m_w3 * energyFrac ",    "m_w3 * energyFrac * energyFrac "),
            ("m_w3 * energyFrac+",    "m_w3 * energyFrac * energyFrac+"),
            ("m_w3*energyFrac",       "m_w3 * energyFrac * energyFrac"),
        ]:
            if old in c:
                c = c.replace(old, new, 1)
                changed.append("Fix2: E → E² (exact)")
                matched = True; break

        if not matched:
            # Flexible: find any m_w3 * <word> that isn't already squared
            # Restrict to ComputeReward function body
            m = re.search(r'ComputeReward.*?\n\}', c, re.DOTALL)
            if m:
                fn_body = m.group()
                v(f"ComputeReward body snippet: {repr(fn_body[:300])}")
                # Replace m_w3 * <anything> inside ComputeReward
                new_body = re.sub(
                    r'(m_w3\s*\*\s*)(\w+)(?!\s*\*\s*\2)',
                    r'\1\2 * \2',
                    fn_body, count=1
                )
                if new_body != fn_body:
                    c = c.replace(fn_body, new_body, 1)
                    changed.append("Fix2: E → E² (flexible regex in ComputeReward)")
                else:
                    print("  WARN: Fix2 — could not find m_w3 * <energyVar> in ComputeReward")
                    # Last resort: show all m_w3 occurrences for manual review
                    for m2 in re.finditer(r'm_w3[^\n;]+', c):
                        print(f"    m_w3 line: {repr(m2.group())}")
            else:
                print("  WARN: Fix2 — ComputeReward function not found")
    else:
        print("  (Fix2 E² already applied)")

    # ── Fix 1e: SetSensitivityLambda implementation → SetTdErrorParams ────
    if "SetSensitivityLambda" in c and "SetTdErrorParams" not in c:
        c = do_re(c,
            r'void\s+QTable::SetSensitivityLambda\s*\([^)]*\)\s*\{[^}]*\}',
            ('void\n'
             'QTable::SetTdErrorParams(double mu, double kappa)\n'
             '{\n'
             '    m_muTdError    = mu;\n'
             '    m_kappaTdError = kappa;\n'
             '}'),
            "Fix1e: SetSensitivityLambda → SetTdErrorParams", changed)

    # ── Fix 1f: stub ΔSeq helper implementations ─────────────────────────
    for fn_pat, name in [
        (r'void\s+QTable::RecordSeqNoUpdate\s*\(\)[^{]*\{[^}]*\}',  'RecordSeqNoUpdate'),
        (r'void\s+QTable::PurgeSeqNoEvents\s*\(\)[^{]*\{[^}]*\}',   'PurgeSeqNoEvents'),
        (r'uint32_t\s+QTable::GetDeltaSeq\s*\(\)[^{]*\{[^}]*\}',    'GetDeltaSeq'),
    ]:
        if re.search(fn_pat, c, re.DOTALL):
            c = re.sub(fn_pat,
                       f'// [EA-fix] {name} removed — replaced by TD-error EMA',
                       c, count=1, flags=re.DOTALL)
            changed.append(f"Fix1f: stubbed {name}()")

    # ── Fix 1a: RecomputeAdaptiveAlpha → TD-error rational ─────────────
    if "m_tdErrorEma / (m_tdErrorEma + m_kappaTdError)" not in c:
        new_rca = (
            'void\n'
            'QTable::RecomputeAdaptiveAlpha()\n'
            '{\n'
            '    // EA-QMAODV Fix 1 (Section 4.4): TD-error EMA drives adaptive alpha.\n'
            '    // alpha_t = alpha_min + (alpha_max - alpha_min) * delta_bar / (delta_bar + kappa)\n'
            '    double newAlpha = 0.1 + 0.8 * m_tdErrorEma / (m_tdErrorEma + m_kappaTdError);\n'
            '    m_alpha = newAlpha;\n'
            '}\n'
        )
        c = do_re(c,
            r'void\s+QTable::RecomputeAdaptiveAlpha\s*\(\)[^{]*\{.*?\n\}',
            new_rca,
            "Fix1a: RecomputeAdaptiveAlpha → TD-error rational", changed)
        if "Fix1a" not in str(changed):
            # Fallback: just replace the formula line
            c = do_re(c,
                r'0\.1\s*\+\s*0\.8\s*\*\s*\(1\.0\s*-\s*std::exp\([^)]+\)\)',
                '0.1 + 0.8 * m_tdErrorEma / (m_tdErrorEma + m_kappaTdError)',
                "Fix1a fallback: replace exponential formula", changed, re.DOTALL)
    else:
        print("  (Fix1a RecomputeAdaptiveAlpha already patched)")

    # ── Fix 1b: add UpdateTdErrorEma() function ───────────────────────────
    fn_decl = 'QTable::UpdateTdErrorEma'
    if fn_decl not in c:
        new_fn = (
            '\n'
            '// EA-QMAODV Fix 1 (Section 4.4): EMA of |TD-error| for adaptive alpha.\n'
            '// delta_bar_t = (1-mu)*delta_bar_{t-1} + mu*|td_error|\n'
            'void\n'
            'QTable::UpdateTdErrorEma(double tdError)\n'
            '{\n'
            '    double absErr = std::fabs(tdError);\n'
            '    m_tdErrorEma  = (1.0 - m_muTdError) * m_tdErrorEma + m_muTdError * absErr;\n'
            '}\n'
        )
        # Insert immediately before RecomputeAdaptiveAlpha
        anchor = 'void\nQTable::RecomputeAdaptiveAlpha'
        if anchor in c:
            c = c.replace(anchor, new_fn + anchor, 1)
            changed.append("Fix1b: added UpdateTdErrorEma()")
        else:
            # Fallback: before closing namespace
            for ns in ['} // namespace qsaqmaodv', '} //namespace qsaqmaodv']:
                if ns in c:
                    idx = c.rfind(ns)
                    c = c[:idx] + new_fn + '\n' + c[idx:]
                    changed.append("Fix1b: appended UpdateTdErrorEma() at namespace end")
                    break
            else:
                print("  WARN: Fix1b — cannot find anchor to insert UpdateTdErrorEma")

    # ── Fix 1c: constructor init list — replace m_lambda ─────────────────
    if "m_tdErrorEma(0" not in c:
        # Try to find m_lambda(x.x) in constructor initializer
        c2 = re.sub(
            r'\bm_lambda\s*\(\s*[0-9.]+\s*\)\s*,',
            'm_muTdError(0.10),\n      m_kappaTdError(0.50),\n      m_tdErrorEma(0.0),',
            c, count=1
        )
        if c2 != c:
            c = c2
            changed.append("Fix1c: constructor — m_lambda → TD-error members")
        else:
            # Fallback: append new members after last member init before first {
            # Find constructor body start and look for last ,
            m = re.search(r'QTable::QTable\s*\([^)]*\)\s*:\s*([^{]+)\{', c, re.DOTALL)
            if m:
                init_list = m.group(1)
                v(f"constructor init list: {repr(init_list[:200])}")
                if "m_lambda" in init_list:
                    new_init = re.sub(r'\bm_lambda\s*\([^)]*\)',
                        'm_muTdError(0.10),\n      m_kappaTdError(0.50),\n      m_tdErrorEma(0.0)',
                        init_list, count=1)
                    c = c.replace(init_list, new_init, 1)
                    changed.append("Fix1c fallback: constructor init list patched")
                else:
                    print("  WARN: Fix1c — m_lambda not in constructor init list")
                    v(f"init list: {repr(init_list)}")
    else:
        print("  (Fix1c constructor already patched)")

    # ── Fix 1d: UpdateQValue → inject TD-error computation ───────────────
    if "UpdateTdErrorEma(tdError)" not in c:
        # Bellman update patterns (vary by code style)
        bellman_pats = [
            r'(target->qValue\s*=\s*\(1\.0\s*-\s*m_alpha\)\s*\*\s*oldQ\s*\+\s*m_alpha\s*\*\s*\([^;]+\)\s*;)',
            r'(->qValue\s*=\s*\(1[^;]*\)\s*\*[^;]*\+[^;]*reward[^;]+;)',
            r'(qValue\s*=\s*[^;]*\(1\.0\s*-\s*\w+\)[^;]+reward[^;]+;)',
        ]
        inject = (
            '\n    // EA-QMAODV Fix 1: TD-error drives adaptive alpha\n'
            '    double tdError = reward + m_gamma * maxFuture - oldQ;\n'
            '    UpdateTdErrorEma(tdError);\n'
            '    RecomputeAdaptiveAlpha();'
        )
        injected = False
        for pat in bellman_pats:
            m = re.search(pat, c, re.DOTALL)
            if m:
                old_stmt = m.group(1)
                c = c.replace(old_stmt, old_stmt + inject, 1)
                changed.append("Fix1d: UpdateQValue — TD-error injection")
                injected = True; break
        if not injected:
            print("  WARN: Fix1d — Bellman update pattern not found")
            # Show all qValue assignment lines for diagnostics
            for m2 in re.finditer(r'[^\n]*qValue[^\n]*=[^\n]+', c):
                v(f"  qValue line: {repr(m2.group())}")
    else:
        print("  (Fix1d UpdateQValue already patched)")

    if c != orig:
        backup(QT_CC)
        with open(QT_CC, "w") as f: f.write(c)
        for ch in changed: print(f"  ✓ {ch}")
    else:
        print("  Nothing new to patch.")

# ---------------------------------------------------------------------------
# Step 3 — fanet-sim.cc  (complete replacement using regex, avoids unicode)
# ---------------------------------------------------------------------------
def patch_fanet_sim():
    print("\n=== 3. fanet-sim.cc ===")

    # Locate fanet-sim.cc
    candidates = [
        os.environ.get("FANET_SIM", ""),
        os.path.join(NS3_DIR, "scratch", "fanet-sim.cc"),
        # Also look relative to this script (project root src/)
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "src", "fanet-sim.cc"),
    ]
    fanet_sim = next((p for p in candidates if p and os.path.exists(p)), None)
    if not fanet_sim:
        print("  ERROR: fanet-sim.cc not found.  Set FANET_SIM=/path/to/fanet-sim.cc")
        return

    print(f"  Path: {fanet_sim}")
    with open(fanet_sim) as f:
        c = f.read()
    orig = c
    changed = []

    if "qsMu" in c:
        print("  Already patched (qsMu present). Nothing to do.")
        return

    # 3a. Replace qsLambda variable declaration
    #     Pattern avoids matching the unicode lambda comment
    c2 = re.sub(
        r'[ \t]*double[ \t]+qsLambda[ \t]+=[ \t]+[0-9.]+\s*;[^\n]*\n',
        ('  double      qsMu              = 0.10;  // EA: EMA smoothing factor mu\n'
         '  double      qsKappa           = 0.50;  // EA: saturation constant kappa\n'),
        c, count=1
    )
    if c2 != c:
        c = c2; changed.append("3a: qsLambda var → qsMu + qsKappa")
    else:
        print("  WARN: 3a — qsLambda variable declaration not found")
        v(f"  File has 'qsLambda': {'qsLambda' in c}")

    # 3b. Replace qsaqmaodv.Set("Lambda", DoubleValue(qsLambda))
    c2 = re.sub(
        r'[ \t]*qsaqmaodv\.Set\("Lambda"\s*,\s*DoubleValue\(qsLambda\)\)\s*;',
        ('      qsaqmaodv.Set("MuTdError",             DoubleValue(qsMu));\n'
         '      qsaqmaodv.Set("KappaTdError",          DoubleValue(qsKappa));'),
        c, count=1
    )
    if c2 != c:
        c = c2; changed.append("3b: Set(Lambda) → Set(MuTdError) + Set(KappaTdError)")
    else:
        print("  WARN: 3b — qsaqmaodv.Set(Lambda) not found")
        # Diagnostic: look for any Set("Lambda"...
        m = re.search(r'[^\n]*"Lambda"[^\n]*', c)
        if m: v(f"  'Lambda' line: {repr(m.group())}")

    # 3c. Replace cmd.AddValue("qsLambda", ...)
    c2 = re.sub(
        r'[ \t]*cmd\.AddValue\("qsLambda"\s*,[^\n]+\n',
        ('  cmd.AddValue("qsMu",    '
         '"EA-QMAODV EMA smoothing factor mu (default 0.10)", qsMu);\n'
         '  cmd.AddValue("qsKappa", '
         '"EA-QMAODV saturation constant kappa (default 0.50)", qsKappa);\n'),
        c, count=1
    )
    if c2 != c:
        c = c2; changed.append("3c: cmd.AddValue(qsLambda) → qsMu + qsKappa")
    else:
        print("  WARN: 3c — cmd.AddValue(qsLambda) not found")

    # 3d. Update cout print: << " λ=..." << qsLambda  →  qsMu + qsKappa
    c2 = re.sub(
        r'<< " [^\s"=]+="\s*<<\s*qsLambda\b',
        '<< " mu=" << qsMu << " kappa=" << qsKappa',
        c, count=1
    )
    if c2 != c:
        c = c2; changed.append("3d: cout qsLambda → qsMu/qsKappa")

    if c != orig:
        backup(fanet_sim)
        with open(fanet_sim, "w") as f: f.write(c)
        for ch in changed: print(f"  ✓ {ch}")
    else:
        print("  No changes made.")

# ---------------------------------------------------------------------------
# Step 4 — qsaqmaodv-routing-protocol.cc
# ---------------------------------------------------------------------------
def patch_routing_protocol():
    print("\n=== 4. qsaqmaodv-routing-protocol.cc ===")
    if not os.path.exists(PROTO_CC):
        print(f"  WARN: {PROTO_CC} not found — skipping."); return

    with open(PROTO_CC) as f:
        c = f.read()
    orig = c
    changed = []

    # 4a. Replace Lambda NS-3 attribute registration
    if '"Lambda"' in c and '"MuTdError"' not in c:
        new_attr = (
            '.AddAttribute("MuTdError",\n'
            '                    "EMA smoothing factor mu for TD-error adaptive alpha (EA-QMAODV Sec.4.4)",\n'
            '                    DoubleValue(0.10),\n'
            '                    MakeDoubleAccessor(&RoutingProtocol::m_muTdError),\n'
            '                    MakeDoubleChecker<double>(0.0, 1.0))\n'
            '        .AddAttribute("KappaTdError",\n'
            '                    "Saturation constant kappa in rational alpha formula (EA-QMAODV Sec.4.4)",\n'
            '                    DoubleValue(0.50),\n'
            '                    MakeDoubleAccessor(&RoutingProtocol::m_kappaTdError),\n'
            '                    MakeDoubleChecker<double>(0.0))'
        )
        # Chained AddAttribute: match .AddAttribute("Lambda"...) up to end of )
        c2 = re.sub(
            r'\.AddAttribute\("Lambda"[^.]+MakeDoubleChecker<double>\s*\([^)]*\)\s*\)',
            new_attr,
            c, count=1, flags=re.DOTALL
        )
        if c2 != c:
            c = c2; changed.append("4a: Lambda attribute → MuTdError + KappaTdError")
        else:
            print("  WARN: 4a — Lambda attribute regex failed")
            m = re.search(r'[^\n]*"Lambda"[^\n]*', c)
            if m: v(f"  Lambda line: {repr(m.group())}")

    # 4b. Replace m_lambda member in RP class
    if "m_lambda" in c and "m_muTdError" not in c:
        c = do_re(c,
            r'double\s+m_lambda\s*;[^\n]*',
            'double      m_muTdError;    ///< EMA smoothing mu\n  double      m_kappaTdError;  ///< Saturation kappa',
            "4b: m_lambda → m_muTdError/m_kappaTdError in RP", changed, re.MULTILINE)

    # 4c. Replace SetSensitivityLambda call (propagate params to QTable)
    for old, new in [
        ('m_qtable.SetSensitivityLambda(m_lambda);',
         'm_qtable.SetTdErrorParams(m_muTdError, m_kappaTdError);'),
        ('m_qtable.SetSensitivityLambda (m_lambda);',
         'm_qtable.SetTdErrorParams(m_muTdError, m_kappaTdError);'),
    ]:
        if old in c:
            c = c.replace(old, new, 1)
            changed.append("4c: SetSensitivityLambda call → SetTdErrorParams"); break

    if c != orig:
        backup(PROTO_CC)
        with open(PROTO_CC, "w") as f: f.write(c)
        for ch in changed: print(f"  ✓ {ch}")
    else:
        print("  Nothing to patch (already done or patterns not matched).")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  apply-ea-formula-fixes-v2.py")
    print("  Fix 1: Adaptive alpha: DeltaSeq -> TD-error EMA (Sec.4.4)")
    print("  Fix 2: Reward energy term: E -> E^2 (Sec.4.2)")
    print(f"  NS3_DIR  : {NS3_DIR}")
    print(f"  QS_MODEL : {QS_MODEL}")
    print(f"  VERBOSE  : {VERBOSE}")
    print("=" * 60)

    for p in [QT_H, QT_CC]:
        if not os.path.exists(p):
            print(f"ERROR: required file not found: {p}")
            sys.exit(1)

    patch_header()
    patch_impl()
    patch_fanet_sim()
    patch_routing_protocol()

    print("\n" + "=" * 60)
    print("  Done.")
    print()
    print("  If cmake-cache is missing, rebuild with:")
    print(f"    cd {NS3_DIR}")
    print("    ./ns3 configure --enable-optimizations")
    print("    ./ns3 build 2>&1 | tail -20")
    print()
    print("  If cmake-cache exists but Makefile is gone:")
    print(f"    cd {NS3_DIR}/cmake-cache")
    print("    cmake .. && cmake --build . -j 6 2>&1 | tail -20")
    print("=" * 60)

if __name__ == "__main__":
    main()
