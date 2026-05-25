#!/usr/bin/env python3
"""
SAQMAODV Phase 2.3.a — Wire Self-Adaptive QTable into SaqmaodvRoutingProtocol.

Identical pattern to QMAODV 2.3.a but registers the SA-specific attributes:
  - LowEnergyThreshold (default 0.20)
  - SeqNoWindow (default 5s)
  - Lambda — sensitivity in α_t formula (default 0.1)

Also adds the SeqNo-tracking helper called from RecvReply (next phase).
"""
import os, re, shutil, sys

NS3_DIR = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
H  = os.path.join(NS3_DIR, "src/saqmaodv/model/saqmaodv-routing-protocol.h")
CC = os.path.join(NS3_DIR, "src/saqmaodv/model/saqmaodv-routing-protocol.cc")


def backup(p):
    bp = p + ".bak-sa23a"
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"  Backup: {bp}")


def patch_header():
    with open(H) as f: c = f.read()
    orig = c
    if "saqmaodv-qtable.h" not in c:
        c = c.replace('#include "saqmaodv-rtable.h"',
                      '#include "saqmaodv-rtable.h"\n#include "saqmaodv-qtable.h"', 1)
        print("  + #include saqmaodv-qtable.h")
    if "QTable m_qtable" not in c:
        c = re.sub(r"(RoutingTable\s+m_routingTable;)",
                   r"\1\n"
                   r"  /// SAQMAODV: Self-adaptive Q-table\n"
                   r"  QTable m_qtable;\n"
                   r"  /// SAQMAODV: max paths\n"
                   r"  uint32_t m_maxPaths{3};\n"
                   r"  /// SAQMAODV: initial Q-learning params (before adaptation)\n"
                   r"  double m_alpha0{0.5};\n"
                   r"  double m_gamma{0.9};\n"
                   r"  double m_epsilon0{0.3};\n"
                   r"  double m_w1{0.5};\n"
                   r"  double m_w2{0.4};\n"
                   r"  double m_w3{0.1};\n"
                   r"  /// SAQMAODV: adaptive controller params\n"
                   r"  double m_lambda{0.1};\n"
                   r"  Time   m_seqNoWindow{Seconds(5.0)};\n"
                   r"  double m_lowEnergyThreshold{0.20};\n"
                   r"  Time   m_periodicAdaptInterval{Seconds(10.0)};\n"
                   r"  EventId m_periodicAdaptEvent;",
                   c, count=1)
        print("  + private members (m_qtable + adaptive params)")
    if "SetMaxPaths" not in c:
        m = re.compile(r"(class\s+RoutingProtocol\b[^{]*\{.*?)(\n\s*private:)", re.DOTALL).search(c)
        if m:
            inject = ("\n"
                "  /// SAQMAODV: setters\n"
                "  void SetMaxPaths(uint32_t mp);\n"
                "  uint32_t GetMaxPaths() const;\n"
                "  void SetSALearningParams(double alpha0, double gamma, double epsilon0);\n"
                "  void SetSARewardWeights(double w1, double w2, double w3);\n"
                "  void SetSAAdaptiveParams(double lambda, Time seqNoWindow,\n"
                "                           double lowEnergyThreshold, Time periodicInterval);\n"
                "  /// SAQMAODV: periodic adaptation tick (ε-decay + α-recompute + reward-weight update)\n"
                "  void PeriodicAdaptiveTick();\n"
                "  /// SAQMAODV: read residual energy fraction from BasicEnergySource\n"
                "  double GetEnergyFraction() const;\n"
            )
            c = c[: m.end(1)] + inject + c[m.end(1):]
            print("  + public decls (SetMaxPaths + adaptive setters + PeriodicAdaptiveTick + GetEnergyFraction)")
        else:
            print("  ! WARN: anchor not found"); return False
    if c != orig:
        with open(H, "w") as f: f.write(c)
    return True


