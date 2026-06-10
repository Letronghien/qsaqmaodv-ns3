# EA-QMAODV — Progress Notes
*Cập nhật: 2026-06-10 (phiên 3 — all fixes done, simulations running)*

---

## 1. Tổng quan dự án

**Tên giao thức:** EA-QMAODV (Energy-Aware Self-Adaptive Q-learning Multipath AODV)
*(đổi tên từ QS-QMAODV / QSAQMAODV trong code)*

**Simulator:** NS-3.40 | **Ngôn ngữ:** C++ | **Build profile hiện tại:** optimized

**Hai công thức thay đổi chính:**
```
Fix 1 — Adaptive α (Section 4.4):
  δ_t = |r + γ·maxQ' − Q|              (TD-error tức thời)
  δ̄_t = (1−μ)·δ̄_{t-1} + μ·δ_t         (EMA, μ=0.10)
  α_t = 0.1 + 0.8 · δ̄_t / (δ̄_t + κ)   (rational, κ=0.50)

Fix 2 — Energy penalty (Section 4.2):
  r3 = m_w3 · energyFrac²   (thay vì energyFrac)
```

---

## 2. GitHub Repository

**URL:** https://github.com/Letronghien/qsaqmaodv-ns3
**Repo local trên VM:** `~/qsaqmaodv-ns3/`

### Cấu trúc repo
```
~/qsaqmaodv-ns3/
  src/
    fanet-sim.cc              ← simulation script (copy từ NS-3 scratch/)
    qsaqmaodv/
      model/                  ← toàn bộ model files (đã push)
        qsaqmaodv-qtable.cc/.h
        qsaqmaodv-routing-protocol.cc/.h
        qsaqmaodv-dpd.cc/.h
        qsaqmaodv-neighbor.cc/.h
        qsaqmaodv-id-cache.cc/.h
        qsaqmaodv-packet.cc/.h
        qsaqmaodv-rqueue.cc/.h
        qsaqmaodv-rtable.cc/.h
      helper/
        qsaqmaodv-helper.cc/.h
      CMakeLists.txt
  scripts/
    run/
      run-paper-full.sh       ← Full paper ~1420 runs (5 protocols × 4 families)
      run-ea-rerun.sh         ← EA-QMAODV only ~380 runs
      run-paper-full.sh       ← ✅ đã push
  results/
    logs/                     ← log files per simulation (gitignored *.log)
    results-YYYYMMDD.csv      ← snapshot CSV sau khi hoàn thành
  ~/plot_results.py           ← Python plotting script (chưa push vào repo)
  README.md, notes/, patches/
```

### Commit history quan trọng
```
e570a2d  Add EA-QMAODV source: model + helper + CMakeLists  (19 files)
2c47818  Add paper run scripts: run-paper-full.sh + run-ea-rerun.sh
93ef130  EA-QMAODV: TD-error EMA alpha + E² penalty + w4 queue reward
e936789  (origin/main) Add files via upload
```

### Push workflow khi có data mới
```bash
cd ~/qsaqmaodv-ns3
cp ~/ns-allinone-3.40/ns-3.40/results.csv results/results-$(date +%Y%m%d).csv
git add results/
git commit -m "Add simulation results $(date +%Y-%m-%d): E+ELONG+STAT+W families"
git push origin main
```

---

## 3. Cấu trúc máy chủ VM

```
~/ (tronghien1011@ns3-research)
├── ns-allinone-3.40/ns-3.40/          ← NS-3.40 root (NHIỀU DỰ ÁN DÙNG CHUNG)
│   ├── src/
│   │   ├── qsaqmaodv/                 ← EA-QMAODV module ← CHỈ SỬA FILE NÀY
│   │   ├── saqmaodv/                  ← SA-QMAODV  ← KHÔNG CHẠM
│   │   ├── qmaodv/                    ← QMAODV     ← KHÔNG CHẠM
│   │   ├── aodv/, aomdv/, pmaodv/     ← Baselines  ← KHÔNG CHẠM
│   │   └── hsaqmaodv/                 ← DISABLED (if(FALSE) trong CMakeLists)
│   ├── scratch/fanet-sim.cc           ← Shared sim script (dùng chung mọi protocol)
│   ├── build/scratch/
│   │   ├── ns3.40-fanet-sim-optimized ← Binary chạy sim (profile hiện tại: optimized)
│   │   └── ns3.40-fanet-sim-debug     ← Binary debug
│   ├── results.csv                    ← Output CSV (append mode, TẤT CẢ protocols ghi vào đây)
│   └── CMakeLists.txt line 173: comment out  ← tránh double-add qsaqmaodv
│
├── qsaqmaodv-ns3/                     ← GIT REPO (GitHub backup)
│   └── (xem cấu trúc repo ở mục 2)
│
├── fanet-routing/                     ← Repo cũ (scripts, analysis)
├── PMAODV/, hsaqmaodv-ns3/, qmaodv-ns3/, saqmaodv-ns3/  ← Repos dự án khác
├── qs-qmaodv-ns3/                     ← Repo cũ của dự án này
│
├── run-paper.log                      ← Log toàn bộ sim run
└── plot_results.py                    ← Plotting script
```

