# QS-QMAODV — Implementation Guide

## Overview

QS-QMAODV adds exactly **one new reward term** to SA-QMAODV's Q-learning function.
The change is minimal and surgical: only `qsaqmaodv-qtable.cc` differs in core logic
from SA-QMAODV. The bigger engineering challenge is **measuring queue occupancy**
at the next-hop node, which requires a cross-layer callback.

---

## Step 0: Prerequisites

- NS-3.40 installed and built
- SA-QMAODV running (`./ns3 run "fanet-sim --protocol=SAQMAODV"` works)
- Git repo synced

```bash
cd ~/saqmaodv-ns3 && git pull
```

---

## Step 1: Run Patch Scripts

```bash
cd paper2-qsaqmaodv
NS3_DIR=$HOME/ns-allinone-3.40/ns-3.40 bash scripts/patches/apply-qsaqmaodv-all.sh
```

This:
1. Creates `$NS3_DIR/src/qsaqmaodv/` by copying SA-QMAODV sources
2. Replaces `qsaqmaodv-qtable.{h,cc}` with 4-term reward implementation
3. Renames namespaces: `saqmaodv` → `qsaqmaodv`
4. Patches `fanet-sim.cc` to add `QSAQMAODV` protocol + `--qsW4` args

---

## Step 2: Build

```bash
cd $NS3_DIR && ./ns3 build 2>&1 | tail -20
```

---

## Step 3: Smoke Test

```bash
$NS3_DIR/build/scratch/fanet-sim \
  --protocol=QSAQMAODV --maxPaths=3 \
  --numNodes=10 --simTime=60 --seed=1 \
  --qsW4=0.2 --qsQueueHigh=0.7 --qsQueueLow=0.3 \
  --mobility=GAUSS --enableEnergy=1 \
  --pktInterval=0.1 \
  --csvFile=/tmp/qs-smoke.csv
cat /tmp/qs-smoke.csv
```

---

## Step 4: The Core Logic

### 4.1 4-Term Reward

```cpp
double QTable::ComputeReward(double ackSuccess, double delaySec,
                             double energyFrac, double queueRatio) const
{
    return m_w1 * ackSuccess                  // ACK success rate
         + m_w2 * (1.0 / (delaySec + 1.0))   // inverse delay
         + m_w3 * energyFrac                  // residual energy fraction
         + m_w4 * (1.0 / (queueRatio + 1.0)); // inverse queue occupancy (NEW)
}
```

**Intuition for `1/(q+1)`:**
- q = 0.0 (empty queue):  1/(0+1) = 1.0  → reward = w4·1.0  (max bonus)
- q = 0.5 (half full):    1/(0.5+1) ≈ 0.67
- q = 1.0 (full queue):   1/(1+1) = 0.5   → reward = w4·0.5  (halved)
- q → ∞ (overflow):       → 0              (no reward from queue term)

This naturally steers the Q-table away from congested next-hops.

### 4.2 High-Load Mode

```cpp
void QTable::RecomputeAdaptiveRewardWeightsWithQueue(
    double energyFraction, double meanQueueRatio)
{
    // Energy check (same as SA-QMAODV)
    m_lowEnergyMode = (energyFraction < m_lowEnergyThresh);

    // Queue check with hysteresis
    bool wasHighLoad = (m_loadMode == LOAD_HIGH || m_loadMode == LOAD_COMBINED);
    bool highLoad = wasHighLoad
        ? (meanQueueRatio > m_qLowThresh)   // recovery: drop below low threshold
        : (meanQueueRatio > m_qHighThresh);  // trigger: exceed high threshold

    // Set combined mode
    if (m_lowEnergyMode && highLoad)   m_loadMode = LOAD_COMBINED;
    else if (highLoad)                 m_loadMode = LOAD_HIGH;
    else if (m_lowEnergyMode)          m_loadMode = LOAD_LOWENERGY;
    else                               m_loadMode = LOAD_NORMAL;

    ApplyLoadMode();  // set w1-w4 from preset
}
```

**Weight presets:**

| Mode        | w1   | w2   | w3   | w4   | Purpose |
|-------------|------|------|------|------|---------|
| NORMAL      | 0.40 | 0.30 | 0.10 | 0.20 | Balanced |
| LOW_ENERGY  | 0.20 | 0.10 | 0.50 | 0.20 | Energy saving |
| HIGH_LOAD   | 0.30 | 0.20 | 0.10 | **0.40** | Congestion avoidance |
| COMBINED    | 0.20 | 0.10 | 0.35 | **0.35** | Both constraints |

### 4.3 Queue Measurement

The routing protocol needs to know the queue occupancy at each potential
next-hop. Two strategies:

**Strategy A — Local measurement (recommended, simpler):**
Each node measures its *own* queue occupancy and piggybacks it in RREP/HELLO:
```
// In routing protocol, when processing outgoing RREP:
double myQ = GetLocalQueueOccupancy();  // read own DropTailQueue
// Encode in RREP extension header
```

**Strategy B — Cross-layer callback (more accurate):**
```cpp
// Register callback on NetDevice queue
Ptr<Queue<Packet>> q = dev->GetQueue();
q->TraceConnectWithoutContext("Drop",
    MakeCallback(&QsaqmaodvRoutingProtocol::OnQueueDrop, this));
```

**For NS-3.40 implementation:**
The simplest working approach is Strategy A — read the local node's queue
depth and use it as the queue state when updating Q-values after ACK/timeout.

```cpp
// In routing protocol, after receiving ACK for sent packet:
double qRatio = GetLocalQueueOccupancy();  // implemented in routing protocol
m_qtable.UpdateQValue(dst, nextHop, ackSuccess, delay, energy, qRatio);
```

```cpp
double QsaqmaodvRoutingProtocol::GetLocalQueueOccupancy() const
{
    // Use the request queue (saqmaodv-rqueue) as proxy
    uint32_t cur = m_queue.GetSize();
    uint32_t max = m_queue.GetMaxSize();
    if (max == 0) return 0.0;
    return static_cast<double>(cur) / static_cast<double>(max);
}
```

This is not perfectly accurate (measures own queue, not next-hop's) but is:
- Simple to implement
- Zero protocol overhead
- Adequate for Q-learning purposes (correlated with congestion)

---

## Step 5: w4 Calibration

Run the W family to find the best w4:

```bash
FAMILIES="W" SEEDS=5 JOBS=8 bash scripts/run/run-paper2-experiments.sh
python3 scripts/plot/plot-paper2.py ~/results-paper2-*/merged.csv --outdir ./figures
```

Open `figures/fig2_w4_sensitivity.pdf`.

**Expected result:** PDR peaks at w4 ∈ [0.2, 0.3] under high load (pktInterval=0.1).
If the peak is at w4=0.0 (same as SA-QMAODV), the queue measurement is not
working — debug the queue callback.

Update `QS_W4` in the run script and re-run full experiments.

---

## Step 6: Run All Experiments

```bash
# KEY scenario: high-load (pktInterval=0.1)
FAMILIES="L N S E" SEEDS=10 JOBS=8 \
  QS_W4=0.2 QS_Q_HIGH=0.7 QS_Q_LOW=0.3 \
  bash scripts/run/run-paper2-experiments.sh

python3 scripts/plot/plot-paper2.py ~/results-paper2-*/merged.csv --outdir ./figures
```

---

## Step 7: Expected Results

| Family | Expected finding |
|--------|----------------|
| **W**  | Optimal w4 ∈ [0.2,0.3]; PDR peaks above SA-QMAODV baseline |
| **L**  | QS-QMAODV gains over SA-QMAODV grow as pktInterval decreases (↑ load) |
| **N**  | QS benefit increases with N (more nodes → more congestion) |
| **S**  | QS gain is load-driven, not speed-driven (flat across speeds) |
| **E**  | QS-QMAODV ≈ SA-QMAODV in energy metrics (Low-Energy mode unchanged) |

---

## Difference from Paper 1 (H-SAQMAODV)

| Aspect | H-SAQMAODV (Paper 1) | QS-QMAODV (Paper 2) |
|--------|---------------------|---------------------|
| **Core idea** | Skip/switch Q-learning modes | Enrich Q-learning reward |
| **Signal used** | ΔSeq (topology change rate) | Queue occupancy (congestion) |
| **Mechanism** | 3-mode switching in selection | 4th reward term + mode weight |
| **Best scenario** | High mobility (V ≥ 20 m/s) | High traffic load (pkt ≤ 0.1) |
| **Overhead** | O(1) TVI check per packet | O(1) queue read per Q-update |
| **Orthogonal?** | Yes — can combine (Paper 3) | Yes — can combine (Paper 3) |

---

## File Map

```
paper2-qsaqmaodv/
├── files/
│   ├── qsaqmaodv-qtable.h     ← LoadMode enum, 4-term weights, queue tracking
│   └── qsaqmaodv-qtable.cc    ← ComputeReward() with w4, High-Load mode logic
├── scripts/
│   ├── patches/
│   │   ├── apply-qsaqmaodv-all.sh
│   │   ├── apply-qsaqmaodv-module.py
│   │   └── apply-qsaqmaodv-fanet.py
│   ├── run/
│   │   └── run-paper2-experiments.sh
│   └── plot/
│       └── plot-paper2.py
└── notes/
    └── implementation-guide.md  ← This file
```
