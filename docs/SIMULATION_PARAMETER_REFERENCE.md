# Simulation Parameter Reference

Tai lieu nay dien giai cac tham so mo phong hien dang xuat hien tren GUI `5G NR PHY STL Research Dashboard`.

Nguon tham chieu:

- Gioi han min/max va cac lua chon enum: [gui/controls.py](../gui/controls.py)
- Gia tri khoi dong khi mo GUI: [configs/default.yaml](../configs/default.yaml) ket hop voi `ControlPanel.apply_config()`
- MCS anchor table: [configs/mcs_tables.yaml](../configs/mcs_tables.yaml)

Luu y quan trong:

- Bang duoi day chi bao gom cac tham so dang hien thi tren GUI.
- Cot `Dai gia tri` dung gia tri GUI cho phep nhap, khong phai luc nao cung co nghia la moi gia tri deu hop ly ve mat he thong.
- Hai tham so `MCS` va `Mode = compare` hien van o muc scaffold/UI:
  - `MCS` dang hien thi tren GUI, nhung hien chua duoc dua vao `build_patch()` de dieu khien runtime. Trong phien ban hien tai, `Modulation` va `Code rate` moi la hai tham so thuc su chi phoi MCS-like operating point.
  - `Mode = compare` hien chua kich hoat mot luong so sanh control-vs-data truc tiep trong GUI single run. Neu can so sanh, nen dung batch experiment `control_vs_data` hoac cac script showcase/testcase.

## Bang tham so GUI

| STT | Ten tham so | Y nghia trong mo phong | Dai gia tri (min, max, mac dinh) | Don vi | Ky hieu |
| ---: | --- | --- | --- | --- | --- |
| 1 | `Mode` | Chon luong can mo phong tren giao dien vo tuyen: `data`, `control`, hoac scaffold `compare`. | Enum `{data, control, compare}`; mac dinh `data` | - | - |
| 2 | `Modulation` | Chon so do dieu che cho RE du lieu/control sau scrambling va truoc resource mapping. | Enum `{QPSK, 16QAM, 64QAM, 256QAM}`; mac dinh `QPSK` | - | `M` |
| 3 | `MCS` | Chi so MCS theo tinh than 3GPP dung de gan ket dieu che va code rate. Hien la scaffold de tham chieu/giang day. | Min `0`, max `27`, mac dinh `9` | index | `I_MCS` |
| 4 | `SCS (kHz)` | Khoang cach song mang con, quyet dinh numerology OFDM va sample rate thong qua `f_s = N_FFT * Delta f`. | Enum `{15, 30, 60}`; mac dinh `30` | kHz | `Delta f` |
| 5 | `FFT` | Kich thuoc FFT/IFFT dung cho OFDM modulation-demodulation. | Enum `{256, 512, 1024}`; mac dinh `512` | points | `N_FFT` |
| 6 | `RB` | So resource block dang active tren resource grid; moi RB gom 12 subcarrier. | Min `6`, max `80`, mac dinh `24` | RB | `N_RB` |
| 7 | `Code rate` | Ti le ma hoa muc tieu cua bo ma data `LDPC-inspired`; gia tri cao thi thong luong cao hon nhung kem robust hon. | Min `0.05`, max `0.95`, mac dinh `0.50` | ratio | `R` |
| 8 | `Channel model` | Chon lop mo hinh kenh tong quat: chi nhieu AWGN, Rayleigh fading, hoac Rician fading. | Enum `{awgn, rayleigh, rician}`; mac dinh `awgn` | - | `H_ch` |
| 9 | `Channel profile` | Chon PDP/TDL profile dai dien cho tinh huong truyen song nhu `pedestrian`, `vehicular`, `urban_los`. | Enum `{static_near, cell_edge, pedestrian, vehicular, indoor, urban_los, urban_nlos, severe_fading}`; mac dinh `static_near` | - | `PDP` |
| 10 | `SNR (dB)` | Ty so tin hieu tren nhieu duoc dung de dat noise variance trong AWGN block. | Min `-10.0`, max `40.0`, mac dinh `40.0` | dB | `SNR` / `gamma` |
| 11 | `Doppler (Hz)` | Do lech tan do do chuyen dong gay ra, anh huong toc do bien thien kenh theo thoi gian. | Min `0.0`, max `1000.0`, mac dinh `0.0` | Hz | `f_D` |
| 12 | `Delay spread (s)` | Do trai rong theo tre cua da duong; dung de scale TDL profile trong kenh fading chon loc tan so. | Min `0.0`, max `1e-4`, mac dinh `0.0` | s | `tau_DS` |
| 13 | `Path loss (dB)` | Suy hao cong suat bo sung do nguoi dung dat; duoc cong them vao free-space path loss va shadowing trong mo hinh fading. | Min `0.0`, max `180.0`, mac dinh `0.0` | dB | `PL` |
| 14 | `K-factor (dB)` | He so Rician the hien ty le thanh phan LOS so voi thanh phan tan xa. Gia tri cao hon nghia la LOS manh hon. | Min `0.0`, max `20.0`, mac dinh `8.0` | dB | `K` |
| 15 | `CFO (Hz)` | Carrier frequency offset giua ben phat va ben thu, gay quay pha theo thoi gian tren waveform. | Min `0.0`, max `1000.0`, mac dinh `0.0` | Hz | `Delta f_CFO` |
| 16 | `STO (samples)` | Symbol timing offset duoc mo hinh hoa bang dich mau waveform truoc khi dong bo. | Min `0`, max `256`, mac dinh `0` | samples | `Delta n_STO` |
| 17 | `Phase noise` | Do lech chuan cua nhiu pha tich luy theo moi mau trong `apply_phase_noise()`. | Min `0.0`, max `0.1`, mac dinh `0.0` | rad/sample | `sigma_phi` |
| 18 | `IQ imbalance` | Bat can bang bien do I/Q; trong code hien tai duoc mo hinh hoa bang gain imbalance theo dB, kem phase imbalance co dinh `2 deg`. | Min `0.0`, max `6.0`, mac dinh `0.0` | dB | `G_IQ` |
| 19 | `Use GNU Radio loopback` | Bat/tat luong loopback qua GNU Radio flowgraph thay vi duong Python-only. | Boolean `{false, true}`; mac dinh `false` | boolean | `b_GR` |

