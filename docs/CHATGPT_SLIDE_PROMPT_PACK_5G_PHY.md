# ChatGPT Slide Prompt Pack for 5G NR PHY Teaching

## 1. Purpose

This document packages a set of ready-to-paste prompts for ChatGPT so it can generate lecture slides about this project and about 5G NR PHY.

The prompts are grounded in the current repository state, not in an imagined product scope.

Use this file when you want ChatGPT to generate:

- one large master teaching deck
- several smaller topic-specific decks
- an appendix deck that goes down to file/module/block level
- speaker notes, diagrams, formulas, tables, demo plans, and discussion questions

## 2. Repository-Grounded Fact Sheet

Before using the prompts, keep these project facts fixed.

### 2.1 What the project is

This repository should be described as:

`software-only, link-level, visually inspectable 5G NR PHY simulator`

At the current baseline it supports:

- CLI single-run execution
- GUI interactive exploration
- batch experiments
- stage-by-stage `PHY Pipeline`
- multi-slot playback with frame/slot/symbol scrubbers

### 2.2 Current implemented feature scope

The simulator currently includes:

- downlink data baseline
- downlink control baseline
- uplink data baseline
- uplink control baseline
- `PRACH` baseline
- `PBCH / SSB` baseline
- file transfer over the PHY chain
- standard-faithful SISO baseline
- SU-MIMO baseline with:
  - `1-2 codewords`
  - `1-4 layers`
  - `2x2` and `4x4`
  - `identity`, `dft`, and `type1_sp` precoding baseline
  - `ZF`, `MMSE`, `OSIC`
  - `CQI / PMI / RI` CSI loop baseline

### 2.3 Reference signals currently present

- `DM-RS`
- `PT-RS`
- `CSI-RS`
- `SRS`
- `PBCH-DMRS`

### 2.4 Main PHY chain currently visible in the project

Use this flow as the canonical chain when describing the project:

```text
Payload / TB
-> CRC + Segmentation + Coding
-> Rate Matching + Scrambling
-> QAM Mapping
-> Codeword -> Layer Mapping
-> Precoding / Port Mapping
-> Resource Grid + Reference Signals
-> OFDM / CP
-> Channel + Impairments
-> Sync + Remove CP + FFT
-> RE Extraction + CE + EQ + MIMO Detection
-> Descrambling + Rate Recovery + Decode
-> CRC / KPIs / GUI Artifacts
```

### 2.5 Main technical modules

Use these modules when you want ChatGPT to map slide content back to the codebase:

- `main.py`
- `run_experiments.py`
- `experiments/common.py`
- `phy/transmitter.py`
- `phy/receiver.py`
- `phy/resource_grid.py`
- `phy/coding.py`
- `phy/layer_mapping.py`
- `phy/precoding.py`
- `phy/mimo_detection.py`
- `phy/csi.py`
- `phy/reference_signals.py`
- `phy/prach.py`
- `gui/phy_pipeline.py`
- `gui/plots.py`
- `configs/default.yaml`
- scenario configs such as:
  - `configs/scenario_pbch_baseline.yaml`
  - `configs/scenario_uplink_baseline.yaml`
  - `configs/scenario_uplink_control_baseline.yaml`
  - `configs/scenario_uplink_prach_baseline.yaml`
  - `configs/scenario_text_transfer.yaml`
  - `configs/scenario_image_transfer.yaml`
  - `configs/scenario_su_mimo_layer_mapping.yaml`
  - `configs/scenario_su_mimo_two_codeword.yaml`
  - `configs/scenario_su_mimo_csi_loop.yaml`

### 2.6 Batch experiments currently present

- `ber_vs_snr`
- `bler_vs_snr`
- `evm_vs_snr`
- `fading_sweep`
- `doppler_sweep`
- `impairment_sweep`
- `file_transfer_sweep`
- `sample_file_transfer_sweep`
- `csi_loop_compare`

### 2.7 GUI and teaching artifacts currently present

- `PHY Pipeline`
- `Signal Domain`
- `Resource Grid`
- `Channel / Sync / EQ`
- `Batch Analytics`
- stage-by-stage playback
- frame/slot/symbol scrubbers
- environment status
- teaching quickstart
- 90-minute teaching demo
- 6-session teaching lab series

### 2.8 What must NOT be presented as already implemented

Do not let ChatGPT claim the project already implements:

