#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply-ea-formula-fixes-v3.py  -  EA-QMAODV formula patch (FINAL)
=================================================================
Exact-string matching based on KNOWN original file content.
NO regex on function bodies. Zero ambiguity.
"""
import os, re, shutil, sys

NS3_DIR  = os.environ.get("NS3_DIR",  os.path.expanduser("~/ns-allinone-3.40/ns-3.40"))
QS_MODEL = os.environ.get("QSAQMAODV_MODEL",
               os.path.join(NS3_DIR, "src", "qsaqmaodv", "model"))

QT_H     = os.path.join(QS_MODEL, "qsaqmaodv-qtable.h")
QT_CC    = os.path.join(QS_MODEL, "qsaqmaodv-qtable.cc")
PROTO_CC = os.path.join(QS_MODEL, "qsaqmaodv-routing-protocol.cc")

def backup(p):
    bp = p + ".bak-ea-v3"
    if not os.path.exists(bp):
        shutil.copy(p, bp)

def rfile(p):
    with open(p, encoding='utf-8') as f:
        return f.read()

def wfile(p, c):
    with open(p, 'w', encoding='utf-8') as f:
        f.write(c)

def exact(c, old, new, label, changed):
    """Exact substring replace - idempotent."""
    if new in c:
        print(f"  (already applied) {label}")
        return c
    if old in c:
        c = c.replace(old, new, 1)
        changed.append(label)
        return c
    first_line = old.split('\n')[0]
    idx = c.find(first_line[:40])
    if idx >= 0:
        print(f"  WARN partial match at {idx}: {repr(c[idx:idx+80])}")
    else:
        print(f"  WARN not found: {label}")
        print(f"    key: {repr(first_line[:60])}")
    return c

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: qsaqmaodv-qtable.cc  (exact matching)
# ─────────────────────────────────────────────────────────────────────────────
def patch_cc():
    print("\n=== 1. qsaqmaodv-qtable.cc ===")
    if not os.path.exists(QT_CC):
        print(f"  ERROR: {QT_CC} not found"); return
    c = rfile(QT_CC)
    orig = c
    changed = []

    # Fix 1c: constructor
    c = exact(c,
        "      m_lambda(0.01),",
        "      m_muTdError(0.10),\n"
        "      m_kappaTdError(0.50),\n"
        "      m_tdErrorEma(0.0),",
        "Fix1c: ctor m_lambda -> TD-error EMA members", changed)

    # Fix 2: E -> E^2
    c = exact(c,
        "    double r3 = m_w3 * energyFrac;",
        "    double r3 = m_w3 * energyFrac * energyFrac;  // EA-Fix2: E^2",
        "Fix2: E -> E^2 in ComputeReward", changed)

    # Fix 1e: SetSensitivityLambda -> SetTdErrorParams
    c = exact(c,
        "void QTable::SetSensitivityLambda(double lambda) { m_lambda = lambda; }",
        "void QTable::SetTdErrorParams(double mu, double kappa)\n"
        "{\n"
        "    m_muTdError    = mu;\n"
        "    m_kappaTdError = kappa;\n"
        "}",
        "Fix1e: SetSensitivityLambda -> SetTdErrorParams", changed)

    # Fix 1a+1b: Replace RecomputeAdaptiveAlpha + add UpdateTdErrorEma
    SENTINEL_NEW  = "m_tdErrorEma / (m_tdErrorEma + m_kappaTdError)"
    LAMBDA_FORMULA = "    m_alpha = 0.1 + 0.8 * (1.0 - std::exp(-m_lambda * static_cast<double>(dseq)));"
    FN_START = "void QTable::RecomputeAdaptiveAlpha()\n{"
    FN_AFTER = "\nvoid QTable::RecomputeAdaptiveRewardWeights"

    if SENTINEL_NEW in c:
        print("  (already applied) Fix1a+1b")
    elif LAMBDA_FORMULA in c:
        idx_start = c.find(FN_START)
        idx_after = c.find(FN_AFTER)
        if idx_start >= 0 and idx_after >= 0 and idx_start < idx_after:
            new_pair = (
                "// EA-QMAODV Fix 1 (Sec.4.4): EMA of |TD-error|.\n"
                "void QTable::UpdateTdErrorEma(double tdError)\n"
                "{\n"
                "    double absErr = std::fabs(tdError);\n"
                "    m_tdErrorEma  = (1.0 - m_muTdError) * m_tdErrorEma + m_muTdError * absErr;\n"
                "}\n"
                "// EA-QMAODV Fix 1 (Sec.4.4): rational alpha from TD-error EMA.\n"
                "void QTable::RecomputeAdaptiveAlpha()\n"
                "{\n"
                "    double newAlpha = 0.1 + 0.8 * m_tdErrorEma / (m_tdErrorEma + m_kappaTdError);\n"
                "    m_alpha = newAlpha;\n"
                "    NS_LOG_DEBUG(\"QS-QTable EA: alpha(TD-EMA)=\" << m_alpha);\n"
                "}"
            )
            c = c[:idx_start] + new_pair + c[idx_after:]
            changed.append("Fix1a+1b: RecomputeAdaptiveAlpha replaced + UpdateTdErrorEma inserted")
        else:
            print(f"  WARN: boundary not found (start={idx_start}, after={idx_after})")
    else:
        print("  WARN: lambda formula not found")

    # Fix 1d: TD-error injection in UpdateQValue
    c = exact(c,
        "        double target = reward + m_gamma * maxNextQ;\n"
        "        rec.qValue    = (1.0 - m_alpha) * rec.qValue + m_alpha * target;",
        "        double oldQ   = rec.qValue;\n"
        "        double target = reward + m_gamma * maxNextQ;\n"
        "        rec.qValue    = (1.0 - m_alpha) * oldQ + m_alpha * target;\n"
        "        // EA-QMAODV Fix 1: TD-error drives adaptive alpha\n"
        "        double tdError = reward + m_gamma * maxNextQ - oldQ;\n"
        "        UpdateTdErrorEma(tdError);\n"
        "        RecomputeAdaptiveAlpha();",
        "Fix1d: UpdateQValue TD-error injection", changed)

    if c != orig:
        backup(QT_CC)
        wfile(QT_CC, c)
        for ch in changed: print(f"  + {ch}")
    else:
        print("  No changes.")

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: qsaqmaodv-qtable.h
# ─────────────────────────────────────────────────────────────────────────────
def patch_header():
    print("\n=== 2. qsaqmaodv-qtable.h ===")
    if not os.path.exists(QT_H):
        print(f"  ERROR: {QT_H} not found"); return
    c = rfile(QT_H)
    orig = c
    changed = []

    # m_lambda -> three TD-error members
    if "m_lambda" in c and "m_muTdError" not in c:
        c2 = re.sub(r'double\s+m_lambda\s*;[^\n]*',
            "double      m_muTdError;    ///< EMA smoothing factor mu  (default 0.10)\n"
            "  double      m_kappaTdError;  ///< Saturation constant  kappa (default 0.50)\n"
            "  double      m_tdErrorEma;   ///< Running EMA of |TD-error|",
            c, count=1)
        if c2 != c:
            c = c2; changed.append("m_lambda -> TD-error EMA members")
        else:
            print("  WARN: m_lambda regex failed")
    elif "m_muTdError" in c:
        print("  (already applied) m_lambda replacement")

    # SetSensitivityLambda decl -> SetTdErrorParams
    if "SetSensitivityLambda" in c and "SetTdErrorParams" not in c:
        c2 = re.sub(r'void\s+SetSensitivityLambda\s*\([^)]*\)\s*;[^\n]*',
            'void SetTdErrorParams(double mu, double kappa);',
            c, count=1)
        if c2 != c:
            c = c2; changed.append("SetSensitivityLambda decl -> SetTdErrorParams")
    elif "SetTdErrorParams" in c:
        print("  (already applied) SetTdErrorParams decl")

    # Add UpdateTdErrorEma declaration
    if "UpdateTdErrorEma" not in c:
        c2 = re.sub(r'(void\s+RecomputeAdaptiveAlpha\s*\(\)\s*;)',
            r'void UpdateTdErrorEma(double tdError);\n  \1',
            c, count=1)
        if c2 != c:
            c = c2; changed.append("added UpdateTdErrorEma() declaration")
        else:
            print("  WARN: RecomputeAdaptiveAlpha decl not found")

    if c != orig:
        backup(QT_H)
        wfile(QT_H, c)
        for ch in changed: print(f"  + {ch}")
    else:
        print("  No changes.")

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: fanet-sim.cc
# ─────────────────────────────────────────────────────────────────────────────
def patch_fanet_sim():
    print("\n=== 3. fanet-sim.cc ===")
    candidates = [
        os.environ.get("FANET_SIM", ""),
        os.path.join(NS3_DIR, "scratch", "fanet-sim.cc"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "src", "fanet-sim.cc"),
    ]
    fpath = next((p for p in candidates if p and os.path.exists(p)), None)
    if not fpath:
        print("  ERROR: not found. Set FANET_SIM=/path/to/fanet-sim.cc"); return
    print(f"  Path: {fpath}")
    c = rfile(fpath)
    orig = c
    changed = []

    if "qsMu" in c:
        print("  Already patched."); return

    # 3a: qsLambda var -> qsMu + qsKappa
    c2 = re.sub(r'[ \t]*double[ \t]+qsLambda[ \t]+=[ \t]+[0-9.]+\s*;[^\n]*\n',
        "  double      qsMu              = 0.10;  // EA: EMA smoothing mu\n"
        "  double      qsKappa           = 0.50;  // EA: saturation kappa\n",
        c, count=1)
    if c2 != c:
        c = c2; changed.append("3a: qsLambda -> qsMu+qsKappa var")
    else:
        print("  WARN 3a: qsLambda var not found")

    # 3b: Set("Lambda") -> Set("MuTdError") + Set("KappaTdError")
    c2 = re.sub(r'[ \t]*qsaqmaodv\.Set\("Lambda"\s*,\s*DoubleValue\(qsLambda\)\)\s*;',
        '      qsaqmaodv.Set("MuTdError",             DoubleValue(qsMu));\n'
        '      qsaqmaodv.Set("KappaTdError",          DoubleValue(qsKappa));',
        c, count=1)
    if c2 != c:
        c = c2; changed.append("3b: Set(Lambda) -> Set(MuTdError)+Set(KappaTdError)")
    else:
        print("  WARN 3b: Set(Lambda) not found")

    # 3c: AddValue("qsLambda") -> AddValue(qsMu)+AddValue(qsKappa)
    c2 = re.sub(r'[ \t]*cmd\.AddValue\("qsLambda"\s*,[^\n]+\n',
        '  cmd.AddValue("qsMu",   "EA-QMAODV EMA smoothing mu (default 0.10)", qsMu);\n'
        '  cmd.AddValue("qsKappa","EA-QMAODV saturation kappa (default 0.50)", qsKappa);\n',
        c, count=1)
    if c2 != c:
        c = c2; changed.append("3c: AddValue(qsLambda) -> qsMu+qsKappa")
    else:
        print("  WARN 3c: AddValue(qsLambda) not found")

    # 3d: cout qsLambda -> qsMu/qsKappa
    c2 = re.sub(r'<< " \S+=" << qsLambda\b',
        '<< " mu=" << qsMu << " kappa=" << qsKappa', c, count=1)
    if c2 != c:
        c = c2; changed.append("3d: cout qsLambda -> qsMu/qsKappa")

    if c != orig:
        backup(fpath)
        wfile(fpath, c)
        for ch in changed: print(f"  + {ch}")
    else:
        print("  No changes.")

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: qsaqmaodv-routing-protocol.cc
# ─────────────────────────────────────────────────────────────────────────────
def patch_routing_protocol():
    print("\n=== 4. qsaqmaodv-routing-protocol.cc ===")
    if not os.path.exists(PROTO_CC):
        print(f"  WARN: not found - skipping."); return
    c = rfile(PROTO_CC)
    orig = c
    changed = []

    if '"Lambda"' in c and '"MuTdError"' not in c:
        new_attrs = (
            '.AddAttribute("MuTdError",\n'
            '                    "EMA smoothing mu for TD-error adaptive alpha",\n'
            '                    DoubleValue(0.10),\n'
            '                    MakeDoubleAccessor(&RoutingProtocol::m_muTdError),\n'
            '                    MakeDoubleChecker<double>(0.0, 1.0))\n'
            '        .AddAttribute("KappaTdError",\n'
            '                    "Saturation kappa in rational alpha formula",\n'
            '                    DoubleValue(0.50),\n'
            '                    MakeDoubleAccessor(&RoutingProtocol::m_kappaTdError),\n'
            '                    MakeDoubleChecker<double>(0.0))'
        )
        c2 = re.sub(r'\.AddAttribute\("Lambda".*?MakeDoubleChecker<double>\s*\([^)]*\)\s*\)',
            new_attrs, c, count=1, flags=re.DOTALL)
        if c2 != c:
            c = c2; changed.append("4a: Lambda attr -> MuTdError+KappaTdError")

    if "m_lambda" in c and "m_muTdError" not in c:
        c2 = re.sub(r'double\s+m_lambda\s*;[^\n]*',
            "double      m_muTdError;\n  double      m_kappaTdError;",
            c, count=1)
        if c2 != c:
            c = c2; changed.append("4b: m_lambda -> m_muTdError/m_kappaTdError in RP")

    for old, new in [
        ("m_qtable.SetSensitivityLambda(m_lambda);",
         "m_qtable.SetTdErrorParams(m_muTdError, m_kappaTdError);"),
        ("m_qtable.SetSensitivityLambda (m_lambda);",
         "m_qtable.SetTdErrorParams(m_muTdError, m_kappaTdError);"),
    ]:
        if old in c:
            c = c.replace(old, new, 1)
            changed.append("4c: SetSensitivityLambda -> SetTdErrorParams"); break

    if c != orig:
        backup(PROTO_CC)
        wfile(PROTO_CC, c)
        for ch in changed: print(f"  + {ch}")
    else:
        print("  No changes.")

# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  apply-ea-formula-fixes-v3.py  (FINAL)")
    print("  Fix 1: alpha: DeltaSeq/lambda -> TD-error EMA")
    print("  Fix 2: reward: E -> E^2")
    print(f"  QS_MODEL: {QS_MODEL}")
    print("=" * 60)

    for p in [QT_H, QT_CC]:
        if not os.path.exists(p):
            print(f"ERROR: {p} not found"); sys.exit(1)

    patch_cc()
    patch_header()
    patch_fanet_sim()
    patch_routing_protocol()

    print("\n" + "=" * 60)
    print("  Done. Build with:")
    print(f"    cd {NS3_DIR}")
    print("    ./ns3 build scratch/fanet-sim 2>&1 | grep 'error:' | head -20")
    print("=" * 60)

if __name__ == "__main__":
    main()
