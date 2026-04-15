# Teaching Quickstart

## Purpose

This is the fastest classroom runbook for the current project.

Use this when you want to **open the project and demo the most important 5G PHY concepts in order**, without reading the longer teaching documents first.

Project root:

```powershell
cd D:\Data\Lectures\20252\MobiCom\Codex\5GNRPHYSITL\5gnr_phy_stl
```

Recommended interpreter:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe
```

---

## Demo Order

### 1. Open the default GUI

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --gui
```

Use this to introduce:

- GUI layout
- `Run`
- `Step Mode`
- `Capture slots`
- `PHY Pipeline`

### 2. Walk the end-to-end downlink PHY chain

Inside the GUI:

- `Direction = downlink`
- `Mode = data`
- `Modulation = QPSK`
- `Channel model = awgn`
- `SNR = 20 dB`
- `Capture slots = 1`
- `Perfect sync = On`
- `Perfect CE = On`

Then click:

- `Step Mode`

Focus on:

- `Traffic / transport block`
- `TB CRC attachment`
- `Channel coding`
- `QAM mapping`
- `Resource Grid + RS`
- `OFDM / IFFT + CP`
- `Timing / CFO correction`
- `Channel estimation`
- `Equalization`
- `Soft LLR before decoding`
- `CRC check`

### 3. Show downlink control and broadcast structure

Downlink control:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --channel-type control --gui
```

PBCH / SSB:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_pbch_baseline.yaml --gui
```

Focus on:

- `CORESET / SearchSpace`
- `SSB / PBCH Broadcast Layout`
- `DM-RS`
- `PBCH-DMRS`
- `CSI-RS`
- `PT-RS`

### 4. Show uplink data and uplink control

Uplink data:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_uplink_baseline.yaml --gui
```

Uplink control:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_uplink_control_baseline.yaml --gui
```

Focus on:

- `PUSCH-style`
- `PUCCH-style`
- optional `Transform precoding`
- `SRS`

### 5. Show PRACH as a detection problem

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_uplink_prach_baseline.yaml --gui
```

Focus on:

- preamble generation
- correlation detection
- detected preamble ID

### 6. Show ideal vs realistic receiver behavior

Open the default GUI again:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --gui
```

Run twice:

1. with
   - `Perfect sync = On`
   - `Perfect CE = On`
2. with
   - `Perfect sync = Off`
   - `Perfect CE = Off`

Then vary:

- `CFO`
- `STO`
- `phase noise`

If you want a harder channel:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml --gui
```

### 7. Show file transfer over PHY

Text:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_text_transfer.yaml --gui
```

Image:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_image_transfer.yaml --gui
```

Focus on:

- `File Source + Packaging`
- PHY transport stages
- `File Reassembly + Write`
- why large files are more fragile at lower SNR

### 8. Show SU-MIMO baseline

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe main.py --config configs/default.yaml --override configs/scenario_su_mimo_two_codeword.yaml --gui
```

Focus on:

- `Codeword Split`
- `Layer Mapping`
- `Precoding / Port Mapping`
- `MIMO Detection`
- `Layer Recovery / De-precoding`
- `CSI Feedback`

### 9. Show one batch comparison

Closed-loop vs open-loop CSI:

```powershell
C:\Users\tuan.dotrong\AppData\Local\radioconda\python.exe run_experiments.py --experiment csi_loop_compare --config configs/default.yaml --override configs/scenario_su_mimo_csi_loop.yaml --output-dir outputs
```

Look at:

- `outputs/csi_loop_compare/csi_loop_compare.csv`
- `outputs/csi_loop_compare/throughput_vs_snr.png`
- `outputs/csi_loop_compare/bler_vs_snr.png`

---

## If You Only Have 30 Minutes

Run only these four:

1. default GUI + `Step Mode`
2. `scenario_pbch_baseline.yaml`
3. `scenario_uplink_prach_baseline.yaml`
4. `scenario_su_mimo_two_codeword.yaml`

---

## If You Only Have 10 Minutes

Run only these two:

1. default GUI + `Step Mode`
2. `scenario_su_mimo_two_codeword.yaml`

---

## Follow-On Documents

- [TEACHING_DEMO_90_MINUTE.md](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/docs/TEACHING_DEMO_90_MINUTE.md)
- [TEACHING_LABS_6_SESSION_SERIES.md](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/docs/TEACHING_LABS_6_SESSION_SERIES.md)
- [TEACHING_LABS_MATRIX.md](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/docs/TEACHING_LABS_MATRIX.md)