- full HARQ protocol stack
- MU-MIMO
- Massive MIMO
- beam management / TCI / beam failure recovery
- FR2 hybrid beamforming
- full MAC/RLC/PDCP/RRC stack
- full 5G Core or system-level scheduling realism

Those should be described as:

- not yet implemented
- roadmap items
- future work

## 3. Global Instructions You Should Keep in Every Prompt

When using the prompts below, always preserve these instructions.

```text
Bạn là chuyên gia 5G NR PHY, chuyên gia instructional design, và technical presenter.

Hãy tạo nội dung slide giảng dạy về 5G NR PHY dựa trên một dự án phần mềm mô phỏng PHY 5G tên là "5G NR PHY STL Research Platform".

Yêu cầu bắt buộc:
1. Không được bịa tính năng mà dự án chưa có.
2. Phải phân biệt rõ:
   - cái gì là lý thuyết 3GPP / 5G NR thực tế
   - cái gì dự án này đã triển khai được
   - cái gì chỉ mới ở mức baseline / simplified model
   - cái gì còn là roadmap
3. Phải dùng giọng văn chuẩn kỹ thuật, phù hợp giảng dạy đại học hoặc cao học.
4. Phải ưu tiên cấu trúc logic của lớp vật lý:
   - bit domain
   - coded-bit / rate-matched domain
   - symbol domain
   - layer / port domain
   - resource-grid domain
   - time-domain waveform
   - channel / receiver inference domain
5. Mỗi slide cần có:
   - tiêu đề
   - mục tiêu học
   - 3-6 ý chính
   - gợi ý hình/bảng/sơ đồ/công thức
   - speaker notes ngắn
6. Với các slide có quy trình hoặc kiến trúc, hãy đề xuất sơ đồ Mermaid.
7. Với các slide có so sánh, hãy đề xuất bảng.
8. Với các slide có biểu thức, hãy đưa công thức ngắn gọn, đúng trọng tâm.
9. Nếu có chỗ chưa chắc vì dự án chỉ là baseline, hãy ghi rõ "baseline implementation" hoặc "teaching-oriented simplification".
10. Đầu ra phải có thể dùng để chuyển thành slide thật ngay.
```

## 4. Prompt 0: Master Prompt for a Full Teaching Deck

Use this when you want one large, comprehensive deck.

```text
Bạn là chuyên gia 5G NR PHY, chuyên gia instructional design, và technical presenter.

Hãy tạo cho tôi một bộ slide hoàn chỉnh bằng tiếng Việt về chủ đề:
"5G NR PHY qua một dự án mô phỏng phần mềm: từ SISO baseline đến SU-MIMO và CSI-aware link-level simulation".

Bối cảnh dự án:
- Tên dự án: 5G NR PHY STL Research Platform
- Bản chất dự án: software-only, link-level, visually inspectable 5G NR PHY simulator
- Có CLI, GUI, batch experiments
- Có PHY Pipeline stage-by-stage
- Có downlink data/control, uplink data/control, PRACH, PBCH/SSB, file transfer over PHY
- Có standard-faithful SISO baseline
- Có SU-MIMO baseline với:
  - 1-2 codewords
  - 1-4 layers
  - 2x2 và 4x4
  - precoding: identity, dft, type1_sp
  - detectors: ZF, MMSE, OSIC
  - CSI loop baseline với CQI / PMI / RI
- Có reference signals: DM-RS, PT-RS, CSI-RS, SRS, PBCH-DMRS
- Có các batch experiments: ber_vs_snr, bler_vs_snr, evm_vs_snr, fading_sweep, doppler_sweep, impairment_sweep, file_transfer_sweep, sample_file_transfer_sweep, csi_loop_compare

Những gì dự án chưa nên bị mô tả là đã hoàn chỉnh:
- full HARQ
- MU-MIMO
- Massive MIMO
- beam management / TCI
- FR2 hybrid beamforming
- full MAC/RLC/PDCP/RRC stack
- full system-level 5G

Tôi muốn bộ slide này có 45-60 slide, chia thành các phần lớn:
1. Động cơ và định vị dự án
2. 5G NR PHY thực tế gồm những gì
3. Kiến trúc tổng thể của dự án
4. PHY pipeline end-to-end của dự án
5. Resource grid và reference signals
6. Receiver chain: sync, remove CP, FFT, RE extraction, channel estimation, equalization, demapping, decoding
7. Downlink vs uplink vs PBCH/SSB vs PRACH
8. File transfer over PHY như một application-facing demo
9. SU-MIMO baseline: codeword, layer, port, precoding, detection, CSI feedback
10. Batch experiments và GUI như công cụ giảng dạy
11. Giới hạn hiện tại của dự án so với 5G thực tế
12. Roadmap từ baseline hiện tại đến realistic NR PHY simulator

Yêu cầu đầu ra:
- Trả ra theo định dạng:
  - Slide number
  - Slide title
  - Learning objective
  - Main bullets
  - Suggested figure/table/formula
  - Suggested Mermaid if applicable
  - Speaker notes
- Với các phần kiến trúc và luồng xử lý, hãy dùng Mermaid.
- Với các phần so sánh giữa "3GPP thực tế" và "dự án đã có", hãy dùng bảng.
- Với các phần receiver và MIMO, hãy thêm công thức ngắn gọn:
  - OFDM
  - channel model
  - equalization
  - LLR
  - ZF/MMSE detection
- Nhấn mạnh rằng đây là simulator link-level, không phải full 5G system simulator.
- Bám sát các module sau khi mô tả implementation:
  - main.py
  - experiments/common.py
  - phy/transmitter.py
  - phy/receiver.py
  - phy/resource_grid.py
  - phy/coding.py
  - phy/layer_mapping.py
  - phy/precoding.py
  - phy/mimo_detection.py
  - phy/csi.py
  - phy/reference_signals.py
  - phy/prach.py
  - gui/phy_pipeline.py

Mức độ chi tiết mong muốn:
- đủ sâu cho một học phần đại học năm cuối hoặc cao học
- không quá ngắn gọn
- phải đủ để từ đầu ra này tôi có thể dựng thành slide hoàn chỉnh
```

