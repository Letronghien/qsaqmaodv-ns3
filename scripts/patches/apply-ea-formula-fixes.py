#!/usr/bin/env python3
"""
apply-ea-formula-fixes.py
=========================
Patches the QSAQMAODV NS-3 module with two EA-QMAODV formula changes:

  Fix 1 (Section 4.4)  — Adaptive α: ΔSeq → TD-error EMA
    OLD:  α_t = 0.1 + 0.8·(1 − exp(−λ·ΔSeq))
    NEW:  δ_t = |r + γ·maxQ − Q|          (TD-error)
          δ̄_t = (1−μ)·δ̄_{t-1} + μ·δ_t   (EMA, μ=0.10)
          α_t = α_min + (α_max−α_min)·δ̄_t/(δ̄_t+κ)  (rational, κ=0.5)

  Fix 2 (Section 4.2)  — Energy term: E → E²
    OLD:  r = w1·ACK + w2·1/(delay+1) + w3·E
    NEW:  r = w1·ACK + w2·1/(delay+1) + w3·E²

Usage:
    # From project root:
    export NS3_DIR=$HOME/ns-allinone-3.40/ns-3.40
    python3 scripts/patches/apply-ea-formula-fixes.py

    # Or override module dir:
    QSAQMAODV_MODEL=/path/to/model python3 scripts/patches/apply-ea-formula-fixes.py
"""
import os, re, shutil, sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
NS3_DIR = os.environ.get("NS3_DIR",
              os.path.expanduser("~/ns-allinone-3.40/ns-3.40"))

# QSAQMAODV model directory inside NS-3 source tree
QSAQMAODV_MODEL = os.environ.get("QSAQMAODV_MODEL",
                      os.path.join(NS3_DIR, "src", "qsaqmaodv", "model"))

QT_H  = os.path.join(QSAQMAODV_MODEL, "qsaqmaodv-qtable.h")
QT_CC = os.path.join(QSAQMAODV_MODEL, "qsaqmaodv-qtable.cc")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def backup(p):
    bp = p + ".bak-ea-fix"
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"  backup -> {os.path.basename(bp)}")

def check_files():
    ok = True
    for p in [QT_H, QT_CC]:
        if not os.path.exists(p):
            print(f"ERROR: not found: {p}")
            ok = False
    if not ok:
        print(f"\nHint: set NS3_DIR or QSAQMAODV_MODEL env var.")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Step 1 — Patch qsaqmaodv-qtable.h