def patch_impl():
    with open(CC) as f: c = f.read()
    orig = c

    # Make sure ns3/double.h, ns3/energy-module.h are included
    if 'ns3/double.h' not in c:
        for anchor in ['#include "ns3/uinteger.h"', '#include "ns3/boolean.h"', '#include "ns3/log.h"']:
            if anchor in c:
                c = c.replace(anchor, anchor + '\n#include "ns3/double.h"', 1)
                print("  + #include ns3/double.h"); break

    if 'ns3/energy-source-container.h' not in c:
        for anchor in ['#include "ns3/double.h"', '#include "ns3/log.h"']:
            if anchor in c:
                c = c.replace(anchor,
                              anchor + '\n#include "ns3/energy-source-container.h"\n'
                                       '#include "ns3/basic-energy-source.h"', 1)
                print("  + #include ns3/energy headers"); break

    # Attributes
    if '"MaxPaths"' not in c:
        m = re.compile(r"(\.AddConstructor<RoutingProtocol>\(\))").search(c)
        if m:
            inject = ("\n            "
                '.AddAttribute("MaxPaths", "Maximum routes per destination",\n'
                "                          UintegerValue(3),\n"
                "                          MakeUintegerAccessor(&RoutingProtocol::SetMaxPaths,\n"
                "                                               &RoutingProtocol::GetMaxPaths),\n"
                "                          MakeUintegerChecker<uint32_t>(1))\n"
                "            "
                '.AddAttribute("Alpha0", "Initial Q-learning rate (will be adapted)",\n'
                "                          DoubleValue(0.5),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_alpha0),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("Gamma", "Q-learning discount factor",\n'
                "                          DoubleValue(0.9),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_gamma),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("Epsilon0", "Initial ε (will be adapted)",\n'
                "                          DoubleValue(0.3),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_epsilon0),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("RewardW1", "Reward weight for ACK_success",\n'
                "                          DoubleValue(0.5),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_w1),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("RewardW2", "Reward weight for 1/(delay+1)",\n'
                "                          DoubleValue(0.4),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_w2),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("RewardW3", "Reward weight for Energy_residual",\n'
                "                          DoubleValue(0.1),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_w3),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("Lambda", "Sensitivity λ in α_t formula",\n'
                "                          DoubleValue(0.1),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_lambda),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("SeqNoWindow", "Window length for Δ_Seq counting",\n'
                "                          TimeValue(Seconds(5.0)),\n"
                "                          MakeTimeAccessor(&RoutingProtocol::m_seqNoWindow),\n"
                "                          MakeTimeChecker())\n"
                "            "
                '.AddAttribute("LowEnergyThreshold", "Energy fraction triggering low-power weights",\n'
                "                          DoubleValue(0.20),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_lowEnergyThreshold),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("PeriodicAdaptInterval", "Period for ε-decay + α recompute + reward-weight update",\n'
                "                          TimeValue(Seconds(10.0)),\n"
                "                          MakeTimeAccessor(&RoutingProtocol::m_periodicAdaptInterval),\n"
                "                          MakeTimeChecker())"
            )
            c = c[:m.end(1)] + inject + c[m.end(1):]
            print("  + 10 SA attributes registered")
        else:
            print("  ! WARN: AddConstructor anchor missing"); return False

    # Hook in Start(): push initial params + schedule first PeriodicAdaptiveTick
    if "PeriodicAdaptiveTick" not in c:
        m = re.compile(r"(void\s+RoutingProtocol::Start\s*\(\s*\)\s*\{)", re.M).search(c)
        if m:
            inject = ("\n  // SAQMAODV: push initial params + start adaptive controller\n"
                "  m_qtable.SetMaxPaths(m_maxPaths);\n"
                "  m_qtable.SetLearningParameters(m_alpha0, m_gamma, m_epsilon0);\n"
                "  m_qtable.SetRewardWeights(m_w1, m_w2, m_w3);\n"
                "  m_qtable.SetSensitivityLambda(m_lambda);\n"
                "  m_qtable.SetSeqNoWindow(m_seqNoWindow);\n"
                "  m_qtable.SetLowEnergyThreshold(m_lowEnergyThreshold);\n"
                "  m_periodicAdaptEvent =\n"
                "      Simulator::Schedule(m_periodicAdaptInterval,\n"
                "                          &RoutingProtocol::PeriodicAdaptiveTick, this);\n"
            )
            c = c[:m.end(1)] + inject + c[m.end(1):]
            print("  + Q-table init + PeriodicAdaptiveTick scheduled in Start()")
        else:
            print("  ! WARN: Start() anchor missing (decay won't auto-schedule)")

    # Append method definitions
    if not re.search(r"^RoutingProtocol::SetMaxPaths\b", c, re.M):
        c += ("\n"
              "namespace ns3\n"
              "{\n"
              "namespace saqmaodv\n"
              "{\n"
              "\n"
              "void\n"
              "RoutingProtocol::SetMaxPaths(uint32_t mp)\n"
              "{\n"
              "  m_maxPaths = mp;\n"
              "  m_qtable.SetMaxPaths(mp);\n"
              "}\n"
              "\n"
              "uint32_t\n"
              "RoutingProtocol::GetMaxPaths() const\n"
              "{\n"
              "  return m_maxPaths;\n"
              "}\n"
              "\n"
              "void\n"
              "RoutingProtocol::SetSALearningParams(double alpha0, double gamma, double epsilon0)\n"
              "{\n"
              "  m_alpha0 = alpha0; m_gamma = gamma; m_epsilon0 = epsilon0;\n"
              "  m_qtable.SetLearningParameters(alpha0, gamma, epsilon0);\n"
              "}\n"
              "\n"
              "void\n"
              "RoutingProtocol::SetSARewardWeights(double w1, double w2, double w3)\n"
              "{\n"
              "  m_w1 = w1; m_w2 = w2; m_w3 = w3;\n"
              "  m_qtable.SetRewardWeights(w1, w2, w3);\n"
              "}\n"
              "\n"
              "void\n"
              "RoutingProtocol::SetSAAdaptiveParams(double lambda, Time seqNoWindow,\n"
              "                                    double lowEnergyThreshold, Time periodicInterval)\n"
              "{\n"
              "  m_lambda = lambda;\n"
              "  m_seqNoWindow = seqNoWindow;\n"
              "  m_lowEnergyThreshold = lowEnergyThreshold;\n"
              "  m_periodicAdaptInterval = periodicInterval;\n"
              "  m_qtable.SetSensitivityLambda(lambda);\n"
              "  m_qtable.SetSeqNoWindow(seqNoWindow);\n"
              "  m_qtable.SetLowEnergyThreshold(lowEnergyThreshold);\n"
              "}\n"
              "\n"
              "double\n"
              "RoutingProtocol::GetEnergyFraction() const\n"
              "{\n"
              "  // Try to find a BasicEnergySource attached to this node\n"
              "  Ptr<Node> node = m_ipv4 ? m_ipv4->GetObject<Node>() : nullptr;\n"
              "  if (!node) return 1.0;\n"
              "  Ptr<ns3::energy::EnergySourceContainer> esc =\n"
              "      node->GetObject<ns3::energy::EnergySourceContainer>();\n"
              "  if (!esc || esc->GetN() == 0) return 1.0;\n"
              "  Ptr<ns3::energy::BasicEnergySource> src =\n"
              "      DynamicCast<ns3::energy::BasicEnergySource>(esc->Get(0));\n"
              "  if (!src) return 1.0;\n"
              "  double initE = src->GetInitialEnergy();\n"
              "  double remE  = src->GetRemainingEnergy();\n"
              "  return (initE > 0.0) ? std::min(1.0, std::max(0.0, remE / initE)) : 1.0;\n"
              "}\n"
              "\n"
              "void\n"
              "RoutingProtocol::PeriodicAdaptiveTick()\n"
              "{\n"
              "  // (1) Periodic ε decay (§4.2)\n"
              "  m_qtable.PeriodicEpsilonDecay();\n"
              "  // (2) Recompute α_t from Δ_Seq (§4.3)\n"
              "  m_qtable.RecomputeAdaptiveAlpha();\n"
              "  // (3) Update reward weights based on residual energy (§4.4)\n"
              "  m_qtable.RecomputeAdaptiveRewardWeights(GetEnergyFraction());\n"
              "  // Re-arm the timer\n"
              "  m_periodicAdaptEvent =\n"
              "      Simulator::Schedule(m_periodicAdaptInterval,\n"
              "                          &RoutingProtocol::PeriodicAdaptiveTick, this);\n"
              "}\n"
              "\n"
              "} // namespace saqmaodv\n"
              "} // namespace ns3\n")
        print("  + Appended SA method definitions")

    if c != orig:
        with open(CC, "w") as f: f.write(c)
    return True


def main():
    if not os.path.exists(H) or not os.path.exists(CC):
        print(f"ERROR: saqmaodv files missing"); sys.exit(1)
    print("=== SAQMAODV Phase 2.3.a: Self-Adaptive QTable infrastructure ===\n")
    backup(H); backup(CC); print()
    print("Patching header...")
    if not patch_header(): sys.exit(1); print()
    print("Patching implementation...")
    if not patch_impl(): sys.exit(1)
    print("\nDone. Next: 2.3b → 2.3c → 2.3d → adaptive → fix-v2")


if __name__ == "__main__":
    main()