## 5. Prompt 1: Deck Tổng Quan và Định Vị Dự Án

Use this for the opening lecture.

```text
Hãy tạo một bộ slide 12-15 trang bằng tiếng Việt về:
"Định vị dự án 5G NR PHY STL Research Platform trong bức tranh 5G NR thực tế".

Nội dung bắt buộc:
- dự án này là gì
- software-only, link-level, visually inspectable simulator nghĩa là gì
- nó khác gì với:
  - full 5G system simulator
  - SDR / HIL platform
  - commercial 5G toolbox
- phạm vi hiện tại:
  - SISO baseline
  - SU-MIMO baseline
  - CSI baseline
  - file transfer demo
- ngoài phạm vi:
  - full HARQ
  - MU-MIMO
  - Massive MIMO
  - beam management
  - MAC/RRC/core network
- vì sao dự án này phù hợp cho teaching và link-level research

Đầu ra cần có:
- slide outline
- mỗi slide có bullets + speaker notes
- ít nhất 2 bảng so sánh
- ít nhất 1 sơ đồ Mermaid về vị trí của PHY trong hệ thống 5G
```

## 6. Prompt 2: Deck End-to-End PHY Pipeline

Use this when you want to teach the processing chain deeply.

```text
Hãy tạo một bộ slide 18-22 trang bằng tiếng Việt về:
"Chuỗi xử lý 5G NR PHY end-to-end qua dự án 5G NR PHY STL Research Platform".

Hãy bám theo chuỗi:
Payload / TB
-> CRC + Segmentation + Coding
-> Rate Matching + Scrambling
-> QAM Mapping
-> Codeword -> Layer Mapping
-> Precoding / Port Mapping
-> Resource Grid + Reference Signals
-> OFDM / CP
-> Channel + Impairments
-> Sync + Remove CP + FFT
-> RE Extraction + CE + EQ + MIMO Detection
-> Descrambling + Rate Recovery + Decode
-> CRC / KPIs

Yêu cầu:
- mỗi khối phải có 1 slide hoặc nửa slide logic riêng
- phải phân biệt domain dữ liệu ở mỗi bước:
  - bits
  - coded bits
  - symbols
  - layers
  - ports
  - RE grid
  - waveform
  - received observation
  - LLR
- phải nói rõ:
  - block nào sát 3GPP
  - block nào là baseline / simplified
  - block nào GUI quan sát được
- phải dùng ít nhất 2 sơ đồ Mermaid:
  - flow tổng của TX -> Channel -> RX
  - flow chi tiết của receiver
- phải gợi ý demo trực tiếp bằng GUI Step Mode
```

## 7. Prompt 3: Deck Resource Grid và Reference Signals