#   • Remove m_lambda + m_seqNoWindow  (ΔSeq tracking no longer needed)
#   • Add    m_tdErrorEma, m_muTdError, m_kappaTdError
#   • Remove RecordSeqNoUpdate / GetDeltaSeq / PurgeSeqNoEvents declarations
#   • Add    UpdateTdErrorEma() declaration
# ---------------------------------------------------------------------------
def patch_header():
    print("\n=== 1. Patch qsaqmaodv-qtable.h ===")
    with open(QT_H) as f:
        c = f.read()
    orig = c
    changed = []

    # 1a. Replace lambda member declaration
    for old, new in [
        # Remove ΔSeq sensitivity λ (replaced by μ and κ)
        ("double      m_lambda;",
         "double      m_muTdError;    ///< EMA smoothing factor μ (default 0.10)\n"
         "  double      m_kappaTdError;  ///< Saturation constant  κ (default 0.50)\n"
         "  double      m_tdErrorEma;   ///< Running EMA of |TD-error|  δ̄_t"),
        # If lambda is written as m_lambda with different spacing, also catch:
        ("double m_lambda;",
         "double m_muTdError;\n"
         "  double m_kappaTdError;\n"
         "  double m_tdErrorEma;"),
    ]:
        if old in c and new not in c:
            c = c.replace(old, new, 1)
            changed.append(f"replaced m_lambda → m_muTdError/m_kappaTdError/m_tdErrorEma")
            break

    # 1b. Replace SetSensitivityLambda declaration → SetTdErrorParams
    for old, new in [
        ("void SetSensitivityLambda(double lambda);",
         "void SetTdErrorParams(double mu, double kappa); ///< Set μ and κ for TD-error EMA"),
        ("void SetSensitivityLambda (double lambda);",
         "void SetTdErrorParams(double mu, double kappa);"),
    ]:
        if old in c:
            c = c.replace(old, new, 1)
            changed.append("replaced SetSensitivityLambda → SetTdErrorParams")
            break

    # 1c. Remove ΔSeq helper declarations (if present)
    for decl in ["void RecordSeqNoUpdate();",
                 "void PurgeSeqNoEvents();",
                 "uint32_t GetDeltaSeq() const;"]:
        if decl in c:
            c = c.replace(decl,
                          "// [EA-fix] removed ΔSeq method: " + decl)
            changed.append(f"commented out: {decl}")

    # 1d. Add UpdateTdErrorEma declaration (before RecomputeAdaptiveAlpha)
    anchor = "void RecomputeAdaptiveAlpha();"
    inject = "void UpdateTdErrorEma(double tdError); ///< Update δ̄_t with new TD-error\n  "
    if anchor in c and "UpdateTdErrorEma" not in c:
        c = c.replace(anchor, inject + anchor, 1)
        changed.append("added UpdateTdErrorEma() declaration")

    # 1e. Remove m_seqEvents deque member (if present)
    for old in [
        "std::deque<Time>  m_seqEvents;",
        "std::deque<Time> m_seqEvents;",
        "std::deque<ns3::Time> m_seqEvents;",
    ]:
        if old in c:
            c = c.replace(old,
                          "// [EA-fix] m_seqEvents removed (ΔSeq tracking replaced by TD-error EMA)")
            changed.append("removed m_seqEvents deque")
            break

    # 1f. Remove SeqNoWindow member (if present; ε still uses seqNo for RERR bumps — keep)
    # NOTE: m_seqNoWindow is used for SeqNo-based epsilon bumps too, so only remove
    #       if it only served alpha adaptation. Check carefully:
    # If the header has a dedicated alpha-only seqNoWindow separate from epsilon seqNo,
    # remove it; otherwise keep. We comment it out safely.
    # (Safe: the CC patch will simply not call the removed methods.)

    if c != orig:
        backup(QT_H)
        with open(QT_H, "w") as f:
            f.write(c)
        for ch in changed:
            print(f"  ✓ {ch}")
    else:
        print("  Already up-to-date (or manual review needed).")