### Build commands
```bash
cd ~/ns-allinone-3.40/ns-3.40

# Build optimized (dùng để chạy sim)
./ns3 configure --build-profile=optimized --disable-examples --disable-tests
./ns3 build scratch/fanet-sim

# Build debug (dùng để debug)
./ns3 configure --build-profile=debug --disable-examples --disable-tests
./ns3 build scratch/fanet-sim

# QUAN TRỌNG: sau khi sửa source → phải touch file + rebuild
touch src/qsaqmaodv/helper/qsaqmaodv-helper.cc
./ns3 build scratch/fanet-sim
```

---

## 4. Trạng thái Fix C++ (✅ HOÀN THÀNH)

| File | Thay đổi chính |
|------|----------------|
| `qsaqmaodv-qtable.cc` | `UpdateTdErrorEma()`, E² trong `ComputeReward()`, xóa `wasLowE` dòng 147 |
| `qsaqmaodv-qtable.h` | `m_muTdError{0.10}`, `m_kappaTdError{0.50}`, `m_tdErrorEma{0.0}` |
| `qsaqmaodv-routing-protocol.cc` | Attrs: `MuTdError`, `KappaTdError`, `RewardW4`, `QueueHighThreshold`, `QueueLowThreshold` |
| `qsaqmaodv-routing-protocol.h` | `m_w4{0.2}`, `m_queueHighThresh{0.7}`, `m_queueLowThresh{0.3}` |
| `qsaqmaodv-helper.cc/.h` | Fix namespace: `saqmaodv::` → `qsaqmaodv::` (LỖI CHÍNH gây SIGSEGV) |
| `scratch/fanet-sim.cc` | `qsLambda`→`qsMu`+`qsKappa`; `qsW4`, queue thresholds; `cout.flush()` |
| `src/qsaqmaodv/CMakeLists.txt` | Thêm dpd.cc, neighbor.cc, id-cache.cc |
| `CMakeLists.txt` (root, line 173) | Comment out `add_subdirectory(src/qsaqmaodv)` |
| `src/hsaqmaodv/CMakeLists.txt` | `if(FALSE)` guard (pre-existing broken module) |

### Lỗi quan trọng đã fix
- **SIGSEGV chính**: `qsaqmaodv-helper.cc` dùng `saqmaodv::RoutingProtocol` → null cast → crash. Fix: đổi namespace.
- **Stale optimized library**: Sau khi fix helper, phải `./ns3 configure --build-profile=optimized` để rebuild `libns3.40-qsaqmaodv-optimized.so`.
- **Exit 139 (pre-existing)**: Xảy ra với TẤT CẢ protocols ở destructor `EnergySourceContainer`. CSV đã ghi trước khi crash. Scripts chấp nhận exit 134/139 là OK.

---

## 5. Smoke Test kết quả

| Protocol | N=10 | N=20 | N=50 |
|----------|------|------|------|
| AODV | ✅ exit 0 | ✅ | ✅ |
| QSAQMAODV (EA) | ✅ delivery=44.4% | ✅ delivery=46.8% | ✅ delivery=10.5% |

```
N=10: delivery=44.4444%  delay=220.3676ms  thr=0.0501Mbps  E=254.6602J
N=20: delivery=46.7532%  delay=351.6191ms  thr=0.0985Mbps  E=512.4680J
N=50: delivery=10.5469%  delay=211.1793ms  thr=0.0350Mbps  E=1297.2377J
```

