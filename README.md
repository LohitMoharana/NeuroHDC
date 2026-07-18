# 🧠 NeuroHDC: High-Efficiency Edge-AI ECG Classification using Spiking-Hyperdimensional Computing

<p align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Verilog](https://img.shields.io/badge/RTL-Verilog-orange.svg)
![FPGA](https://img.shields.io/badge/FPGA-Zynq%20%7C%20Artix--7-green.svg)
![License](https://img.shields.io/badge/License-MIT-red.svg)
![Status](https://img.shields.io/badge/Research-Prototype-success.svg)

</p>

> **Ultra-efficient, zero-multiplier Edge-AI ECG classification using Spiking Hyperdimensional Computing (HDC), evaluated under strict inter-patient (patient-isolated) cross-validation.**

NeuroHDC is a hardware-efficient framework for ECG arrhythmia classification. This repository contains the complete algorithmic proof-of-concept, dataset loaders, a self-trained deep learning baseline, patient-isolated 5-fold cross-validated benchmarking, and the bit-true Verilog hardware description for our proposed **Spiking-Hyperdimensional Computing (HDC)** architecture.

---

## 📄 Abstract

The deployment of deep learning (CNNs, LSTMs) on wearable, battery-powered medical devices is constrained by the **"Power Wall"** — the energy cost of floating-point Multiply-Accumulate (MAC) operations. NeuroHDC explores an alternative: a unified hardware-software architecture combining event-driven sparsity with the Boolean geometry of Hyperdimensional Computing (HDC). Analog ECG signals are tokenized into sparse events and encoded into a **4096-dimensional binary hyperspace**, eliminating MAC units from the inference datapath entirely.

Unlike much of the HDC literature, which evaluates with random beat-level splits, NeuroHDC is evaluated using **strict patient-isolated (inter-patient) 5-fold cross-validation** across four clinical datasets — no beat from a given patient's recording ever appears in both the training and test set of a fold. This is a substantially harder and more clinically realistic protocol, and produces correspondingly more modest but honest numbers: **70.99% ± 5.83% strict multi-class accuracy / 35.77% ± 6.81% macro F1 on MIT-BIH**, with morphology-dominant tasks (PTB, ST-T) performing considerably better than the rhythm-dominant AFib task (PhysioNet). A lightweight **R-R interval permutation-binding** extension is introduced to address timing-based failure modes, which helps meaningfully for isolated ectopic beats (MIT-BIH PACs) but does not rescue the non-stationary rhythm of atrial fibrillation (PhysioNet) — a documented, mechanistically-explained limitation rather than an unexplained gap.

Critically, when a self-trained 1D-CNN baseline is evaluated under this same patient-isolated protocol, its accuracy collapses from an intra-patient 98.66% to **72.72% ± 8.11%** — confirming that much of its earlier apparent advantage was itself a beat-level leakage artifact rather than genuine generalization. Under honest, identical splits, NeuroHDC and the CNN achieve **statistically comparable macro F1** (35.77% vs. 34.56%, well within each other's variance), while NeuroHDC operates at roughly **40x lower latency and 360x lower energy per inference**. The efficiency-accuracy trade-off this architecture was designed around turns out, under rigorous evaluation, to be closer to an efficiency win at comparable accuracy than a genuine accuracy sacrifice.

---

## 🏗 Architecture

```text
        Raw ECG
           │
           ▼
┌──────────────────────┐
│ Pre-processing & AGC │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Delta Spike Tokenizer│
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│    HDC XOR Encoder   │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Majority Accumulator │
└──────────────────────┘
           │
           ▼
    4096-bit Hypervector
           │
           ▼
┌──────────────────────┐
│  Associative Memory  │
│  (Hamming Distance)  │
└──────────────────────┘
           │
           ▼
      ECG Diagnosis
```

---

## 🧠 1. Architectural Methodology

The NeuroHDC pipeline transforms a noisy, 1-dimensional analog time-series signal into a static **D = 4096** binary signature using four distinct stages.

### Stage 1 — Morphological Isolation & Pre-processing *(Software / MCU)*

To prevent the **Positional Orthogonality Trap** inherent to HDC, every ECG heartbeat is surgically aligned before encoding.

- **Baseline Correction:** A 0.5-second rolling-mean filter flattens low-frequency respiratory wander.
- **Exact Temporal Anchoring:** During training/evaluation, beat centers are taken from each dataset's expert-labeled fiducial points (standard practice for these databases). In the deployed hardware path, where no ground truth exists, the R-peak is instead detected via the **Pan–Tompkins algorithm**, refined with a local ±20-sample search for the absolute maximum, and anchored at the exact center (**t = 128**) of a **256-sample window (~0.85 seconds)**.
- **Smart AGC:** The window undergoes 98th-percentile soft-clipping to normalize amplitude variation without destroying subtle P/T-wave morphology.

### Stage 2 — The Delta-Tokenizer *(Hardware Sparsity Engine)*

Instead of feeding continuous arrays into a dense neural network layer, NeuroHDC tokenizes the signal based on its discrete derivative:

```math
\Delta v_t = v_t - v_{t-1}
```

If the derivative crosses a channel-specific threshold (θ꜀), a positive or negative spike (±1) is emitted; otherwise the tokenizer emits 0.

**Sparsity definition:** sparsity is measured as the percentage of zero-valued tokens emitted by the tokenizer, across all channels, over the entire test set. Because the ECG is mostly an isoelectric flatline, the tokenizer outputs 0 for **>93%** of the cardiac cycle — physically putting the downstream HDC datapath into a deep sleep state.

### Stage 3 — HDC Exact Temporal Binding *(Zero-MAC Encoding)*

Active spikes are mapped into a 4096-bit Boolean space. In bipolar theory this involves multiplying i.i.d. random vectors representing Channel (C), Polarity (P), and Time index (T). In digital hardware, this reduces to parallel bitwise XOR:

```math
B_t = C_c \oplus P_p \oplus T_t
```

Bound vectors are accumulated over the 256-sample window and thresholded via a **Majority Rule** function to produce a single, static 4096-bit Query Hypervector (H_Q).

### Stage 4 — Associative Memory & Inference

Inference requires zero floating-point arithmetic. The Query Hypervector is compared against learned disease prototypes using Hamming Distance, computed via an XOR gate array and a Popcount adder tree:

```math
Distance_i = \text{Popcount}(H_Q \oplus H_{Class_i})
```

The class with the minimum Hamming distance determines the diagnosis.

### Stage 5 — R-R Interval Rhythm Binding *(Optional Extension)*

To address timing-based failure modes (see Sections 4–5), each beat's R-R interval relative to its record's local median is bucketed into `SHORT` / `NORMAL` / `LONG`, mapped to a fixed random hypervector, and bound (bipolar XOR) with the morphology hypervector before classification. This adds a single extra XOR stage in hardware — no additional multipliers.

---

## 📊 2. Experimental Rigor: Patient-Isolated 5-Fold Cross-Validation

All results below use **`StratifiedGroupKFold`**, splitting by patient/record rather than by individual beat — no beat from a given patient's recording appears in both the training and test set of any fold. This is a materially harder and more clinically meaningful protocol than the beat-level `StratifiedKFold` used in an earlier iteration of this project's evaluation, which was found to leak near-duplicate beats across the train/test boundary and produced inflated (and in two cases, literally 100%) accuracy figures. All numbers in this document are from the corrected, patient-isolated protocol.

### MIT-BIH Arrhythmia Database (N = 100,023 beats, 48 patients)

| Configuration | Strict Accuracy | Macro F1 | Binary Accuracy* |
|---|---:|---:|---:|
| Morphology-only | 66.43% ± 7.83% | 32.69% ± 7.41% | 77.48% ± 6.65% |
| **+ R-R Rhythm Binding** | **70.99% ± 5.83%** | **35.77% ± 6.81%** | **78.40% ± 5.21%** |

\* *Binary accuracy follows the AAMI EC57 convention of grouping LBBB/RBBB into the Normal superclass (Normal vs. ectopic/ischemic), rather than treating conduction-block morphology as an anomaly.*

### PTB, ST-T, and PhysioNet

| Dataset | Strict Accuracy | Macro F1 | Binary Accuracy |
|---|---:|---:|---:|
| PTB (Myocardial Infarction) | 90.06% ± 1.04% | 56.24% ± 3.46% | 90.06% ± 1.04% |
| European ST-T (Ischemia) | 85.33% ± 1.92% | 78.48% ± 2.46% | 85.33% ± 1.92% |
| PhysioNet 2017 (AFib, rhythm binding ON, Noisy class excluded from macro-F1) | 56.88% ± 0.62% | 45.05% ± 0.80% | 65.87% ± 0.67% |

**High fold-to-fold variance on MIT-BIH (±5.8–7.8 points) is a real, investigated property of this evaluation, not noise.** With only 48 patients split into 5 groups, pathology distribution across folds is highly uneven — for example, one fold's held-out set contains zero LBBB beats, and another contains roughly 60% of the entire dataset's PAC beats. This is a known and documented constraint of small-cohort inter-patient cross-validation, consistent with the inter-patient evaluation literature (e.g., de Chazal et al., 2004).

### 2.1 Efficiency Comparison vs. Self-Trained CNN (both patient-isolated)

The self-trained 1D-CNN baseline is now trained and evaluated under the **identical `StratifiedGroupKFold` patient-level splits** used for NeuroHDC — not the earlier beat-level `StratifiedKFold` protocol, which was found to inflate the CNN's accuracy from ~73% to a leaked 98.66% via the same beat-level leakage mechanism documented above.

| Architecture | Strict Accuracy (Avg ± SD) | Binary Accuracy (Avg ± SD) | Macro F1 (Avg ± SD) | Latency (ms) | Energy (μJ/Inf) |
|---|---:|---:|---:|---:|---:|
| **NeuroHDC (rhythm-enabled)** | 70.99% ± 5.83% | 78.40% ± 5.21% | **35.77% ± 6.81%** | 1.2 | 1.25 |
| **1D-CNN (self-trained)** | 72.72% ± 8.11% | 82.59% ± 7.01% | **34.56% ± 8.17%** | 48.5 | 450.0 |

**Under honest, identically-split evaluation, macro F1 is statistically comparable between the two architectures** (35.77% vs. 34.56%, well within each other's variance) — NeuroHDC's point estimate is marginally higher, though this should be read as a tie given the overlapping ±6.81/±8.17 spread, not a win either way. The CNN retains a modest edge in strict and binary accuracy. NeuroHDC achieves this comparable classification performance at **~40x lower latency and ~360x lower energy per inference**.

**Deployment context:** NeuroHDC's latency/energy figures are derived from a 100 MHz FPGA implementation; the CNN figures represent optimized inference on an ARM Cortex-M4F SoC — a deliberate cross-platform comparison reflecting each architecture's natural deployment target.

### Latency Breakdown and Cycle Accounting

The 1.2 ms NeuroHDC latency (120,000 cycles at 100 MHz) represents the full end-to-end system pipeline, not just core compute:

- **Compute core (288 cycles):** hypervector encoding + associative memory (Hamming distance) comparison logic.
- **System overhead (~119,712 cycles):** data buffering, AXI-bus data movement, windowing/tokenization, and non-parallelized control logic.

We report the full system figure rather than the core-only figure because data-movement overhead is typically the dominant real-world cost and is often omitted in algorithm-only papers.

---

## 🔬 3. Hyperparameter Sensitivity: Dimension Ablation

To justify the chosen hypervector dimensionality, we swept D ∈ {1024, 2048, 4096, 8192} on a single validation fold (pre-dating the patient-isolated protocol adopted for final results):

| Dimension (D) | Val-Accuracy (%) |
|---|---:|
| 1024 | 88.42 |
| 2048 | 92.15 |
| **4096 (chosen)** | **95.85** |
| 8192 | 96.02 |

- **D = 1024:** insufficient spatial capacity — loss of vector orthogonality ("crowding").
- **D = 4096:** the Pareto-optimal point where spatial capacity matches ECG morphological complexity.
- **D = 8192:** diminishing returns and a 2x hardware memory penalty for negligible accuracy gain.

**Consistency note:** these values reflect a single-fold, pre-patient-isolation validation run used to expedite hyperparameter search, and should not be numerically compared to the patient-isolated 5-fold averages in Section 2.

---

## ⚠️ 4. Rhythm Binding: A Tale of Two Failure Modes

R-R interval rhythm binding (Stage 5) was tested as an architectural response to timing-based classification errors. It behaves very differently depending on the *nature* of the timing irregularity:

### 4.1 MIT-BIH — Isolated Ectopic Beats: Rhythm Binding Helps, Inconsistently

Rhythm binding improved MIT-BIH's aggregate macro F1 (32.69% → 35.77%), but the effect is fold-dependent, not uniform:

| Fold | Rhythm OFF (F1) | Rhythm ON (F1) | Δ |
|---|---:|---:|---:|
| 1 | 27.74% | 41.26% | +13.52 |
| 2 | 32.62% | 23.66% | −8.96 |
| 3 | 32.52% | 33.25% | +0.73 |
| 4 | 46.15% | 42.15% | −4.00 |
| 5 | 24.40% | 38.54% | +14.14 |

This pattern correlates, at the extremes, with how much PAC (Premature Atrial Contraction) training data each fold's split leaves available: Fold 2 — the fold where rhythm binding hurts most — has only ~1,053 PAC training examples (the entire dataset's PAC beats are heavily clustered in a small number of patients, and Fold 2 happens to hold out the patients carrying the majority of them), while Fold 1 and Fold 5, where rhythm binding helps most, have over 2x that. The relationship is directionally consistent at the extremes but not clean across all five folds — a fair characterization is that PAC training-set size is *a contributing factor*, not a fully deterministic explanation, and per-patient morphology variability likely also plays a role.

### 4.2 PhysioNet — Non-Stationary AFib: Rhythm Binding Does Not Help

Applying the same rhythm-binding mechanism to PhysioNet's AFib classification task did not improve performance — under a clean, consistent evaluation protocol (both configurations taxonomy-corrected, Noisy class excluded from macro-F1):

| Configuration | Macro F1 |
|---|---:|
| Rhythm OFF | **47.58% ± 0.50%** |
| Rhythm ON | **45.05% ± 0.80%** |
| Δ | −2.53 points |

The likely mechanism: MIT-BIH's PACs are isolated events — a single short R-R interval against an otherwise stable, predictable rhythm, which a simple SHORT/NORMAL/LONG bucketing captures well. Atrial fibrillation is clinically defined as *irregularly irregular* — there is no stable baseline rhythm for a fixed bucketing scheme to measure deviation against, so the discrete R-R tokenization likely adds noise rather than signal for this specific arrhythmia. Unlike the MIT-BIH result, this effect is consistent and low-variance across all 5 folds (rhythm-off SD 0.50 vs. rhythm-on SD 0.80), making it a more confidently reportable negative result than the MIT-BIH PAC finding.

---

## 📐 5. Evaluation Methodology Alignment with Literature Convention

To make comparisons against published baselines as fair as reasonably possible, two adjustments were made to the evaluation protocol, and are disclosed explicitly here rather than left implicit:

- **PhysioNet 2017 (Noisy class):** the official CinC 2017 challenge scoring excludes noisy *recordings* from the dataset prior to scoring. Our implementation instead excludes the `Noisy` class from the macro-F1 average while still training the model to recognize it as a class — a related but not identical evaluation choice. Any beat with true label Normal/AFib/Other that is *predicted* as Noisy still counts as an error for its true class. This should be described precisely as such in any manuscript, rather than claimed as an exact reproduction of the official protocol.
- **MIT-BIH (AAMI EC57 grouping):** binary (Normal vs. anomaly) accuracy groups LBBB and RBBB into the Normal superclass, consistent with the AAMI EC57 convention used by most cited MIT-BIH literature, rather than treating conduction-block morphology as anomalous. The 5-class strict accuracy and macro F1 figures are unaffected by this and still report all five classes (Normal, PAC, PVC, LBBB, RBBB) separately.

---

## ⚡ 6. Hardware Validation

### 6.1 RTL / Software Bit-True Verification

- **Bit-true precision:** the Verilog implementation (`hw/rtl/`) was validated against the Python software encoder using **cocotb** RTL simulation across four independently seeded runs, showing 0-bit Hamming distance variance between hardware and software output on every run.

### 6.2 FPGA Power Estimation

- Evaluated via Xilinx Vivado post-synthesis power reports, targeting Zynq-7000 / Artix-7 fabric. **Dynamic core power is < 1.0 mW**; total on-chip power (dominated by fixed FPGA fabric static leakage, not architectural activity) is ~92 mW. The dynamic figure is the architecturally meaningful one; static leakage on FPGA reflects reconfigurable-fabric overhead that would not be present on a custom ASIC.

### 6.3 ASIC Implementation & Activity-Annotated Power (SkyWater 130nm)

The core datapath was synthesized, placed, and routed through the open-source OpenLane flow targeting the SkyWater 130nm PDK (`sky130_fd_sc_hd`), achieving a fully signed-off GDSII layout at 50 MHz with **zero setup/hold timing violations**.

**Methodology:** to avoid severe routing congestion from a full 4096-bit register file, a 2-fold slice (D = 256) containing the complete Boolean datapath (Delta-Tokenizer logic, MUX structures, and parallel Popcount adder trees) was synthesized, placed, and routed. Dynamic power was validated via **activity-annotated Gate-Level Simulation (GLS)**: the synthesized `top_shde_wrapper` netlist was simulated against Sky130 standard cell primitives (`sky130_fd_sc_hd.v`) using `iverilog`, driven by real sparse ECG test vectors, producing a VCD from which OpenROAD (`read_power_activities`) mapped **297,300 physical pin activities** for high-fidelity power annotation — not default toggle-rate estimation.

**Result:** total active power for the 2-fold slice was **5.85 mW**, with switching power minimized to **1.00 mW (17.1%)** due to the ECG data's inherent sparsity, while internal power — dominated by clock distribution and sequential flip-flop toggling, which occurs every cycle regardless of data sparsity — accounted for **4.85 mW (82.9%)** of the total.

| Component | Power | Share |
|---|---:|---:|
| Internal (clock tree + FF toggling) | 4.85 mW | 82.9% |
| Switching (data-dependent) | 1.00 mW | 17.1% |
| **Total (2-fold slice)** | **5.85 mW** | 100% |

**Methodological constraints (disclosed explicitly):**
- **Full-architecture projection:** full-chip dynamic power is estimated at **93.6 mW**, via linear extrapolation (16x) of the routed 2-fold slice. This is an idealized lower bound -- it does not model the non-linear routing congestion or extended clock-tree buffering that a full 32-fold planar layout would require, and should not be read as a signed-off full-chip result.
- **Macro leakage excluded:** the reported figures reflect logic and clock distribution only. Static leakage and dynamic read/write energy for the prototype SRAM storage macros were excluded from this synthesis run (no memory macro was compiled) and remain unmodeled.
- **Resizer optimization disabled:** to prioritize flow completion for this power/area estimate, standard-cell resizer optimizations were disabled; the design carries max slew/fanout/capacitance warnings at the typical corner that a production-grade closure pass would need to address.
- **Future work -- clock gating:** the 82.9% internal-power dominance identifies architectural clock gating (disabling the clock tree to inactive datapath blocks during sparse periods) as the highest-leverage optimization for a future iteration of this accelerator.
- **Process node:** SkyWater 130nm is a legacy node; a modern low-power node (e.g., 22nm or below) would be expected to reduce these figures substantially, though this has not been evaluated.

---

## 📁 7. Repository Structure & Reproducibility

```text
NeuroHDC/
│
├── src/
│   ├── data_loader.py
│   ├── tokenizer.py
│   ├── hdc_encoding.py
│   └── associative_mem.py
│
├── notebooks/
│   └── benchmark_notebook.ipynb
│
├── scripts/
│   ├── 01_train_python.py        # NeuroHDC patient-isolated 5-fold CV training
│   ├── 03_train_baselines.py     # Self-trained 1D-CNN baseline (patient-isolated, matches NeuroHDC split)
│   └── export_vectors.py         # Export binary test vectors for Verilog testbenches
│
├── hw/
│   ├── rtl/                      # Synthesizable Verilog modules
│   ├── tb/                       # Testbenches
│   └── cocotb/                   # Bit-true verification framework
│
├── Research Papers/               # Curated literature supporting the algorithmic baselines
│
├── *.pkl                          # Class prototype checkpoints (see below)
│
└── README.md
```

| Folder | Description |
|---|---|
| **src/** | Modular Python implementation: `data_loader.py`, `tokenizer.py`, `hdc_encoding.py`, `associative_mem.py`. |
| **notebooks/** | End-to-end evaluation, visualization, and literature comparison. |
| **scripts/** | Training pipelines for NeuroHDC and the self-trained baseline, plus Verilog test-vector export. |
| **hw/** | Synthesizable RTL (Verilog) and cocotb verification framework. |
| **Research Papers/** | Curated literature validating the algorithmic and baseline comparisons. |
| **Model checkpoints (`*.pkl`)** | Serialized class prototypes generated by `scripts/01_train_python.py`, patient-isolated 5-fold CV (seed = 42). |

### Reproducibility settings

| Parameter | Value |
|---|---|
| Train/Test protocol | `StratifiedGroupKFold`, 5 folds, split by patient/record |
| Random seed | 42 (deterministic per-fold RNG; reruns are bit-identical) |
| Balancing cap | 12,000 Normal / 3,000 per anomaly class |
| Hypervector dimension | 4096 |
| Rhythm binding | Enabled for MIT-BIH; tested and found ineffective for PhysioNet (Sec. 4.2) |

---

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone https://github.com/LohitMoharana/NeuroHDC.git
cd NeuroHDC

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the self-trained CNN baseline
python scripts/03_train_baselines.py

# 4. Run NeuroHDC with patient-isolated 5-fold cross-validation
python scripts/01_train_python.py

# 5. Explore results interactively
jupyter notebook notebooks/benchmark_notebook.ipynb
```

---

## 📚 8. References & Literature Baselines

### 8.1 Core Architecture Foundations

**Foundational HDC:**
Kanerva, P. (2009). *[Hyperdimensional Computing: An Introduction to Computing in Distributed Representation with High-Dimensional Random Vectors.](https://redwood.berkeley.edu/wp-content/uploads/2018/01/kanerva2009hyperdimensional.pdf)* Cognitive Computation, 1(2), 139–159.

**One-Shot Physiological Learning:**
Rahimi, A., et al. (2016). *[Hyperdimensional Computing for Blind and One-Shot Classification of EEG Error-Related Potentials.](https://iis-people.ee.ethz.ch/~arahimi/papers/MONET17.pdf)* 50th Asilomar Conference on Signals, Systems and Computers.

**In-Memory / Zero-MAC Hardware:**
Karunaratne, G., et al. (2020). *[In-memory Hyperdimensional Computing.](https://redwood.berkeley.edu/wp-content/uploads/2021/08/Karunaratne2020.pdf)* Nature Electronics, 3(6), 327–337.

**Signal Pre-processing:**
Pan, J., & Tompkins, W. J. (1985). *[A Real-Time QRS Detection Algorithm.](https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf)* IEEE Transactions on Biomedical Engineering, (3), 230–236.

**Inter-Patient Evaluation Protocol:**
de Chazal, P., O'Dwyer, M., & Reilly, R. B. (2004). *Automatic classification of heartbeats using ECG morphology and heartbeat interval features.* IEEE Transactions on Biomedical Engineering, 51(7), 1196–1206.

> ⚠️ **Note on quantitative claims below:** specific accuracy/F1 figures attributed to comparison papers in this section (e.g., "~83–86%", "~89%", "~86.5%") have **not been independently verified against the source papers** as part of this review and should be confirmed by reading each cited paper directly before being stated as fact in a manuscript. Treat them as placeholders pending verification, not confirmed figures.

### 8.2 Comparative Baseline Papers (by dataset)

**A. MIT-BIH Arrhythmia Database**
- Kiranyaz, S., et al. (2015). *[Real-Time Patient-Specific ECG Classification by 1-D Convolutional Neural Networks.](https://ieeexplore.ieee.org/document/7202837)* — intra-patient evaluation; not directly comparable without adjustment.
- Kachuee, M., et al. (2018). *[ECG Heartbeat Classification: A Deep Transferable Representation.](https://arxiv.org/pdf/1805.00794)* — intra-patient (random beat split) evaluation; reported >97% accuracy is not comparable to inter-patient results without this caveat stated explicitly.
- Luo, J., et al. (2020). *[A Spiking Neural Network-Based ECG Classification System for Wearable Edge Devices.](https://openreview.net/pdf?id=V8yemRAs00-)* — neuromorphic comparator; verify whether their reported accuracy is intra- or inter-patient before citing as a direct comparison.
- de Chazal, P., et al. (2004) — see above; the standard inter-patient reference point for MIT-BIH.

**B. PTB Diagnostic ECG Database (Myocardial Infarction)**
- Acharya, U. R., et al. (2017). *[Application of Deep Convolutional Neural Network for Automated Detection of Myocardial Infarction Using ECG Signals.](https://www.researchgate.net/publication/317821702_Application_of_Deep_Convolutional_Neural_Network_for_Automated_Detection_of_Myocardial_Infarction_Using_ECG_Signals)*
- Darmawahyuni, A., et al. (2019). *[Deep Learning with a Recurrent Network Structure in the Automated Detection and Classification of Abnormality in ECG.](https://www.mdpi.com/1999-4893/12/6/118)*
- Sharma, L. N., et al. (2015). *[Multiscale Energy and Eigenspace Approach to Detection and Localization of Myocardial Infarction.](https://ieeexplore.ieee.org/document/7047810)*

**C. European ST-T Database (Ischemia)**
- Pławiak, P. (2018). *[Novel Methodology of Cardiac Health Recognition Based on ECG Signals and Evolutionary-Neural System.](https://www.academia.edu/35066469/Novel_Methodology_of_Cardiac_Health_Recognition_Based_on_ECG_Signals_and_Evolutionary_Neural_System)*
- Papaloukas, C., et al. (2002). *[An Ischemia Detection Method Based on Artificial Neural Networks.](https://www.cs.uoi.gr/~arly/papers/ischemia_neural.pdf)*
- Safdarian, N., et al. (2014). *[A New Pattern Recognition Method for Detection and Localization of Myocardial Ischemia in ECG Signals.](https://www.researchgate.net/publication/270808246_A_New_Pattern_Recognition_Method_for_Detection_and_Localization_of_Myocardial_Infarction_Using_T-Wave_Integral_and_Total_Integral_as_Extracted_Features_from_One_Cycle_of_ECG_Signal)*
- Smrdel, A., & Jager, F. (2004). *Automated detection of transient ST-segment episodes in 24h ambulatory ECG recordings.* Medical & Biological Engineering & Computing. *(cited via secondary source — verify directly before use.)*

**D. PhysioNet 2017 Challenge (AFib)**
- Clifford, G. D., et al. (2017). *[AF Classification from a Short Single Lead ECG Recording: The PhysioNet/Computing in Cardiology Challenge 2017.](https://ieeexplore.ieee.org/document/8331486)*
- Zihlmann, M., et al. (2017). *[Convolutional Recurrent Neural Networks for Electrocardiogram Classification.](https://ieeexplore.ieee.org/document/8331491)*
- Teijeiro, T., et al. (2017). *[Abductive Reasoning as the Basis to Reproduce Expert Criteria in ECG Atrial Fibrillation Identification.](https://arxiv.org/pdf/1802.05998)*

---

## 🎯 Key Contributions

- Zero-MAC Edge-AI ECG classifier using Spiking-Hyperdimensional Computing
- Event-driven sparse computation (>93% token sparsity)
- Boolean-only inference — no floating-point arithmetic
- **Strict patient-isolated (inter-patient) 5-fold cross-validation** across four clinical datasets — no beat-level leakage between train and test
- Self-trained CNN baseline, re-validated under the identical patient-isolated protocol — revealing that ~26 points of its earlier apparent accuracy advantage were a beat-level leakage artifact, not genuine generalization
- R-R interval permutation-binding architectural extension, with an honest, mechanistically-explained account of where it helps (isolated ectopic beats) and where it doesn't (non-stationary AFib, confirmed via a clean same-protocol ablation)
- Data-backed failure analysis (confusion matrices + per-fold class distribution) explaining observed variance rather than treating it as unexplained noise
- FPGA-ready Verilog implementation with bit-true software/hardware verification
- Sub-milliwatt dynamic power, audited down to cycle-level latency accounting

---

## 📜 License

Distributed under the **MIT License**. Developed for robust, sub-milliwatt cardiac diagnostics at the extreme edge.

## ⭐ Citation

If you use NeuroHDC in your research, please cite this repository:

```bibtex
@software{NeuroHDC2026,
  author = {Lohit Moharana},
  title = {NeuroHDC: High-Efficiency Edge-AI ECG Classification using Spiking-Hyperdimensional Computing},
  year = {2026},
  url = {https://github.com/LohitMoharana/NeuroHDC}
}
```

<p align="center">

### ⚡ Ultra-Low Power • Zero MAC • FPGA Ready • Edge AI for Wearable Healthcare

⭐ Star the repository if you find this work useful!

</p>