# ---------------------------------------------------------------------------
# Step 2 — Patch qsaqmaodv-qtable.cc
#   Fix 2a: ComputeReward   → E²
#   Fix 1a: RecomputeAdaptiveAlpha → TD-error EMA
#   Fix 1b: Add UpdateTdErrorEma()
#   Fix 1c: Constructor init of new members
#   Fix 1d: UpdateQValue → compute TD-error + call UpdateTdErrorEma
#   Fix 1e: SetSensitivityLambda → SetTdErrorParams
#   Fix 1f: Remove/stub RecordSeqNoUpdate, GetDeltaSeq, PurgeSeqNoEvents
# ---------------------------------------------------------------------------
def patch_impl():
    print("\n=== 2. Patch qsaqmaodv-qtable.cc ===")
    with open(QT_CC) as f:
        c = f.read()
    orig = c
    changed = []

    # ── Fix 2a: ComputeReward E → E² ──────────────────────────────────────
    # Pattern: m_w3 * energyFrac   (may have spaces around *)
    for old, new in [
        ("m_w3 * energyFrac;",           "m_w3 * energyFrac * energyFrac;"),
        ("m_w3 * energyFrac\n",          "m_w3 * energyFrac * energyFrac\n"),
        ("m_w3 * energyFrac ",           "m_w3 * energyFrac * energyFrac "),
        ("m_w3*energyFrac",              "m_w3 * energyFrac * energyFrac"),
    ]:
        if old in c and "energyFrac * energyFrac" not in c:
            c = c.replace(old, new, 1)
            changed.append("Fix2: ComputeReward: E → E²")
            break

    # ── Fix 1e: SetSensitivityLambda → SetTdErrorParams ───────────────────
    old_setter = (
        "void\n"
        "QTable::SetSensitivityLambda(double lambda) { m_lambda = lambda; }"
    )
    new_setter = (
        "void\n"
        "QTable::SetTdErrorParams(double mu, double kappa)\n"
        "{\n"
        "    m_muTdError    = mu;\n"
        "    m_kappaTdError = kappa;\n"
        "}"
    )
    if "SetSensitivityLambda" in c and "SetTdErrorParams" not in c:
        # Try to replace the whole function regardless of exact brace style
        c = re.sub(
            r'void\s+QTable::SetSensitivityLambda\s*\([^)]*\)\s*\{[^}]*\}',
            new_setter,
            c,
            count=1
        )
        changed.append("Fix1e: SetSensitivityLambda → SetTdErrorParams")

    # ── Fix 1f: Stub out ΔSeq helper functions ─────────────────────────────
    for fn_pattern, stub_name in [
        (r'void\s+QTable::RecordSeqNoUpdate\s*\(\)[^}]*\}',
         "RecordSeqNoUpdate"),
        (r'void\s+QTable::PurgeSeqNoEvents\s*\(\)[^}]*\}',
         "PurgeSeqNoEvents"),
        (r'uint32_t\s+QTable::GetDeltaSeq\s*\(\)[^}]*\}',
         "GetDeltaSeq"),
    ]:
        if re.search(fn_pattern, c, re.DOTALL):
            stub = f"// [EA-fix] {stub_name} removed — ΔSeq replaced by TD-error EMA\n"
            c = re.sub(fn_pattern, stub, c, count=1, flags=re.DOTALL)
            changed.append(f"Fix1f: stubbed {stub_name}()")

    # ── Fix 1a: RecomputeAdaptiveAlpha → TD-error version ─────────────────
    new_recompute = '''\
void
QTable::RecomputeAdaptiveAlpha()
{
    // EA-QMAODV Fix 1 (Section 4.4): TD-error EMA drives adaptive α.
    // δ̄_t is maintained by UpdateTdErrorEma() called inside UpdateQValue().
    // α_t = α_min + (α_max − α_min) · δ̄_t / (δ̄_t + κ)
    double newAlpha = 0.1 + 0.8 * m_tdErrorEma / (m_tdErrorEma + m_kappaTdError);
    NS_LOG_DEBUG("QSAQM α (TD-error EMA): δ̄=" << m_tdErrorEma << " → α=" << newAlpha);
    m_alpha = newAlpha;
}
'''
    # Replace entire RecomputeAdaptiveAlpha function
    pattern_rca = (
        r'void\s+QTable::RecomputeAdaptiveAlpha\s*\(\).*?(?=\n(?:void|uint32_t|bool|double|std::|QTable|//\s*={5}|\})\s)'
    )
    if re.search(pattern_rca, c, re.DOTALL):
        c = re.sub(pattern_rca, new_recompute, c, count=1, flags=re.DOTALL)
        changed.append("Fix1a: RecomputeAdaptiveAlpha → TD-error rational formula")
    elif "RecomputeAdaptiveAlpha" in c:
        # Fallback: look for specific old formula text
        old_formula = "0.1 + 0.8 * (1.0 - std::exp(-m_lambda * static_cast<double>(dSeq)))"
        new_formula = "0.1 + 0.8 * m_tdErrorEma / (m_tdErrorEma + m_kappaTdError)"
        if old_formula in c:
            c = c.replace(old_formula, new_formula, 1)
            changed.append("Fix1a (fallback): replaced exponential formula with rational")

    # ── Fix 1b: Add UpdateTdErrorEma() function ────────────────────────────
    if "UpdateTdErrorEma" not in c:
        new_fn = '''\

// EA-QMAODV Fix 1 (Section 4.4): EMA update for TD-error signal.
// Called by UpdateQValue() after each Q-table update.
// δ̄_t = (1−μ)·δ̄_{t-1} + μ·|TD-error|
void
QTable::UpdateTdErrorEma(double tdError)
{
    double absErr = std::fabs(tdError);
    m_tdErrorEma  = (1.0 - m_muTdError) * m_tdErrorEma + m_muTdError * absErr;
    NS_LOG_DEBUG("QSAQM TD-error EMA: |δ|=" << absErr << " δ̄=" << m_tdErrorEma);
}
'''
        # Insert before RecomputeAdaptiveAlpha
        anchor = "void\nQTable::RecomputeAdaptiveAlpha"
        if anchor in c:
            c = c.replace(anchor, new_fn + anchor, 1)
            changed.append("Fix1b: added UpdateTdErrorEma() function")
        else:
            # Append before closing namespace
            marker = "} // namespace qsaqmaodv"
            idx = c.rfind(marker)
            if idx >= 0:
                c = c[:idx] + new_fn + "\n" + c[idx:]
                changed.append("Fix1b: appended UpdateTdErrorEma() (namespace end)")

    # ── Fix 1d: UpdateQValue → compute TD-error + call UpdateTdErrorEma ───
    # We need to inject TD-error computation + EMA update into UpdateQValue.
    # The existing Bellman update: target->qValue = (1-α)*Q + α*(r + γ*maxFuture)
    # After this, compute tdError = |r + γ*maxFuture - oldQ| and call UpdateTdErrorEma.
    bellman_pattern = r'(target->qValue\s*=\s*\(1\.0\s*-\s*m_alpha\)\s*\*\s*oldQ\s*\+\s*m_alpha\s*\*\s*\(reward\s*\+\s*m_gamma\s*\*\s*maxFuture\)\s*;)'
    td_inject = (
        r'\1\n'
        r'    // EA-QMAODV Fix 1: compute TD-error and update EMA for α adaptation\n'
        r'    double tdError = reward + m_gamma * maxFuture - oldQ;\n'
        r'    UpdateTdErrorEma(tdError);\n'
        r'    RecomputeAdaptiveAlpha();'
    )
    if re.search(bellman_pattern, c) and "UpdateTdErrorEma(tdError)" not in c:
        c = re.sub(bellman_pattern, td_inject, c, count=1)
        changed.append("Fix1d: UpdateQValue → computes TD-error + calls UpdateTdErrorEma + RecomputeAdaptiveAlpha")

    # ── Fix 1c: Constructor — init new members ─────────────────────────────
    # Add m_muTdError(0.10), m_kappaTdError(0.5), m_tdErrorEma(0.0) to initialiser list.
    # Find the constructor initialiser list and append.
    ctor_init_pattern = r'(QTable::QTable\s*\([^)]*\)\s*:[^{]*)(m_lambda\s*\([0-9.]+\),?)'
    ctor_replacement  = (
        r'\1'
        r'm_muTdError(0.10),\n'
        r'      m_kappaTdError(0.50),\n'
        r'      m_tdErrorEma(0.0),'
    )
    if re.search(ctor_init_pattern, c, re.DOTALL):
        c = re.sub(ctor_init_pattern, ctor_replacement, c, count=1, flags=re.DOTALL)
        changed.append("Fix1c: constructor init: replaced m_lambda with TD-error members")
    elif "m_tdErrorEma(0.0)" not in c:
        # Fallback: find m_lambda(0.1) and replace
        for old_init in ["m_lambda(0.1),", "m_lambda(0.10),", "m_lambda(0.1),"]:
            if old_init in c:
                c = c.replace(
                    old_init,
                    "m_muTdError(0.10),\n      m_kappaTdError(0.50),\n      m_tdErrorEma(0.0),",
                    1
                )
                changed.append("Fix1c (fallback): replaced m_lambda init in constructor")
                break

    if c != orig:
        backup(QT_CC)
        with open(QT_CC, "w") as f:
            f.write(c)
        for ch in changed:
            print(f"  ✓ {ch}")
    else:
        print("  No changes made — check if already patched or patterns need adjustment.")
        print("  Run with VERBOSE=1 to see diff.")