```text
Hãy tạo một bộ slide 14-18 trang bằng tiếng Việt về:
"Resource grid và reference signals trong 5G NR, nhìn qua dự án 5G NR PHY STL Research Platform".

Các chủ đề bắt buộc:
- numerology, slot, symbol, subcarrier, RE
- data RE vs control RE
- CORESET / SearchSpace baseline
- SSB / PBCH region
- DM-RS
- PT-RS
- CSI-RS
- SRS
- PBCH-DMRS
- cách các reference signal này được nhìn thấy trong GUI Resource Grid
- cách chúng liên hệ tới:
  - channel estimation
  - synchronization
  - CSI feedback
  - uplink sounding

Yêu cầu:
- có ít nhất 3 bảng
- có ít nhất 2 sơ đồ Mermaid
- có một phần riêng giải thích:
  - dự án này đã hiện thực RS nào
  - RS nào mới là baseline, chưa full-standard
```

## 8. Prompt 4: Deck Receiver, Impairments, và Estimation

```text
Hãy tạo một bộ slide 16-20 trang bằng tiếng Việt về:
"Receiver chain trong 5G NR PHY: synchronization, channel estimation, equalization, soft demapping, decoding".

Phải bám theo khả năng hiện có của dự án:
- synchronization
- remove CP
- FFT
- RE extraction
- channel estimation
- equalization
- MIMO detection baseline
- soft demapping
- descrambling
- rate recovery
- decoding
- CRC / KPIs

Phải có thêm phần về impairments:
- CFO
- STO
- phase noise
- IQ imbalance
- fading
- Doppler

Hãy làm rõ:
- vì sao `Perfect sync` và `Perfect CE` chỉ là ideal switches
- khi tắt chúng thì receiver khó hơn như thế nào
- các artifact nào trong GUI giúp thấy điều đó

Yêu cầu đầu ra:
- slide-by-slide
- công thức ngắn cho:
  - CFO effect
  - OFDM demod
  - CE/EQ
  - LLR
  - ZF/MMSE
- bảng "ideal receiver vs realistic receiver"
- gợi ý chạy:
  - default GUI
  - scenario_vehicular
  - impairment sweeps
```

## 9. Prompt 5: Deck Downlink, Uplink, PBCH, PRACH

```text
Hãy tạo một bộ slide 16-20 trang bằng tiếng Việt về:
"Các đường xử lý vật lý khác nhau trong dự án: downlink data, downlink control, uplink data, uplink control, PBCH/SSB, PRACH".

Nội dung bắt buộc:
- downlink data baseline
- downlink control baseline
- uplink data baseline
- uplink control baseline
- PRACH baseline như một bài toán preamble detection
- PBCH/SSB baseline như một bài toán broadcast

Hãy chỉ rõ:
- channel_type nào tương ứng với từng mode
- các scenario cấu hình sẵn:
  - scenario_uplink_baseline.yaml
  - scenario_uplink_control_baseline.yaml
  - scenario_uplink_prach_baseline.yaml
  - scenario_pbch_baseline.yaml
- khối nào khác nhau giữa các đường xử lý
- reference signal nào nổi bật ở từng case

Yêu cầu:
- có một bảng lớn so sánh 6 mode
- có Mermaid cho 2 flow:
  - PBCH / SSB
  - PRACH
- có speaker notes giải thích điều gì nên demo trực tiếp trước lớp
```

## 10. Prompt 6: Deck File Transfer over PHY

```text
Hãy tạo một bộ slide 10-14 trang bằng tiếng Việt về:
"Truyền file text và ảnh qua chuỗi PHY 5G NR trong dự án 5G NR PHY STL Research Platform".

Hãy dùng đây như một case study để nối từ PHY đến outcome ở mức ứng dụng.

Nội dung bắt buộc:
- file packaging ở TX
- chia chunk / mapping sang transport bits
- truyền qua toàn bộ PHY pipeline
- file reassembly ở RX
- cơ chế pass/fail theo chunk
- tại sao file lớn nhạy hơn file nhỏ
- ảnh hưởng của SNR đến khả năng khôi phục file
- ý nghĩa của file_transfer_sweep và sample_file_transfer_sweep

Yêu cầu:
- có một bảng text vs image
- có một sơ đồ Mermaid từ file -> bits -> PHY -> bits -> file
- có một slide riêng giải thích:
  - đây là một teaching-oriented application demo
  - nó không có nghĩa là PHY 5G thực tế truyền file theo đúng cách ở tầng ứng dụng
```

