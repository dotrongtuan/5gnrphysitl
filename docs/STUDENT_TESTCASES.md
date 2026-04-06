# Student Testcases for 5G NR PHY STL

This guide gives students a small set of reproducible experiments that illustrate the meaning of key PHY concepts in the current software-only prototype.

The goal is not only to run commands, but also to connect the observed KPIs to PHY intuition:

- why EVM changes with SNR
- why higher-order modulation needs more SNR
- why fading and Doppler reduce the effective received quality
- why a harsh channel can break throughput even if the baseline link works
- why simplified models must be interpreted carefully

## Before You Start

Run from the project root:

Windows:

```powershell
cd C:\path\to\5gnr_phy_stl
```

Linux/macOS:

```bash
cd /path/to/5gnr_phy_stl
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## One-Command Teaching Run

You can run the curated testcase bundle with:

Windows:

```cmd
run_student_testcases.bat
```

Linux/macOS:

```bash
chmod +x run_student_testcases.sh
./run_student_testcases.sh
```

Direct Python command:

```bash
python run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
```

Outputs:

- `outputs/student_testcases/student_testcases.csv`
- `outputs/student_testcases/student_testcases.md`

## Testcase 1: Clean Baseline Link

### Purpose

Show the reference behavior of the PHY chain in a very clean AWGN setup with perfect synchronization and perfect channel estimation.

### Command

```bash
python main.py --config configs/default.yaml
```

### Sample result from this repository

| KPI | Value |
| --- | ---: |
| BER | 0.0 |
| BLER | 0.0 |
| EVM | 0.00667 |
| Throughput | 2.05e6 bps |
| Estimated SNR | 43.51 dB |

### What students should learn

- This is the sanity-check case.
- BER and BLER are zero, so the link is decoding correctly.
- EVM is very small, which means the received constellation points are close to the transmitted symbols.
- Before studying fading or impairments, always verify that the clean reference case behaves correctly.

## Testcase 2: 256QAM SNR Sweep

### Purpose

Show that higher-order modulation needs a higher SNR to become reliable.

### Command

```bash
python run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
```

Look for the rows with `case_id = TC2`.

### Sample result from this repository

| SNR (dB) | BER | BLER | EVM |
| ---: | ---: | ---: | ---: |
| 0 | 0.08496 | 1.0 | 0.66565 |
| 5 | 0.02441 | 1.0 | 0.37454 |
| 10 | 0.00195 | 1.0 | 0.21066 |
| 15 | 0.0 | 0.0 | 0.11847 |
| 20 | 0.0 | 0.0 | 0.06662 |

### What students should learn

- At low SNR, 256QAM symbols are too close together in the I/Q plane, so the receiver makes many wrong decisions.
- As SNR increases, EVM decreases and BER improves.
- In this prototype, the 256QAM link becomes clean around 15 dB for the chosen coding rate and payload size.
- This experiment is a concrete demonstration of the modulation-vs-robustness tradeoff.

## Testcase 3: Channel Profile Comparison

### Purpose

Show that the same nominal SNR can lead to different effective received quality under different channels.

### Command

```bash
python run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
```

Look for the rows with `case_id = TC3`.

### Sample result from this repository

| Profile | BER | BLER | EVM | Estimated SNR (dB) |
| --- | ---: | ---: | ---: | ---: |
| static_near | 0.0 | 0.0 | 0.06673 | 23.51 |
| pedestrian | 0.0 | 0.0 | 0.14318 | 16.88 |
| vehicular | 0.0 | 0.0 | 0.14174 | 16.97 |
| urban_los | 0.0 | 0.0 | 0.18742 | 14.54 |

### What students should learn

- All cases use the same nominal SNR setting, but the effective quality still changes.
- EVM increases when the channel is more difficult to estimate or equalize.
- Estimated SNR at the receiver can be lower than the configured SNR because the channel profile changes the signal seen after equalization.
- This is why link-level evaluation must consider the channel model, not only the AWGN value.

## Testcase 4: Vehicular Stress Scenario

### Purpose

Show how Doppler, delay spread, and synchronization impairments can collapse the link.

### Command

```bash
python main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml
```

### Sample result from this repository

| KPI | Value |
| --- | ---: |
| BER | 0.73633 |
| BLER | 1.0 |
| EVM | 2.00057 |
| Throughput | 0.0 |
| Estimated SNR | -6.02 dB |

### What students should learn

- This case is intentionally harsh.
- BER is very high and BLER is 1, so the block fails every time in this example.
- Throughput drops to zero because CRC fails.
- This illustrates why mobility, multipath, and sync errors matter in OFDM systems.
- It also shows why a clean baseline result does not guarantee performance in realistic channels.

## Testcase 5: Control vs Data as a Model-Limitation Study

### Purpose

Teach students how to interpret a simplified simulator critically.

### Command

```bash
python run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
```

Look for the rows with `case_id = TC5`.

### Sample result from this repository at -4 dB

| Channel type | BER | BLER | EVM |
| --- | ---: | ---: | ---: |
| control | 0.42188 | 1.0 | 0.39993 |
| data | 0.00684 | 1.0 | 1.05530 |

### What students should learn

- In a standards-faithful NR system, control is normally designed to be highly reliable.
- In this prototype, the control path uses a simplified `polar-like` coder and is not yet a conformance-grade implementation.
- The unexpected result is therefore educational: it reveals a limitation of the model rather than a property of real 5G NR.
- Students should learn to separate implementation artifact from physical-layer principle.

## Suggested Classroom Workflow

1. Run Testcase 1 first and verify that the simulator behaves correctly in the clean reference setting.
2. Run Testcase 2 and ask students to identify the SNR region where 256QAM becomes usable.
3. Run Testcase 3 and compare channels at the same nominal SNR.
4. Run Testcase 4 and discuss why the link fails in a high-mobility scenario.
5. Run Testcase 5 and discuss model limitations and validation methodology.

## Discussion Questions

1. Why can two links configured with the same SNR produce different EVM values?
2. Why does higher-order modulation need a higher SNR?
3. Why is BLER often the more operationally meaningful metric than BER?
4. Why should we always compare difficult scenarios against a clean reference case?
5. How can a simplified simulator still be useful even when some blocks are not fully standard-compliant?