# ---------------------------------------------------------------------------
# Step 3 — Update fanet-sim.cc: replace qsLambda/qsSeqNoWin flags with qsMu/qsKappa
# ---------------------------------------------------------------------------
def patch_fanet_sim():
    print("\n=== 3. Patch fanet-sim.cc (CLI flags) ===")

    fanet_sim = os.environ.get("FANET_SIM",
                   os.path.join(NS3_DIR, "scratch", "fanet-sim.cc"))
    if not os.path.exists(fanet_sim):
        alt = os.path.join(os.path.dirname(os.path.dirname(
                  os.path.abspath(__file__))), "src", "fanet-sim.cc")
        if os.path.exists(alt):
            fanet_sim = alt
        else:
            print(f"  WARN: fanet-sim.cc not found at {fanet_sim} — skipping.")
            return

    with open(fanet_sim) as f:
        c = f.read()
    orig = c
    changed = []

    # 3a. Add qsMu / qsKappa variable declarations (after qsLambda)
    for old, new in [
        ('double      qsLambda          = 0.1;   // λ in α_t formula\n',
         'double      qsMu              = 0.10;  // μ: EMA smoothing factor for TD-error\n'
         '  double      qsKappa           = 0.50;  // κ: saturation constant (Eq.2c)\n'),
        ('double qsLambda = 0.1;',
         'double qsMu = 0.10;  // EA-QMAODV: μ EMA\n  double qsKappa = 0.50; // EA-QMAODV: κ saturation'),
    ]:
        if old in c and "qsMu" not in c:
            c = c.replace(old, new, 1)
            changed.append("added qsMu, qsKappa variable declarations")
            break

    # 3b. Remove qsSeqNoWin (no longer needed for α, only Lambda matters)
    #     Replace Lambda attribute set call with SetTdErrorParams equivalent
    for old, new in [
        ('qsaqmaodv.Set("Lambda",                DoubleValue(qsLambda));',
         'qsaqmaodv.Set("MuTdError",             DoubleValue(qsMu));\n'
         '      qsaqmaodv.Set("KappaTdError",          DoubleValue(qsKappa));'),
        ('qsaqmaodv.Set("Lambda", DoubleValue(qsLambda));',
         'qsaqmaodv.Set("MuTdError", DoubleValue(qsMu));\n'
         '      qsaqmaodv.Set("KappaTdError", DoubleValue(qsKappa));'),
    ]:
        if old in c and "MuTdError" not in c:
            c = c.replace(old, new, 1)
            changed.append("replaced Lambda set → MuTdError + KappaTdError")
            break

    # 3c. Update cmd.AddValue for Lambda → MuTdError / KappaTdError
    for old, new in [
        ('cmd.AddValue("qsLambda",          "QS-QMAODV sensitivity λ in α_t formula",        qsLambda);',
         'cmd.AddValue("qsMu",              "EA-QMAODV EMA smoothing factor μ (default 0.10)", qsMu);\n'
         '  cmd.AddValue("qsKappa",            "EA-QMAODV saturation constant κ (default 0.50)", qsKappa);'),
    ]:
        if old in c and "qsMu" not in c:
            c = c.replace(old, new, 1)
            changed.append("replaced qsLambda cmd.AddValue → qsMu + qsKappa")
            break

    if c != orig:
        backup(fanet_sim)
        with open(fanet_sim, "w") as f:
            f.write(c)
        for ch in changed:
            print(f"  ✓ {ch}")
    else:
        print("  No changes (already patched or patterns not matched).")


