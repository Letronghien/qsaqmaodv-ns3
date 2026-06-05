#!/usr/bin/env python3
"""
fix-fanet-sim.py
Hoàn thiện scratch/fanet-sim.cc bị truncate tại dòng "On..." (OnOffHelper).
Chạy trên VM:
    python3 fix-fanet-sim.py
"""
import os, sys

SCRATCH = os.path.expanduser(
    "~/ns-allinone-3.40-qsaqmaodv/ns-3.40/scratch/fanet-sim.cc")
REPO_SRC = os.path.expanduser(
    "~/qsaqmaodv-ns3/src/fanet-sim.cc")

# ---------------------------------------------------------------------------
# Đọc file hiện tại, cắt tại dòng "ApplicationContainer clientApps;"
# (tất cả code trước đó đều đúng)
# ---------------------------------------------------------------------------
with open(SCRATCH, 'r') as f:
    lines = f.readlines()

cut = -1
for i, ln in enumerate(lines):
    if 'ApplicationContainer clientApps;' in ln:
        cut = i

if cut == -1:
    sys.exit("[ERROR] Không tìm thấy 'ApplicationContainer clientApps;'")

kept = lines[:cut + 1]          # giữ nguyên phần tốt
print(f"Giữ {len(kept)} dòng đầu, append phần còn thiếu...")

# ---------------------------------------------------------------------------
# Phần còn thiếu — OnOff apps + FlowMonitor + metrics + CSV + return
# Dựa trên hsaqmaodv/src/fanet-sim.cc (498 dòng, đã verify hoàn chỉnh)
# Điều chỉnh: bỏ energy:: prefix (ns-3.40), thêm QSAQMAODV vào maxPaths cond
# ---------------------------------------------------------------------------
ENDING = r"""  double startBase = 5.0;
  for (size_t i = 0; i < flows.size(); ++i) {
    OnOffHelper onoff("ns3::UdpSocketFactory",
        InetSocketAddress(interfaces.GetAddress(flows[i].dst), port));
    onoff.SetAttribute("DataRate",   StringValue(rateStr.str()));
    onoff.SetAttribute("PacketSize", UintegerValue(pktSize));
    onoff.SetAttribute("OnTime",
        StringValue("ns3::ConstantRandomVariable[Constant=1.0]"));
    onoff.SetAttribute("OffTime",
        StringValue("ns3::ConstantRandomVariable[Constant=0.0]"));
    ApplicationContainer app = onoff.Install(nodes.Get(flows[i].src));
    app.Start(Seconds(startBase + 0.5 * (double)i));
    app.Stop(Seconds(simTime - 1.0));
    clientApps.Add(app);
  }

  // ====== FlowMonitor + overhead counter ======
  FlowMonitorHelper flowMonHelper;
  Ptr<FlowMonitor> monitor = flowMonHelper.InstallAll();

  OverheadCounter* overhead = new OverheadCounter();
  Config::ConnectWithoutContext(
      "/NodeList/*/$ns3::Ipv4L3Protocol/Tx",
      MakeCallback(&OverheadCounter::OnIpTx, overhead));

  // ====== Run ======
  Simulator::Stop(Seconds(simTime + 1.0));
  Simulator::Run();

  // ====== Compute metrics ======
  monitor->CheckForLostPackets();
  Ptr<Ipv4FlowClassifier> classifier =
      DynamicCast<Ipv4FlowClassifier>(flowMonHelper.GetClassifier());
  auto stats = monitor->GetFlowStats();

  uint64_t txPackets = 0, rxPackets = 0, rxBytes = 0;
  double   sumDelay  = 0.0;
  for (auto &kv : stats) {
    Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(kv.first);
    if (t.destinationPort == port) {
      txPackets += kv.second.txPackets;
      rxPackets += kv.second.rxPackets;
      rxBytes   += kv.second.rxBytes;
      sumDelay  += kv.second.delaySum.GetSeconds();
    }
  }

  double   deliveryRatio  = (txPackets > 0) ? (100.0 * rxPackets / txPackets) : 0.0;
  double   avgDelayMs     = (rxPackets > 0) ? (1000.0 * sumDelay  / rxPackets) : 0.0;
  double   throughputMbps = (rxBytes * 8.0) / (simTime * 1.0e6);
  uint64_t routingOverhead = (overhead->ipTxPackets > txPackets)
                               ? (overhead->ipTxPackets - txPackets) : 0;

  double   totalEnergyJ = 0.0;
  uint32_t nodesDead    = 0;
  if (enableEnergy) {
    for (uint32_t i = 0; i < sources.GetN(); ++i) {
      // ns-3.40: BasicEnergySource nằm trong ns3:: trực tiếp (không có energy::)
      Ptr<BasicEnergySource> src =
          DynamicCast<BasicEnergySource>(sources.Get(i));
      if (src) {
        double rem = src->GetRemainingEnergy();
        totalEnergyJ += (initialEnergyJ - rem);
        if (rem <= 0.0) ++nodesDead;
      }
    }
  }

  Simulator::Destroy();
  delete overhead;

  // ====== Console output ======
  std::cout << std::fixed << std::setprecision(4);
  std::cout << " delivery=" << deliveryRatio  << "%"
            << " delay="    << avgDelayMs     << " ms"
            << " thr="      << throughputMbps << " Mbps"
            << " rOver="    << routingOverhead
            << " E="        << totalEnergyJ   << " J"
            << " dead="     << nodesDead << "/" << numNodes
            << std::endl;

  // ====== CSV ======
  struct stat st;
  bool needHeader = (stat(csvFile.c_str(), &st) != 0) || (st.st_size == 0);
  std::ofstream csv(csvFile.c_str(), std::ios::app);
  if (needHeader) {
    csv << "scenario,protocol,mobility,maxPaths,numNodes,numFlows,"
           "meanVelMin,meanVelMax,pktInterval,simTime,seed,"
           "deliveryRatio,avgDelayMs,throughputMbps,"
           "routingOverhead,totalEnergyJ,nodesDead\n";
  }
  csv << scenario   << "," << protocol  << "," << mobility << ","
      << ((protocol == "PMAODV"    || protocol == "AOMDV"     ||
           protocol == "QMAODV"    || protocol == "SAQMAODV"  ||
           protocol == "QSAQMAODV") ? maxPaths : 1)           << ","
      << numNodes   << "," << numFlows  << ","
      << meanVelMin << "," << meanVelMax << "," << pktInterval << ","
      << simTime    << "," << seed      << ","
      << std::fixed << std::setprecision(4)
      << deliveryRatio  << "," << avgDelayMs     << ","
      << throughputMbps << "," << routingOverhead << ","
      << totalEnergyJ   << "," << nodesDead       << "\n";
  csv.close();

  return 0;
}
"""

# ---------------------------------------------------------------------------
# Ghi file hoàn chỉnh
# ---------------------------------------------------------------------------
with open(SCRATCH, 'w') as f:
    f.writelines(kept)
    f.write(ENDING)

total = len(kept) + ENDING.count('\n')
print(f"OK. Tổng ~{total} dòng. Đã ghi: {SCRATCH}")

# Đồng bộ luôn vào repo src/
import shutil
shutil.copy(SCRATCH, REPO_SRC)
print(f"Đã copy sang: {REPO_SRC}")
print()
print("Bước tiếp theo:")
print("  cd ~/ns-allinone-3.40-qsaqmaodv/ns-3.40")
print("  ./ns3 build 2>&1 | tail -10")
