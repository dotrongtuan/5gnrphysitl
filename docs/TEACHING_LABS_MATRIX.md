# Teaching Labs Matrix for the Full-Option PHY Pipeline

## Scope

This document converts the full-option PHY pipeline use cases into practical labs that can be executed with the current project and extended later as additional PHY blocks are implemented. The matrix is intended for classroom use, guided demos, and structured self-study.

The commands below assume the project root is the current working directory.

## Recommended Baseline

Use the following baseline unless a lab explicitly overrides it:

- Python interpreter: the active project environment or Radioconda when GNU Radio QT sinks are needed
- Base config: `configs/default.yaml`
- GUI mode: `python main.py --config configs/default.yaml --gui`
- Multi-slot demo baseline: `Capture slots = 12`
- Robust file-transfer baseline:
  - `Modulation = QPSK`
  - `Code rate = 0.50`
  - `Channel model = awgn`
  - `Channel profile = static_near`
  - `SNR = 40 dB`
  - `Perfect sync = On`
  - `Perfect CE = On`

## Lab Matrix

| Lab ID | Lab title | GUI settings | CLI / batch command | Main blocks | Expected result | Student questions |
| --- | --- | --- | --- | --- | --- | --- |
| `LAB-01` | End-to-end PHY walkthrough | `Mode=data`, `QPSK`, `AWGN`, `SNR=20 dB`, `Capture slots=1`, `Perfect sync=On`, `Perfect CE=On` | `python main.py --config configs/default.yaml --gui` | full chain | Clean constellation, low BER/BLER, all pipeline stages visible | Which stage changes data domain from bits to symbols to samples? |
| `LAB-02` | Multi-slot playback | Same as `LAB-01`, but `Capture slots=12` | `python main.py --config configs/default.yaml --gui` | playback, OFDM, sync, CE | Frame/slot scrubber spans `Frame 0 / Slot 0..9` then `Frame 1 / Slot 0..1` | What changes from one slot to the next when the PHY settings are unchanged? |
| `LAB-03` | Text transfer over PHY | Select `TX file=input/sample_message.txt`, `RX output=outputs/rx_files`, keep robust baseline | `python main.py --config configs/default.yaml --tx-file input/sample_message.txt --rx-output-dir outputs/rx_files` | packaging, coding, CRC, file reassembly | RX writes a timestamped `.txt` file with matching hash | Why does a small file survive lower SNR more easily than a large file? |
| `LAB-04` | Image transfer over PHY | Select `TX file=input/sample_image.png`, same robust baseline | `python main.py --config configs/default.yaml --tx-file input/sample_image.png --rx-output-dir outputs/rx_files` | packaging, coding, CRC, file reassembly | RX writes a timestamped `.png` file when all chunks pass CRC | Why can one bad chunk prevent the image from being written at all? |
| `LAB-05` | File-transfer SNR sensitivity | Same as `LAB-03` or `LAB-04`, then repeat with `SNR=40,10,4,0 dB`, `Perfect sync=Off`, `Perfect CE=Off` | `python run_experiments.py --experiment sample_file_transfer_sweep --config configs/default.yaml --override configs/scenario_sample_file_transfer_sweep.yaml --output-dir outputs` | sync, CE, decoder, CRC | Text succeeds over a wider SNR range than image; chunk failures rise as SNR drops | How does chunk count influence end-to-end file success probability? |
| `LAB-06` | Perfect vs realistic receiver | Run once with `Perfect sync=On`, `Perfect CE=On`, then again with both `Off` | `python main.py --config configs/default.yaml --gui` | sync, CE, EQ, demap | Realistic mode shows worse estimation quality and decoder input quality | Which KPI changes first when perfect assumptions are removed? |
| `LAB-07` | Modulation comparison | Repeat with `QPSK`, `16QAM`, `64QAM`, `256QAM`, hold channel constant | `python run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs` | modulation, demap, decoder | Higher-order QAM raises throughput but needs higher SNR | Why does the LLR histogram become less robust for dense constellations? |
| `LAB-08` | Channel profile comparison | Compare `awgn/static_near`, `rayleigh/pedestrian`, `rician/urban_los`, `rayleigh/vehicular` | `python run_showcases.py --config configs/default.yaml --output-dir outputs/showcases` | channel, CE, EQ | Same nominal SNR produces different EVM/BLER across profiles | Which artifact best explains why two channels at the same SNR behave differently? |
| `LAB-09` | Synchronization impairment study | Start from robust baseline, then increase `CFO`, `STO`, `Phase noise`, disable `Perfect sync` | `python run_experiments.py --experiment impairment_sweep --config configs/default.yaml --output-dir outputs` | sync, remove CP, FFT | Timing/CFO artifacts worsen, then BER/BLER rises | At what point does the impairment first become visible in the pipeline before it hits CRC? |
| `LAB-10` | DMRS / channel estimation study | Fading profile, `Perfect CE=Off`, use `PHY Pipeline`, `Resource Grid`, `Channel / Sync / EQ` tabs | `python run_showcases.py --config configs/default.yaml --output-dir outputs/showcases` | DMRS, RE extraction, CE, EQ | Estimated channel grid degrades before decoder failure | Why is post-equalization constellation more informative than raw RX constellation here? |
| `LAB-11` | Decoder-input quality study | Moderate fading, `Perfect sync=Off`, `Perfect CE=Off`, use `Step Mode` | `python main.py --config configs/default.yaml --gui` | demap, descramble, rate recovery, soft LLR | LLR quality visibly degrades before BLER reaches 1 | What does the LLR histogram say about decoder confidence? |
| `LAB-12` | P3 HARQ RV and soft combining | `Capture slots=4`, `Perfect sync=On`, `Perfect CE=On`, inspect `HARQ Process Timeline` | `python main.py --config configs/default.yaml --override configs/scenario_harq_baseline.yaml --gui` | HARQ process, RV, soft buffer, rate recovery | RV sequence advances as `0,2,3,1`; soft observations accumulate over retransmissions | Why does the decoder get more confident after repeated observations of the same TB? |
| `LAB-13` | P3 DCI-like scheduler replay | Use scheduler scenario, inspect `DCI-like Grant Timeline` and per-slot `scheduled_*` fields | `python main.py --config configs/default.yaml --override configs/scenario_scheduler_grant_replay.yaml --gui` | DCI-like grant, MCS, layers, precoder | Grants replay across slots and change modulation/layer/precoding choices | What is the difference between a PHY block and a scheduler decision? |
| `LAB-14` | P3 coupled scheduler + HARQ | Use coupled scenario, inspect `process_id`, `NDI`, `RV`, ACK/NACK and soft observations | `python main.py --config configs/default.yaml --override configs/scenario_p3_harq_scheduler_loop.yaml --gui` | scheduler, HARQ process, NDI, RV | Two HARQ processes are scheduled; retransmissions reuse NDI and advance RV | Why does HARQ need both process identity and NDI? |
| `LAB-15` | VRB to PRB allocation | In GUI set `VRB map=interleaved`, `BWP size PRB=24`, `Start VRB=6`, `VRB count=4` | `python main.py --config configs/default.yaml --gui` | VRB, PRB, resource grid, DMRS | `VRB -> PRB` stage shows allocation mask and PRB permutation before grid mapping | Why is resource allocation a scheduling/resource-mapping problem rather than modulation? |
| `LAB-16` | Full-option extension planning | Use `PHY Pipeline` plus `docs/FULL_OPTION_PHY_USECASES.md` to map future blocks | No runtime command; this is a design lab | layer mapping, precoding, de-precoding, RF front-end | Students can place each future block in the correct TX/RX position | Which future blocks are still mathematically software-only, and why? |