## 11. Prompt 7: Deck SU-MIMO, Layers, Precoding, Detection, CSI

```text
Hãy tạo một bộ slide 18-24 trang bằng tiếng Việt về:
"SU-MIMO baseline trong dự án 5G NR PHY STL Research Platform: codeword, layer, port, precoding, detection, CSI".

Nội dung bắt buộc:
- vì sao SISO không đủ để đại diện cho PHY 5G hiện đại
- tensor domains:
  - codeword
  - layer
  - port
  - tx_ant
  - rx_ant
- 1-2 codewords
- 1-4 layers
- 2x2 và 4x4 baseline
- layer mapping
- precoding / port mapping
- type1_sp baseline
- channel tensor concept
- detectors:
  - ZF
  - MMSE
  - OSIC
- layer recovery / de-precoding
- CSI feedback:
  - CQI
  - PMI
  - RI
- open-loop vs closed-loop CSI

Phải gắn với:
- scenario_su_mimo_layer_mapping.yaml
- scenario_su_mimo_two_codeword.yaml
- scenario_su_mimo_csi_loop.yaml
- experiment csi_loop_compare

Yêu cầu:
- ít nhất 2 bảng
- ít nhất 2 sơ đồ Mermaid
- công thức ngắn cho:
  - y = Hx + n
  - precoding
  - ZF
  - MMSE
  - rank / singular values / CSI intuition
- phải nói rõ đây là SU-MIMO baseline, chưa phải MU-MIMO hay massive MIMO
```

## 12. Prompt 8: Deck GUI, Experiments, and Teaching Workflow

```text
Hãy tạo một bộ slide 12-16 trang bằng tiếng Việt về:
"GUI, experiments, và workflow giảng dạy với dự án 5G NR PHY STL Research Platform".

Nội dung bắt buộc:
- 3 cách dùng dự án:
  - CLI single-run
  - GUI interactive exploration
  - batch experiments
- các panel GUI:
  - PHY Pipeline
  - Signal Domain
  - Resource Grid
  - Channel / Sync / EQ
  - Batch Analytics
- Run vs Step Mode
- frame / slot / symbol scrubbers
- teaching quickstart
- 90-minute teaching demo
- 6-session lab series
- teaching labs matrix
- experiment files:
  - ber_vs_snr
  - bler_vs_snr
  - evm_vs_snr
  - fading_sweep
  - doppler_sweep
  - impairment_sweep
  - file_transfer_sweep
  - csi_loop_compare

Hãy kết thúc bằng một slide:
"Cách dùng dự án này để dạy 5G PHY trong 1 buổi, 1 module, hoặc 1 học phần".
```

## 13. Prompt 9: Deck Giới Hạn và Roadmap

```text
Hãy tạo một bộ slide 12-16 trang bằng tiếng Việt về:
"Khoảng cách giữa dự án 5G NR PHY STL Research Platform và hệ 5G NR thực tế: giới hạn hiện tại và roadmap phát triển".

Bối cảnh:
- dự án hiện đã có P0, P1, P2 baseline
- dự án chưa có:
  - full HARQ
  - MU-MIMO
  - Massive MIMO
  - beam management / TCI
  - FR2 hybrid beamforming
  - full MAC/RLC/PDCP/RRC

Hãy chia slide thành:
1. cái gì đã làm được và có thể dạy tốt
2. cái gì mới ở mức baseline
3. cái gì chưa nên claim là đã có
4. roadmap P3 / P4 / P5
5. vì sao dự án này vẫn rất có giá trị cho teaching và link-level research

Yêu cầu:
- ít nhất 2 bảng:
  - "real 5G NR vs current project"
  - "implemented vs baseline vs roadmap"
- ít nhất 1 sơ đồ Mermaid cho roadmap kỹ thuật
```

## 14. Prompt 10: Element-Level Appendix Deck

Use this when you want ChatGPT to generate a deep appendix that goes close to file/block level.

