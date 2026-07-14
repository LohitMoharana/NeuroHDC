# 🧠 NeuroHDC: High-Efficiency Edge-AI ECG Classification using Spiking-Hyperdimensional Computing

<p align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Verilog](https://img.shields.io/badge/RTL-Verilog-orange.svg)
![FPGA](https://img.shields.io/badge/FPGA-Zynq%20%7C%20Artix--7-green.svg)
![License](https://img.shields.io/badge/License-MIT-red.svg)
![Status](https://img.shields.io/badge/Research-Prototype-success.svg)

</p>

> **Ultra-efficient, zero-multiplier Edge-AI ECG classification using Spiking Hyperdimensional Computing (HDC).**

NeuroHDC is a hardware-efficient framework for ECG arrhythmia classification. This repository contains the complete algorithmic proof-of-concept, dataset loaders, a self-trained deep learning baseline for fair comparison, 5-fold cross-validated benchmarking, and the bit-true Verilog hardware description for our proposed **Spiking-Hyperdimensional Computing (HDC)** architecture.

---

## 📄 Abstract

The deployment of deep learning (CNNs, LSTMs) on wearable, battery-powered medical devices is constrained by the **"Power Wall"** — the energy cost of floating-point Multiply-Accumulate (MAC) operations. NeuroHDC explores an alternative: a unified hardware-software architecture combining event-driven sparsity with the Boolean geometry of Hyperdimensional Computing (HDC). Analog ECG signals are tokenized into sparse events and encoded into a **4096-dimensional binary hyperspace**, eliminating MAC units from the inference datapath entirely.

Evaluated with 5-fold stratified cross-validation on the MIT-BIH Arrhythmia Database and compared directly against a self-trained 1D-CNN baseline on identical splits, NeuroHDC reaches **91.92% ± 0.23% accuracy** (vs. 98.66% ± 0.26% for the CNN) while using **pure XOR/Boolean logic** instead of MAC operations — trading roughly 7 points of accuracy for over two orders of magnitude in energy efficiency. The architecture was additionally validated for morphological anomaly detection on the PTB and European ST-T databases, and evaluated (with a documented failure mode) on the PhysioNet 2017 AFib Challenge dataset.

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
│ HDC XOR Encoder       │
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
│ Associative Memory    │
│ (Hamming Distance)    │
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
- **Exact Temporal Anchoring:** The approximate R-peak is detected using the **Pan–Tompkins algorithm**, refined with a local ±20-sample search for the absolute maximum, and anchored at the exact center (**t = 128**) of a **256-sample window (~0.85 seconds)**.
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

---

## 📊 2. Experimental Rigor: 5-Fold Cross-Validation

To ensure statistical stability, MIT-BIH results are reported using 5-fold stratified cross-validation (N = 100,023 samples). To avoid an apples-to-oranges comparison against literature-reported numbers, we self-trained a 1D-CNN baseline on the **exact same data splits**.

| Architecture | Accuracy (Avg ± SD) | F1-Score (Avg ± SD) | Latency (ms) | Energy (μJ/Inf) |
|---|---:|---:|---:|---:|
| **NeuroHDC (Ours)** | 91.92% ± 0.23% | 78.60% ± 0.29% | 1.2 | 1.25 |
| **1D-CNN (Self-Trained)** | 98.66% ± 0.26% | 95.39% ± 0.77% | 48.5 | 450.0 |

**Deployment context:** NeuroHDC figures are derived from a 100 MHz FPGA implementation; the 1D-CNN figures represent optimized inference on an ARM Cortex-M4F SoC. This cross-platform comparison is intentional — it reflects the natural deployment target for each architecture (hardware-accelerated Boolean logic vs. software MAC-based inference), rather than forcing both onto a platform that suits only one.

**Result:** NeuroHDC trades ~7 points of accuracy and ~17 points of F1 for a **~40x reduction in latency** and a **~360x reduction in energy per inference**.

### Latency Breakdown and Cycle Accounting

The 1.2 ms NeuroHDC latency (120,000 cycles at 100 MHz) represents the full end-to-end system pipeline, not just the core compute:

- **Compute core (288 cycles):** pure hypervector encoding + associative memory (Hamming distance) comparison logic.
- **System overhead (~119,712 cycles):** data buffering, AXI-bus data movement, windowing/tokenization, and non-parallelized control logic.

We report the full system figure rather than the core-only figure because data-movement overhead is typically the dominant real-world cost and is often omitted in algorithm-only papers.

---

## 🔬 3. Hyperparameter Sensitivity: Dimension Ablation

To justify the chosen hypervector dimensionality, we swept D ∈ {1024, 2048, 4096, 8192}:

| Dimension (D) | Val-Accuracy (%) |
|---|---:|
| 1024 | 88.42 |
| 2048 | 92.15 |
| **4096 (chosen)** | **95.85** |
| 8192 | 96.02 |

- **D = 1024:** insufficient spatial capacity — loss of vector orthogonality ("crowding").
- **D = 4096:** the Pareto-optimal point where spatial capacity matches ECG morphological complexity.
- **D = 8192:** diminishing returns and a 2x hardware memory penalty for negligible accuracy gain.

**Consistency note:** ablation values reflect performance on a single validation fold, used to expedite hyperparameter search. These differ from — and should not be directly compared to — the 5-fold test-set averages reported in Section 2.

---

## ⚠️ 4. PhysioNet 2017: A Data-Backed Failure Analysis

While Spiking-HDC performs well on morphological anomalies (MIT-BIH, PTB), evaluation on the PhysioNet 2017 AFib Challenge dataset reveals a clear limitation of fixed spatial windows for non-stationary rhythms.

**Multi-class confusion matrix** (cumulative predictions, N = 16,180):

| True \ Predicted | AFib | Normal | Other |
|---|---:|---:|---:|
| **AFib** | 832 | 165 | 521 |
| **Normal** | 2,336 | 7,100 | 250 |
| **Other** | 502 | 1,124 | 3,350 |

**Precision (AFib):** 832 / (832 + 2,336 + 502) = 832 / 3,670 ≈ **0.23**

**Mechanistic failure mode — the "spatial shift problem":** physiological variation in P-wave timing shifts the wave outside the fixed 0.85-second window. Because NeuroHDC encodes an exact temporal position, this shift is perceived as a "missing" or altered feature, causing a high rate of Normal/Other beats to be misclassified as AFib. This points to a specific, fixable direction (dynamic/adaptive windowing, or hybrid recurrent memory) rather than a fundamental dead end for the architecture.

---

## ⚡ 5. Hardware Validation

- **Bit-true precision:** the Verilog implementation (`hw/rtl/`) was validated against the Python software encoder using **cocotb** RTL simulation, showing 0-bit Hamming distance variance between the two.
- **Power estimation:** evaluated via Xilinx Vivado post-synthesis power reports, targeting Zynq-7000 / Artix-7 fabric. Estimated dynamic core power is **< 1.0 mW**.

---

## 📁 6. Repository Structure & Reproducibility

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
│   ├── 01_train_python.py        # NeuroHDC 5-fold CV training
│   ├── 03_train_baselines.py     # Self-trained 1D-CNN baseline
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
| **Model checkpoints (`*.pkl`)** | Serialized class prototypes in the root directory, generated by `scripts/01_train_python.py` using 5-fold CV (seed = 42). |

### Reproducibility settings

| Parameter | Value |
|---|---|
| Train/Test protocol | 5-fold stratified cross-validation |
| Random seed | 42 |
| Prototype cap | 5,000 samples/class |
| Hypervector dimension | 4096 |

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

# 4. Run NeuroHDC with 5-fold cross-validation
python scripts/01_train_python.py

# 5. Explore results interactively
jupyter notebook notebooks/benchmark_notebook.ipynb
```

---

## 📚 7. References & Literature Baselines

### 7.1 Core Architecture Foundations

**Foundational HDC**

Kanerva, P. (2009). 

*[Hyperdimensional Computing: An Introduction to Computing in Distributed Representation with High-Dimensional Random Vectors.](https://redwood.berkeley.edu/wp-content/uploads/2018/01/kanerva2009hyperdimensional.pdf)* Cognitive Computation, 1(2), 139–159.

**One-Shot Physiological Learning**

Rahimi, A., et al. (2016). 

*[Hyperdimensional Computing for Blind and One-Shot Classification of EEG Error-Related Potentials.](https://iis-people.ee.ethz.ch/~arahimi/papers/MONET17.pdf)* 50th Asilomar Conference on Signals, Systems and Computers.

**In-Memory / Zero-MAC Hardware**

Karunaratne, G., et al. (2020). 

*[In-memory Hyperdimensional Computing.](https://redwood.berkeley.edu/wp-content/uploads/2021/08/Karunaratne2020.pdf)* Nature Electronics, 3(6), 327–337.

**Signal Pre-processing**

Pan, J., & Tompkins, W. J. (1985). 

*[A Real-Time QRS Detection Algorithm.](https://www.robots.ox.ac.uk/~gari/teaching/cdt/A3/readings/ECG/Pan+Tompkins.pdf)* IEEE Transactions on Biomedical Engineering, (3), 230–236.

### 7.2 Comparative Baseline Papers

Baseline metrics discussed for broader context are drawn from the following dataset-specific studies. Note: the primary quantitative comparison in Section 2 uses our own self-trained CNN on identical splits — the papers below represent published literature ceilings, not 1-to-1 controlled comparisons.

**A. MIT-BIH Arrhythmia Database**
- Kiranyaz, S., et al. (2015). *[Real-Time Patient-Specific ECG Classification by 1-D Convolutional Neural Networks.](https://ieeexplore.ieee.org/document/7202837)*
- Kachuee, M., et al. (2018). *[ECG Heartbeat Classification: A Deep Transferable Representation.](https://arxiv.org/pdf/1805.00794)*
- Luo, J., et al. (2020). *[A Spiking Neural Network-Based ECG Classification System for Wearable Edge Devices.](https://openreview.net/pdf?id=V8yemRAs00-)*

**B. PTB Diagnostic ECG Database (Myocardial Infarction)**
- Acharya, U. R., et al. (2017). *[Application of Deep Convolutional Neural Network for Automated Detection of Myocardial Infarction Using ECG Signals.](https://www.researchgate.net/publication/317821702_Application_of_Deep_Convolutional_Neural_Network_for_Automated_Detection_of_Myocardial_Infarction_Using_ECG_Signals)*
- Darmawahyuni, A., et al. (2019). *[Deep Learning with a Recurrent Network Structure in the Automated Detection and Classification of Abnormality in ECG.](https://www.mdpi.com/1999-4893/12/6/118)*
- Sharma, L. N., et al. (2015). *[Multiscale Energy and Eigenspace Approach to Detection and Localization of Myocardial Infarction.](https://ieeexplore.ieee.org/document/7047810)*

**C. European ST-T Database (Ischemia)**
- Pławiak, P. (2018). *[Novel Methodology of Cardiac Health Recognition Based on ECG Signals and Evolutionary-Neural System.](https://www.academia.edu/35066469/Novel_Methodology_of_Cardiac_Health_Recognition_Based_on_ECG_Signals_and_Evolutionary_Neural_System)*
- Papaloukas, C., et al. (2002). *[An Ischemia Detection Method Based on Artificial Neural Networks.](https://www.cs.uoi.gr/~arly/papers/ischemia_neural.pdf)*
- Safdarian, N., et al. (2014). *[A New Pattern Recognition Method for Detection and Localization of Myocardial Ischemia in ECG Signals.](https://www.researchgate.net/publication/270808246_A_New_Pattern_Recognition_Method_for_Detection_and_Localization_of_Myocardial_Infarction_Using_T-Wave_Integral_and_Total_Integral_as_Extracted_Features_from_One_Cycle_of_ECG_Signal)*

**D. PhysioNet 2017 Challenge (AFib)**
- Clifford, G. D., et al. (2017). *[AF Classification from a Short Single Lead ECG Recording: The PhysioNet/Computing in Cardiology Challenge 2017.](https://ieeexplore.ieee.org/document/8331486)*
- Zihlmann, M., et al. (2017). *[Convolutional Recurrent Neural Networks for Electrocardiogram Classification.](https://ieeexplore.ieee.org/document/8331491)*
- Teijeiro, T., et al. (2017). *[Abductive Reasoning as the Basis to Reproduce Expert Criteria in ECG Atrial Fibrillation Identification.](https://arxiv.org/pdf/1802.05998)*

---

## 🎯 Key Contributions

- Zero-MAC Edge-AI ECG classifier using Spiking-Hyperdimensional Computing
- Event-driven sparse computation (>93% token sparsity)
- Boolean-only inference — no floating-point arithmetic
- Self-trained CNN baseline on identical splits for a fair accuracy/efficiency comparison
- 5-fold cross-validated results with reported variance
- Dimension ablation study justifying architectural choices
- Data-backed failure analysis (confusion matrix + mechanistic explanation) for known limitations
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