## Ghi chu dien giai them

### 1. `Mode`

- `data`: mo phong luong PDSCH-style baseline.
- `control`: mo phong luong PDCCH-style simplified.
- `compare`: hien la scaffold tren GUI; de so sanh dung nghia, nen dung:
  - `python run_experiments.py --experiment control_vs_data --config configs/default.yaml --output-dir outputs`
  - hoac `python run_student_testcases.py --config configs/default.yaml --case-id TC5 --output-dir outputs/student_testcases_tc5`

### 2. `MCS`

GUI hien cho phep nhap chi so `MCS`, nhung runtime hien tai chua tiep day vao chain mo phong. Ve mat thuc thi hien tai:

- `Modulation` quyet dinh so do dieu che
- `Code rate` quyet dinh muc rate matching / coding target

Bang MCS tham chieu hien co trong project:

| `I_MCS` | Modulation | Target rate |
| ---: | --- | ---: |
| 0 | QPSK | 0.12 |
| 4 | QPSK | 0.37 |
| 9 | 16QAM | 0.48 |
| 14 | 16QAM | 0.66 |
| 19 | 64QAM | 0.60 |
| 24 | 64QAM | 0.77 |
| 27 | 256QAM | 0.80 |

### 3. `RB` va rang buoc hop le

Validator hien tai ap dat dieu kien:

```text
n_rb * 12 < fft_size
```

Muc dich la de giu guard band va vi tri DC. Vi du:

- `N_RB = 24` thi so subcarrier active la `24 * 12 = 288`, hop le voi `N_FFT = 512`
- `N_RB = 80` se khong hop le neu `N_FFT = 512`, vi `80 * 12 = 960 > 512`

### 3.1. `VRB map`, `BWP start PRB`, `BWP size PRB`, `Start VRB`, `VRB count`

Cac tham so nay dieu khien baseline `VRB -> PRB Mapping` trong PHY Pipeline:

- `VRB map = non_interleaved`: VRB duoc anh xa truc tiep sang PRB.
- `VRB map = interleaved`: dung hoan vi teaching de thay adjacent VRB bi trai ra cac PRB khac nhau.
- `BWP size PRB = 0`: tu dong dung phan bandwidth con lai tinh tu `BWP start PRB`.
- `VRB count = 0`: tu dong cap phat tu `Start VRB` den cuoi BWP.
- Neu muon demo allocation hep, co the dat `BWP start PRB = 0`, `BWP size PRB = 24`, `Start VRB = 6`, `VRB count = 4`.

### 4. `Path loss`

Trong duong kenh fading, suy hao tong cong duoc tinh theo:

```text
PL_total = PL_user + FSPL(distance, f_c) + shadowing
```

Do do `Path loss (dB)` tren GUI nen duoc hieu la phan suy hao bo sung do nguoi dung cau hinh, khong phai toan bo suy hao kenh.

### 5. `Phase noise`

`Phase noise` trong project hien tai la simplified random-walk phase noise:

```text
phi[n] = phi[n-1] + w[n],  voi  w[n] ~ N(0, sigma_phi^2)
```

Nghia la gia tri nhap vao la do lech chuan cua buoc pha theo moi sample.

### 6. `IQ imbalance`

`IQ imbalance` hien tai duoc mo hinh hoa theo:

- gain imbalance theo dB do nguoi dung nhap
- phase imbalance co dinh `2 deg`

Day la mo hinh simplified phu hop cho giang day va sensitivity study, chua phai mo hinh RF front-end day du.

## Goi y su dung nhanh cho sinh vien

- Muon thay anh huong nhieu nen doi `SNR`
- Muon thay anh huong mobility nen doi `Doppler`
- Muon thay anh huong da duong nen doi `Channel profile` va `Delay spread`
- Muon thay anh huong lech dong bo nen doi `CFO`, `STO`, `Phase noise`
- Muon thay tradeoff thong luong-do tin cay nen doi `Modulation` va `Code rate`