```text
Hãy tạo một bộ slide appendix 25-35 trang bằng tiếng Việt về:
"Bản đồ phần tử của dự án 5G NR PHY STL Research Platform ở mức file, module, block xử lý và artifact GUI".

Mục tiêu:
- tạo slide phục vụ giảng viên hoặc trợ giảng muốn giải thích dự án đến cấp độ từng thành phần
- không chỉ nói lý thuyết 5G NR, mà còn map sang codebase thực

Yêu cầu bắt buộc:
- nhóm slide theo các cụm:
  1. entry points và orchestration
  2. transmitter path
  3. channel / impairments
  4. receiver path
  5. grid / reference signals
  6. spatial processing
  7. CSI
  8. PRACH / PBCH special paths
  9. GUI and artifacts
  10. scenarios and experiments
- phải map các file sau vào slide:
  - main.py
  - run_experiments.py
  - experiments/common.py
  - phy/transmitter.py
  - phy/receiver.py
  - phy/resource_grid.py
  - phy/coding.py
  - phy/layer_mapping.py
  - phy/precoding.py
  - phy/mimo_detection.py
  - phy/csi.py
  - phy/reference_signals.py
  - phy/prach.py
  - gui/app.py
  - gui/controls.py
  - gui/plots.py
  - gui/phy_pipeline.py
  - configs/default.yaml
  - scenario yaml files
- mỗi slide phải có:
  - module/file name
  - technical responsibility
  - data domain in/out
  - what students should learn from it
  - which GUI artifact or experiment exposes it

Hãy thêm 1 bảng tổng kết cuối:
"file/module -> concept -> demo path -> slide role"
```

## 15. Prompt 11: Speaker-Notes-First Version

Use this if you already have a slide outline and only want deep notes.

```text
Dựa trên dự án 5G NR PHY STL Research Platform, hãy viết speaker notes thật chi tiết cho một bộ slide giảng dạy về 5G NR PHY.

Giả định rằng slide deck đã có sẵn tiêu đề các phần:
- Project positioning
- 5G NR PHY overview
- End-to-end PHY pipeline
- Resource grid and reference signals
- Receiver chain and impairments
- Downlink / Uplink / PRACH / PBCH
- File transfer over PHY
- SU-MIMO and CSI baseline
- Experiments and GUI
- Limitations and roadmap

Hãy viết speaker notes theo từng phần, mỗi phần:
- 250-500 từ
- có logic giảng dạy rõ
- giải thích what, why, how
- chỉ rõ đâu là 3GPP theory, đâu là project implementation
- gợi ý chỗ nào nên mở GUI demo
```

## 16. Prompt 12: Visual-Heavy Slide Version

Use this if you want ChatGPT to bias toward diagrams and figures.

```text
Hãy tạo outline cho một bộ slide cực kỳ trực quan bằng tiếng Việt về 5G NR PHY dựa trên dự án 5G NR PHY STL Research Platform.

Ưu tiên:
- sơ đồ Mermaid
- bảng
- icon/figure suggestion
- ít chữ hơn, nhiều hình hơn

Ràng buộc:
- mỗi slide phải chỉ ra loại visual phù hợp nhất:
  - Mermaid flowchart
  - Mermaid architecture diagram
  - Mermaid sequence diagram
  - comparison table
  - formula box
  - screenshot from GUI
  - plot suggestion from batch experiments
- phải gắn visual đó với khả năng thực tế của dự án:
  - PHY Pipeline
  - Resource Grid
  - Signal Domain
  - Channel / Sync / EQ
  - SU-MIMO detector artifacts
  - file transfer artifacts
```

## 17. Recommended Prompt Usage Strategy

If you want the best result from ChatGPT, do this in order:

1. Start with `Prompt 0` to get the master structure.
2. Then run topic prompts `1-9` separately to deepen each section.
3. Use `Prompt 10` to get an appendix deck for advanced students or assistants.
4. Use `Prompt 11` if you want presenter notes after the outline is stable.
5. Use `Prompt 12` if you want a more visual deck after the content is fixed.

## 18. Suggested Classroom Deck Combinations

### Option A: One 90-minute lecture

Use:

- `Prompt 1`
- `Prompt 2`
- `Prompt 3`
- `Prompt 5`
- `Prompt 8`

### Option B: A 3-lecture mini-module

Lecture 1:

- `Prompt 1`
- `Prompt 2`

Lecture 2:

- `Prompt 3`
- `Prompt 4`
- `Prompt 5`

Lecture 3:

- `Prompt 6`
- `Prompt 7`
- `Prompt 9`

### Option C: A full teaching package

Use:

- `Prompt 0`
- `Prompt 10`
- `Prompt 11`

## 19. Final Reminder

These prompts are designed to keep ChatGPT honest about the project scope.

The most important constraint is:

- present the project as a strong teaching and link-level research platform
- do not present it as a full, commercial, end-to-end 5G system simulator

That distinction is essential for technically correct lecture material.