---

## 6. Simulation Scenarios cho Paper

**5 protocols:** AODV, AOMDV, PMAODV, QMAODV, QSAQMAODV(=EA-QMAODV)

| Family | Scenario tag | Điều kiện | Seeds | Protocols | Runs |
|--------|-------------|-----------|-------|-----------|------|
| E | `default` | GAUSS, N=10..50 | 1-36 | 5 | 900 |
| ELONG | `elong` | areaX=3000,areaY=200 | 1-30 | 5 | 150 |
| STAT | `stat` | vel=0 | 1-50 | 5 | 250 |
| W | `ablw1..ablw6` | EA-QMAODV only, N=20 | 1-20 | 1 | 120 |
| **Tổng** | | | | | **~1420** |

**CSV format:** `scenario,protocol,mobility,seed,nodes,flows,velMin,velMax,pktInterval,simTime,pktSize,pdr,delay,thr,overhead,energy,dead`

**Chạy từng family trong tmux:**
```bash
# Session mới
tmux new-session -d -s w-fam

# W trước (120 runs, ~10 phút)
tmux send-keys -t w-fam "bash ~/qsaqmaodv-ns3/scripts/run/run-paper-full.sh 2>&1 | tee ~/run-paper.log" ENTER

# Sau W xong → detach, kiểm tra
tmux attach -t w-fam   # Ctrl+B, D để detach
grep "^abl" ~/ns-allinone-3.40/ns-3.40/results.csv | wc -l   # nên = 120
```

**Thứ tự chạy đề xuất (tránh VM đơ):**
1. W family (120 runs) → plot → kiểm tra
2. STAT family (250 runs)
3. ELONG family (150 runs)
4. E family (900 runs) ← lớn nhất, để cuối

---

## 7. Plot Script

**File:** `~/plot_results.py`

```bash
pip3 install pandas matplotlib --break-system-packages -q
python3 ~/plot_results.py
# Output: ~/plots/*.pdf
```

**Plots được tạo:**
- `E_vs_nodes.pdf` — 4 metrics vs node count, 5 protocol lines
- `W_ablation.pdf` — bar chart 6 weight combos cho EA-QMAODV
- `elong_bar.pdf` — bar chart 5 protocols, elongated topology
- `stat_bar.pdf` — bar chart 5 protocols, static nodes

**Download về máy local:**
```bash
# Từ máy local
scp -r user@VM_IP:~/plots/ ./paper-plots/
# Hoặc dùng Google Cloud Console → Download
```

---

## 8. fanet-sim.cc — Arguments đã confirm

```
--protocol     AODV|AOMDV|PMAODV|QMAODV|SAQMAODV|QSAQMAODV
--numNodes     [10]
--mobility     GAUSS|RWP  [GAUSS]
--simTime      [200]  (dùng 30s cho paper)
--seed         [1]
--scenario     <string> — chỉ là CSV tag, nhận bất kỳ string
--areaX/Y/Z   [1000/1000/300]
--meanVelMin/Max  [15/25]
--qsMu         EMA smoothing μ  [0.10]
--qsKappa      saturation κ  [0.50]
--qsW1/W2/W3/W4  reward weights [0.4/0.3/0.1/0.2]
```

---

## 9. Việc còn lại

- [x] Fix tất cả C++ errors + build
- [x] Smoke test N=10, N=20, N=50
- [x] GitHub backup (source code)
- [x] Tạo run scripts + plot script
- [ ] **Chạy W family** (120 runs) → plot → verify
- [ ] Chạy STAT family (250 runs)
- [ ] Chạy ELONG family (150 runs)
- [ ] Chạy E family (900 runs)
- [ ] Push results.csv lên GitHub
- [ ] Update paper v5.docx với số liệu mới

---

## 10. Ý tưởng Section 4.4

- **Framing**: TD-error = learning progress signal trực tiếp; α cao khi Q-table chưa converge
- **So sánh**: ΔSeq (proxy topological) vs TD-error (proxy learning quality)
- **Stability**: Rational function `δ̄/(δ̄+κ)` — đạo hàm bounded, không discontinuity
- **Half-saturation**: κ=0.5 → khi δ̄=κ thì α=0.5 (điểm trung bình tự nhiên)
- **Citation**: Sutton & Barto (2018) ch.6; Adam optimizer analogy
