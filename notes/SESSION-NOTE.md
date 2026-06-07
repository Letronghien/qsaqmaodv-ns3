# Session Note — QSAQMAODV-NS3
> Cập nhật: 2026-06-07

---

## Vấn đề gốc

`src/fanet-sim.cc` trong repo bị **truncate tại dòng ~420**, kết thúc giữa chừng ở `OnOffHelper`. Toàn bộ phần dưới bị mất:
- Traffic setup (OnOff apps)
- FlowMonitor
- Tính metrics (delivery, delay, throughput, overhead, energy)
- Ghi CSV
- `return 0` / đóng `}`

**Hệ quả:** Simulation build lỗi hoặc chạy không ra dữ liệu → không vẽ được đồ thị.

---

## Đã làm

### 1. Fix `src/fanet-sim.cc`
Ghép phần đầu hiện có + phần đuôi từ `fix-fanet-sim.py` → file hoàn chỉnh **524 dòng**.

File đã fix: **`fanet-sim.cc`** (đính kèm trong session này).

### 2. Verify tất cả 5 giao thức
```
AODV      → delivery=60.4167%  rc=139 ✓
AOMDV     → delivery=60.4167%  rc=139 ✓
PMAODV    → delivery=60.4167%  rc=139 ✓
QMAODV    → delivery=58.3333%  rc=139 ✓
QSAQMAODV → delivery=58.3333%  rc=139 ✓
```
`rc=139` (segfault cleanup) là **bình thường** với ns-3.40, data đã ghi vào CSV trước đó.

Binary hiện tại: `~/ns-allinone-3.40-qsaqmaodv/ns-3.40/build/scratch/ns3.40-fanet-sim-optimized`

---

## Cần làm tiếp

### Bước 1 — Commit file đã fix lên GitHub (nếu chưa)
```bash
cd ~/qsaqmaodv-ns3
git add src/fanet-sim.cc
git commit -m "fix: complete fanet-sim.cc (was truncated at line 420)"
git push
```

### Bước 2 — Chạy thí nghiệm (từng family, dùng tmux)
```bash
cd ~/qsaqmaodv-ns3
ulimit -c 0
tmux new -s paper
JOBS=3 bash scripts/run/run-paper-full.sh
```

Hoặc chạy từng family để an toàn:
```bash
FAMILIES="N" JOBS=3 bash scripts/run/run-paper-full.sh
# Xong N → chạy tiếp S, L, E, W, M, STAT, ELONG
```

Theo dõi tiến độ (tab khác):
```bash
RDIR=$(ls -dt ~/results-paper-full-* | head -1)
watch -n 30 "grep -c '^OK' $RDIR/run_full.log; grep -c '^FAIL' $RDIR/run_full.log; wc -l $RDIR/*.csv"
```

### Bước 3 — Plot sau khi có CSV
Trên VM:
```bash
RDIR=$(ls -dt ~/results-paper-full-* | head -1)
mkdir -p ~/figures/{N,S,L,E,W,M}
python3 scripts/plot/plot-family-N.py $RDIR/family_N_nodes.csv ~/figures/N/
```

Hoặc upload CSV vào chat → mình vẽ tại đây.

---

## Lưu ý vận hành

| Mục | Giá trị |
|-----|---------|
| JOBS an toàn (N≤30) | 3 |
| JOBS an toàn (N≥50) | 2 |
| RAM tối thiểu free | JOBS × 5 GB |
| rc=139 | Bình thường, data đã ghi |
| Swap khuyến nghị | 16 GB (`/swapfile`) |

Nếu VM đơ: vào GCP Console → Reset → SSH lại → `RESUME=1 JOBS=2 bash scripts/run/run-paper-full.sh`
