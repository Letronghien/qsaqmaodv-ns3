#!/usr/bin/env python3
"""
QMAODV Phase 2.3.a — Wire QTable infrastructure into QmaodvRoutingProtocol.

Mirrors PMAODV apply-phase-2.3a.py with the additional Q-learning attributes
(Alpha, Gamma, Epsilon, W1, W2, EpsilonDecay) needed to drive the Q-table.

Modifies:
  qmaodv-routing-protocol.h:
    + #include "qmaodv-qtable.h"
    + private members:  QTable m_qtable; uint32_t m_maxPaths{3};
                        double m_alpha, m_gamma, m_epsilon, m_w1, m_w2,
                        m_epsilonDecay; Time m_epsilonDecayPeriod;
                        EventId m_epsilonDecayEvent;
    + public methods:   SetMaxPaths / GetMaxPaths,
                        SetQLearningParameters, SetRewardWeights,
                        SetEpsilonDecay, DecayEpsilonHandler.

  qmaodv-routing-protocol.cc:
    + .AddAttribute("MaxPaths", ...) and the six Q-learning attributes
      inside TypeId().
    + Method definitions appended at end of file (in ns3::qmaodv namespace).
    + Schedules DecayEpsilonHandler() from DoInitialize().

Idempotent.
"""

import os
import re
import shutil
import sys

NS3_DIR = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
H_PATH  = os.path.join(NS3_DIR, "src/qmaodv/model/qmaodv-routing-protocol.h")
CC_PATH = os.path.join(NS3_DIR, "src/qmaodv/model/qmaodv-routing-protocol.cc")


def backup(p):
    bp = p + ".bak-q23a"
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"  Backup: {bp}")


def patch_header():
    with open(H_PATH) as f:
        c = f.read()
    orig = c

    # 1. Include
    if "qmaodv-qtable.h" not in c:
        c = c.replace(
            '#include "qmaodv-rtable.h"',
            '#include "qmaodv-rtable.h"\n#include "qmaodv-qtable.h"',
            1,
        )
        print("  + #include qmaodv-qtable.h")

    # 2. Private members after RoutingTable m_routingTable;
    if "QTable m_qtable" not in c:
        c = re.sub(
            r"(RoutingTable\s+m_routingTable;)",
            r"\1\n"
            r"  /// QMAODV: per-node Q-table (alternate routes + Q-values)\n"
            r"  QTable m_qtable;\n"
            r"  /// QMAODV: max routes per dst (set via 'MaxPaths' attribute)\n"
            r"  uint32_t m_maxPaths{3};\n"
            r"  /// QMAODV: Q-learning hyper-parameters (set via attributes)\n"
            r"  double m_alpha{0.5};\n"
            r"  double m_gamma{0.9};\n"
            r"  double m_epsilon{0.5};\n"
            r"  double m_w1{0.6};\n"
            r"  double m_w2{0.4};\n"
            r"  double m_epsilonDecay{0.02};\n"
            r"  Time   m_epsilonDecayPeriod{Seconds(10)};\n"
            r"  EventId m_epsilonDecayEvent;",
            c,
            count=1,
        )
        print("  + private members m_qtable, m_maxPaths, RL hyper-parameters")

    # 3. Public method declarations before first 'private:' inside class RoutingProtocol
    if "SetMaxPaths" not in c:
        pat = re.compile(
            r"(class\s+RoutingProtocol\b[^{]*\{.*?)(\n\s*private:)",
            re.DOTALL,
        )
        m = pat.search(c)
        if m:
            inject = (
                "\n"
                "  /// QMAODV: max paths setter that propagates to QTable\n"
                "  void SetMaxPaths(uint32_t mp);\n"
                "  uint32_t GetMaxPaths() const;\n"
                "  /// QMAODV: configure RL hyper-parameters (α, γ, ε)\n"
                "  void SetQLearningParameters(double alpha, double gamma, double epsilon);\n"
                "  /// QMAODV: configure reward weights w1·ACK + w2·1/(delay+1)\n"
                "  void SetRewardWeights(double w1, double w2);\n"
                "  /// QMAODV: configure ε-decay (amount & period)\n"
                "  void SetEpsilonDecayConfig(double decay, Time period);\n"
                "  /// QMAODV: periodic ε-decay handler\n"
                "  void DecayEpsilonHandler();\n"
            )
            c = c[: m.end(1)] + inject + c[m.end(1):]
            print("  + public decls (SetMaxPaths / Q-learning setters / DecayEpsilonHandler)")
        else:
            print("  ! WARN: class RoutingProtocol anchor not found in .h")
            return False

    if c != orig:
        with open(H_PATH, "w") as f:
            f.write(c)
    else:
        print("  (no header change)")
    return True