# ---------------------------------------------------------------------------
# Step 4 — Update qsaqmaodv helper to register new attributes
# ---------------------------------------------------------------------------
def patch_helper():
    print("\n=== 4. Patch qsaqmaodv-routing-protocol.cc (NS-3 attributes) ===")

    proto_cc = os.path.join(QSAQMAODV_MODEL, "qsaqmaodv-routing-protocol.cc")
    if not os.path.exists(proto_cc):
        print(f"  WARN: {proto_cc} not found — skipping.")
        return

    with open(proto_cc) as f:
        c = f.read()
    orig = c
    changed = []

    # 4a. Replace Lambda attribute with MuTdError + KappaTdError attributes
    old_attr = (
        '.AddAttribute("Lambda",\n'
        '                    "Sensitivity λ in adaptive α formula",\n'
        '                    DoubleValue(0.1),\n'
        '                    MakeDoubleAccessor(&RoutingProtocol::m_lambda),\n'
        '                    MakeDoubleChecker<double>(0.0))'
    )
    new_attr = (
        '.AddAttribute("MuTdError",\n'
        '                    "EMA smoothing factor μ for TD-error adaptive α (EA-QMAODV §4.4)",\n'
        '                    DoubleValue(0.10),\n'
        '                    MakeDoubleAccessor(&RoutingProtocol::m_muTdError),\n'
        '                    MakeDoubleChecker<double>(0.0, 1.0))\n'
        '        .AddAttribute("KappaTdError",\n'
        '                    "Saturation constant κ in rational α formula (EA-QMAODV §4.4)",\n'
        '                    DoubleValue(0.50),\n'
        '                    MakeDoubleAccessor(&RoutingProtocol::m_kappaTdError),\n'
        '                    MakeDoubleChecker<double>(0.0))'
    )
    if '"Lambda"' in c and '"MuTdError"' not in c:
        # Try exact match first, then fuzzy
        if old_attr in c:
            c = c.replace(old_attr, new_attr, 1)
            changed.append("replaced Lambda NS-3 attribute → MuTdError + KappaTdError")
        else:
            # Fuzzy: find Lambda attribute block
            c = re.sub(
                r'\.AddAttribute\("Lambda".*?MakeDoubleChecker<double>\(\)\)',
                new_attr,
                c, count=1, flags=re.DOTALL
            )
            changed.append("replaced Lambda NS-3 attribute (fuzzy) → MuTdError + KappaTdError")

    # 4b. Replace m_lambda member in RP header propagation to qtable
    for old, new in [
        ('m_qtable.SetSensitivityLambda(m_lambda);',
         'm_qtable.SetTdErrorParams(m_muTdError, m_kappaTdError);'),
        ('m_qtable.SetSensitivityLambda (m_lambda);',
         'm_qtable.SetTdErrorParams(m_muTdError, m_kappaTdError);'),
    ]:
        if old in c:
            c = c.replace(old, new, 1)
            changed.append("replaced SetSensitivityLambda call → SetTdErrorParams")
            break

    if c != orig:
        backup(proto_cc)
        with open(proto_cc, "w") as f:
            f.write(c)
        for ch in changed:
            print(f"  ✓ {ch}")
    else:
        print("  No changes (already patched or patterns not matched).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 62)
    print("  apply-ea-formula-fixes.py")
    print("  Fix 1: Adaptive α  ΔSeq → TD-error EMA (§4.4)")
    print("  Fix 2: Energy term  E → E²              (§4.2)")
    print(f"  NS3_DIR         : {NS3_DIR}")
    print(f"  QSAQMAODV_MODEL : {QSAQMAODV_MODEL}")
    print("=" * 62)

    check_files()
    patch_header()
    patch_impl()
    patch_fanet_sim()
    patch_helper()

    print("\n" + "=" * 62)
    print("  Done. Next steps:")
    print(f"    cd {NS3_DIR}")
    print("    ./ns3 build 2>&1 | tail -5")
    print("    # If build OK, run experiments:")
    print("    bash ~/qsaqmaodv-ns3/scripts/run/run-ea-rerun.sh")
    print("=" * 62)


if __name__ == "__main__":
    main()