## Operational Notes

- `Run` executes a complete simulation and leaves the current view unchanged.
- `Step Mode` executes the same simulation, then jumps to the `PHY Pipeline` tab at the first captured slot and first stage.
- For file transfer, the effective slot count is driven by the number of chunks needed to carry the file.
- For non-file multi-slot demos, the effective slot count is controlled by `Capture slots`.
- RX file names include both the received SNR label and a timestamp to avoid collisions across repeated runs.

## Suggested Lab Progression

1. Start with `LAB-01` and `LAB-02` so students understand the base chain and the time structure.
2. Move to `LAB-03` and `LAB-04` so students can connect PHY reliability to application-level outcomes.
3. Use `LAB-05`, `LAB-06`, `LAB-09`, and `LAB-10` to explain why realistic impairments matter.
4. Use `LAB-07` and `LAB-11` to connect constellation density, LLR quality, and decoder behavior.
5. Use `LAB-12`, `LAB-13`, and `LAB-14` to show that 5G PHY behavior is slot-sequence and scheduler/HARQ dependent, not only a one-slot waveform problem.
6. Use `LAB-15` to connect scheduler grants to frequency-domain resource allocation.
7. End with `LAB-16` to bridge from the current project to the full-option PHY roadmap.

## Placeholder Figures and Tables

- Placeholder: table of expected `chunks_failed` values for text and image versus SNR under the current default config
- Placeholder: screenshot set for `PHY Pipeline`, `Resource Grid`, and `Channel / Sync / EQ` tabs
- Placeholder: screenshot set for `DCI-like Grant Timeline`, `HARQ Process Timeline`, and `VRB -> PRB Mapping`
- Placeholder: timing budget per lab session and per lab run
- Placeholder: assessment rubric for student reports