def patch_impl():
    with open(CC_PATH) as f:
        c = f.read()
    orig = c

    # 3.5. Make sure ns3/double.h is included (needed for DoubleValue, MakeDoubleAccessor,
    #      MakeDoubleChecker — AODV stock only includes uinteger.h and boolean.h).
    if 'ns3/double.h' not in c:
        # Try common anchors in order of likelihood
        for anchor in [
            '#include "ns3/uinteger.h"',
            '#include "ns3/boolean.h"',
            '#include "ns3/log.h"',
        ]:
            if anchor in c:
                c = c.replace(anchor, anchor + '\n#include "ns3/double.h"', 1)
                print("  + #include ns3/double.h")
                break

    # 4. Add attributes inside TypeId() (after AddConstructor<RoutingProtocol>())
    if '"MaxPaths"' not in c:
        pat = re.compile(r"(\.AddConstructor<RoutingProtocol>\(\))")
        m = pat.search(c)
        if m:
            inject = (
                "\n            "
                '.AddAttribute("MaxPaths",\n'
                '                          "Maximum routes per destination for QMAODV multipath",\n'
                "                          UintegerValue(3),\n"
                "                          MakeUintegerAccessor(&RoutingProtocol::SetMaxPaths,\n"
                "                                               &RoutingProtocol::GetMaxPaths),\n"
                "                          MakeUintegerChecker<uint32_t>(1))\n"
                "            "
                '.AddAttribute("Alpha", "Q-learning learning rate (0..1)",\n'
                "                          DoubleValue(0.5),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_alpha),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("Gamma", "Q-learning discount factor (0..1)",\n'
                "                          DoubleValue(0.9),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_gamma),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("Epsilon", "Initial ε for ε-greedy selection",\n'
                "                          DoubleValue(0.5),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_epsilon),\n"
                "                          MakeDoubleChecker<double>(0.0, 1.0))\n"
                "            "
                '.AddAttribute("RewardW1", "Reward weight for ACK_success",\n'
                "                          DoubleValue(0.6),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_w1),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("RewardW2", "Reward weight for 1/(delay+1)",\n'
                "                          DoubleValue(0.4),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_w2),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("EpsilonDecay", "ε-decay amount per period",\n'
                "                          DoubleValue(0.02),\n"
                "                          MakeDoubleAccessor(&RoutingProtocol::m_epsilonDecay),\n"
                "                          MakeDoubleChecker<double>())\n"
                "            "
                '.AddAttribute("EpsilonDecayPeriod", "Period at which ε is decayed",\n'
                "                          TimeValue(Seconds(10.0)),\n"
                "                          MakeTimeAccessor(&RoutingProtocol::m_epsilonDecayPeriod),\n"
                "                          MakeTimeChecker())"
            )
            c = c[: m.end(1)] + inject + c[m.end(1):]
            print("  + 7 Q-learning attributes registered in TypeId")
        else:
            print("  ! WARN: AddConstructor<RoutingProtocol>() anchor not found")
            return False

    # 5. Schedule decay handler from DoInitialize() (or Start()) — append after first
    #    occurrence of "AODV::DoInitialize" or "RoutingProtocol::DoInitialize".
    if "DecayEpsilonHandler" not in c:
        # try to hook a one-shot setter into Start() if it exists
        anchor_re = re.compile(r"(void\s+RoutingProtocol::Start\s*\(\s*\)\s*\{)", re.M)
        m = anchor_re.search(c)
        if m:
            inject = (
                "\n  // QMAODV: push attribute values into the Q-table and start decay timer.\n"
                "  m_qtable.SetMaxPaths(m_maxPaths);\n"
                "  m_qtable.SetLearningParameters(m_alpha, m_gamma, m_epsilon);\n"
                "  m_qtable.SetRewardWeights(m_w1, m_w2);\n"
                "  m_qtable.SetEpsilonDecay(m_epsilonDecay);\n"
                "  m_epsilonDecayEvent =\n"
                "      Simulator::Schedule(m_epsilonDecayPeriod,\n"
                "                          &RoutingProtocol::DecayEpsilonHandler, this);\n"
            )
            c = c[: m.end(1)] + inject + c[m.end(1):]
            print("  + Q-table init + decay timer scheduled in Start()")
        else:
            print("  ! WARN: RoutingProtocol::Start() anchor not found — decay hook skipped")

    # 6. Append method definitions.
    # NOTE: must use a definition-style anchor (start-of-line `RoutingProtocol::`)
    # — the bare string "RoutingProtocol::SetMaxPaths" already exists in step 4's
    # AddAttribute(MakeUintegerAccessor(&RoutingProtocol::SetMaxPaths, ...)) and
    # would mis-trigger the "already applied" skip otherwise.
    if not re.search(r"^RoutingProtocol::SetMaxPaths\b", c, re.M):
        c += (
            "\n"
            "namespace ns3\n"
            "{\n"
            "namespace qmaodv\n"
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
            "RoutingProtocol::SetQLearningParameters(double alpha, double gamma, double epsilon)\n"
            "{\n"
            "  m_alpha = alpha; m_gamma = gamma; m_epsilon = epsilon;\n"
            "  m_qtable.SetLearningParameters(alpha, gamma, epsilon);\n"
            "}\n"
            "\n"
            "void\n"
            "RoutingProtocol::SetRewardWeights(double w1, double w2)\n"
            "{\n"
            "  m_w1 = w1; m_w2 = w2;\n"
            "  m_qtable.SetRewardWeights(w1, w2);\n"
            "}\n"
            "\n"
            "void\n"
            "RoutingProtocol::SetEpsilonDecayConfig(double decay, Time period)\n"
            "{\n"
            "  m_epsilonDecay = decay; m_epsilonDecayPeriod = period;\n"
            "  m_qtable.SetEpsilonDecay(decay);\n"
            "}\n"
            "\n"
            "void\n"
            "RoutingProtocol::DecayEpsilonHandler()\n"
            "{\n"
            "  m_qtable.DecayEpsilon();\n"
            "  m_epsilonDecayEvent =\n"
            "      Simulator::Schedule(m_epsilonDecayPeriod,\n"
            "                          &RoutingProtocol::DecayEpsilonHandler, this);\n"
            "}\n"
            "\n"
            "} // namespace qmaodv\n"
            "} // namespace ns3\n"
        )
        print("  + Appended method definitions (SetMaxPaths, Q-learning setters, DecayEpsilonHandler)")

    if c != orig:
        with open(CC_PATH, "w") as f:
            f.write(c)
    else:
        print("  (no impl change)")
    return True


def main():
    if not os.path.exists(H_PATH) or not os.path.exists(CC_PATH):
        print(f"ERROR: qmaodv files not found:\n  {H_PATH}\n  {CC_PATH}")
        sys.exit(1)

    print("=== QMAODV Phase 2.3.a: Q-table infrastructure ===\n")
    print("Backing up...")
    backup(H_PATH); backup(CC_PATH); print()

    print("Patching header...")
    if not patch_header():
        print("FAILED"); sys.exit(1)
    print()

    print("Patching implementation...")
    if not patch_impl():
        print("FAILED"); sys.exit(1)

    print("\n=== Done. Run: ./ns3 build ===")


if __name__ == "__main__":
    main()
