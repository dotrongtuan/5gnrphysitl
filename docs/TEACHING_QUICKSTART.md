# Teaching Quickstart

## Purpose

This is the fastest classroom runbook for the current project.

Use this when you want to **open the project and demo the most important 5G PHY concepts in order**, without reading the longer teaching documents first.

Project root:

```powershell
cd <path-to-5gnr_phy_stl>
```

Replace `<path-to-5gnr_phy_stl>` with the local checkout path on the classroom machine.

Absolute-path examples:

- Windows: `D:\Projects\5gnr_phy_stl`
- Ubuntu/Linux: `/home/<user>/projects/5gnr_phy_stl`
- macOS: `/Users/<user>/projects/5gnr_phy_stl`

Recommended interpreter:

```powershell
<radioconda-python>
```

`<radioconda-python>` means the `python.exe` inside your local Radioconda installation.

Explicit interpreter examples:

- Windows Radioconda: `C:\Users\<user>\AppData\Local\radioconda\python.exe`
- Ubuntu/Linux Conda environment: `/home/<user>/miniforge3/envs/5gnr-phy/bin/python`
- macOS Conda environment: `/Users/<user>/miniforge3/envs/5gnr-phy/bin/python`

---

## Demo Order

### 1. Open the default GUI

```powershell
<radioconda-python> main.py --config configs/default.yaml --gui
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
<radioconda-python> main.py --config configs/default.yaml --channel-type control --gui
```

PBCH / SSB:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_pbch_baseline.yaml --gui
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
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_uplink_baseline.yaml --gui
```

Uplink control:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_uplink_control_baseline.yaml --gui
```

Focus on:

- `PUSCH-style`
- `PUCCH-style`
- optional `Transform precoding`
- `SRS`

### 5. Show PRACH as a detection problem

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_uplink_prach_baseline.yaml --gui
```

Focus on:

- preamble generation
- correlation detection
- detected preamble ID

### 6. Show ideal vs realistic receiver behavior

Open the default GUI again:

```powershell
<radioconda-python> main.py --config configs/default.yaml --gui
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
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml --gui
```

### 7. Show file transfer over PHY

Text:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_text_transfer.yaml --gui
```

Image:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_image_transfer.yaml --gui
```

Focus on:

- `File Source + Packaging`
- PHY transport stages
- `File Reassembly + Write`
- why large files are more fragile at lower SNR

### 8. Show P3 HARQ and DCI-like scheduling

HARQ baseline:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_harq_baseline.yaml --gui
```

Scheduler replay:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_scheduler_grant_replay.yaml --gui
```

Coupled HARQ + scheduler:

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_p3_harq_scheduler_loop.yaml --gui
```

Focus on:

- `DCI-like Grant Timeline`
- `HARQ Process Timeline`
- `HARQ soft combining`
- `RV`
- `NDI`
- `process_id`
- `VRB -> PRB Mapping`

Optional quick GUI allocation demo:

- set `VRB map = interleaved`
- set `BWP size PRB = 24`
- set `Start VRB = 6`
- set `VRB count = 4`
- run default GUI and inspect `VRB -> PRB Mapping`

### 9. Show SU-MIMO baseline

```powershell
<radioconda-python> main.py --config configs/default.yaml --override configs/scenario_su_mimo_two_codeword.yaml --gui
```

Focus on:

- `Codeword Split`
- `Layer Mapping`
- `Precoding / Port Mapping`
- `MIMO Detection`
- `Layer Recovery / De-precoding`
- `CSI Feedback`

### 10. Show one batch comparison

Closed-loop vs open-loop CSI:

```powershell
<radioconda-python> run_experiments.py --experiment csi_loop_compare --config configs/default.yaml --override configs/scenario_su_mimo_csi_loop.yaml --output-dir outputs
```

Look at:

- `outputs/csi_loop_compare/csi_loop_compare.csv`
- `outputs/csi_loop_compare/throughput_vs_snr.png`
- `outputs/csi_loop_compare/bler_vs_snr.png`

---

## If You Only Have 30 Minutes

Run only these five:

1. default GUI + `Step Mode`
2. `scenario_pbch_baseline.yaml`
3. `scenario_uplink_prach_baseline.yaml`
4. `scenario_p3_harq_scheduler_loop.yaml`
5. `scenario_su_mimo_two_codeword.yaml`

---

## If You Only Have 10 Minutes

Run only these two:

1. default GUI + `Step Mode`
2. `scenario_p3_harq_scheduler_loop.yaml`

---

## Follow-On Documents

- [TEACHING_DEMO_90_MINUTE.md](TEACHING_DEMO_90_MINUTE.md)
- [TEACHING_LABS_6_SESSION_SERIES.md](TEACHING_LABS_6_SESSION_SERIES.md)
- [TEACHING_LABS_MATRIX.md](TEACHING_LABS_MATRIX.md)
