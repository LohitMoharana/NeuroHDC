# Related-work notes (revision prep, NOT part of the submitted paper)

Source: the 9 PDFs in `Research Papers/`, text-extracted with pypdf and read at abstract level
(title/abstract/first page). Every statement below is taken from those first pages. Nothing here comes from
memory of other literature, and no citation outside the folder is introduced.

## What each PDF is

| File | What it is (from its own abstract) | Relation to NeuroHDC |
|---|---|---|
| [1] Kanerva 2009 | Foundational hyperdimensional computing paper (32 pp). | HDC background: binding, bundling, similarity. |
| [2] Rahimi et al. 2017 (Mobile Netw Appl) | One-shot, blind classification of EEG error-related potentials; reports 74.5% vs 69.5% single-trial accuracy against a conventional method. | HDC applied to a biosignal with one-shot learning. This is EEG, not ECG. |
| [3] Karunaratne et al. (In-memory HDC, IBM/ETH) | Complete in-memory HDC system on 760,000 phase-change memory devices; language, news and EMG gesture tasks. | HDC associative memory in hardware (analog in-memory). NeuroHDC is a digital CMOS/FPGA design. |
| [4] Pan and Tompkins 1985 (IEEE TBME) | Real-time QRS detector; reports 99.3% of QRS complexes detected on MIT/BIH. | Basis of the Pan-Tompkins sensitivity analysis in `revision/pan_tompkins.py`. Note: that file is my own implementation, not code from the paper. |
| CLDV (Du et al.) | Survey and cross-layer co-design of vector-symbolic hardware (analog, mixed-signal, digital); proposes an in-memory hierarchical cognition system. | Context for where NeuroHDC's digital FPGA/ASIC datapath sits among VSA hardware styles. |
| HDDSNN (Kinavuidi et al., Neuromorph. Comput. Eng. 2026) | Hyperdimensional decoding of spiking neural networks; reports spike-count reductions of 1.74x-3.36x (DvsGesture) and 1.36x-2.70x (SL-Animals-DVS). | Event-sparse processing plus HDC. Different input (event cameras) and different sparsity source. |
| HyperGRAF (Chen et al.) | First HDC graph-reasoning accelerator on FPGA; reports over 100x speedup and energy efficiency versus NVIDIA Jetson Orin. | FPGA HDC accelerator for a different task (graphs). |
| MTSA (Schlegel et al., IV 2021) | HDC encoding of multivariate time series plus a feed-forward network for driving-style classification; accuracy comparable to or slightly above LSTM. | HDC for time series. Uses a neural network back end, not an associative memory. |
| SpikeHD (Zou et al., Sci. Rep. 2022) | SNN feature extractor followed by HDC classifier; claims better learning capability, robustness and smaller networks than an SNN alone. | Combines event-based spikes with HDC. NeuroHDC's tokenizer/zero-token path is a non-spiking analogue. |

## What the folder does NOT contain (gap, not closed)

* **No prior ECG-specific HDC paper is in the folder.** There is therefore no direct ECG HDC baseline to compare
  against from this material. I will not add ECG-HDC citations from memory. If the reviewers ask for them, the
  author must supply the references.
* No prior zero-MAC / event-sparse ECG accelerator paper and no prior HDC-on-FPGA ECG paper is in the folder.
* The comparison with CNN (72.15 / 34.47) and ResNet (76.00 / 39.48) in the paper is NeuroHDC's own
  baselines, not literature numbers.

## What can be said safely from these sources

1. HDC has been applied to biosignals with one-shot or few-shot learning ([2], EEG), to time series (MTSA), and to
   gesture/EMG ([3]).
2. HDC hardware spans analog in-memory ([3]), mixed-signal and digital styles (CLDV survey). NeuroHDC is a digital
   design, so [3] and CLDV are the natural contrast.
3. Event-driven or spike-sparse processing has been combined with HDC before (SpikeHD, HDDSNN) for event-based
   data. NeuroHDC's contribution is sparsity of a delta-tokenized ECG window, not spikes from an event sensor.
4. Pan-Tompkins [4] is the standard QRS detector, which supports using it as the R-peak source in the causal R-R
   sensitivity analysis.

## Caveats

* Only first pages were read for the five non-foundational papers; methods and result tables were not
  audited. Do not quote their numbers beyond the abstract-level figures above without reading the full text.
* Extracted PDF [4] has spacing artefacts from the scan; the abstract figures were readable.

## Full-text verification of the five remaining papers (second pass)

Searched the extracted full text of CLDV, HDDSNN, HyperGRAF, MTSA and SpikeHD for ECG/arrhythmia, FPGA/ASIC,
power, sparsity and multiplier terms, then read the matching passages.

* **None of the five mentions ECG, arrhythmia or any cardiac task** (searches for "ecg", "electrocardio",
  "arrhythm" returned nothing in these five). They therefore cannot serve as ECG baselines.
* **HyperGRAF** (verified, Table II): Xilinx Alveo U50 at 200 MHz, 29.8 W, 589.1K LUT (83.6%), 2048 DSP (41.6%),
  238 BRAM. Task is graph reasoning on a CPU-FPGA platform with PCIe; it claims over 100x speed and 10x energy
  gains over Jetson Orin and DPIM respectively. Not comparable to NeuroHDC (XC7Z010, 5,321 LUT, 0 DSP, ECG);
  useful only as a contrast in platform class and DSP use.
* **HDDSNN** (verified): states a 45 nm figure of 0.1 pJ for a 32-bit add versus 3.1 pJ for a 32-bit multiply
  (citing its ref. [45]) to motivate multiplication-free decoding; estimates energy from synaptic operations at
  26 pJ per SOP (TrueNorth). This supports the general motivation for avoiding multipliers, but is a secondary
  citation of ref. [45]; the original source would need to be obtained before NeuroHDC cites that figure.
* **SpikeHD** (verified): reports 6.1% (MNIST) and 3.8% (DVS Gesture) higher accuracy than an SNN alone, and an
  average 5.7% / 3.2% gain in its comparison against DECOLLE. Image/event-camera tasks only.
* **MTSA** (verified): table of F1 scores for driving-style classification (LSTM [4] about 0.91 / 0.82 / 0.88 on one
  setting and about 0.43 / 0.48 / 0.41 on another). Tabular values read from the extracted text only; the
  setting labels were not audited.
* **CLDV** (verified): Table I lists cross-layer features such as "controlled sparsity level -> density-thinning
  logic -> sparse event recognition", "variable vector lengths -> temporal vector folding", and, among
  surveyed designs, "Shift-ACCumulate instead of MAC" and "HV chunk fragmentation". These show that sparsity,
  MAC-free arithmetic and chunked/folded hypervector datapaths each have prior art in VSA hardware, so
  novelty claims should be worded as the *combination for ECG with the measured FPGA/ASIC flow*, not as
  first use of any single technique. Only the survey's own table text was read, not the cited works.

Still not verified: the cited works inside these surveys (CLDV refs [15], [52], [79], [125], etc.); the paper
folder does not contain them.

---
## Independent web search for ECG-specific HDC prior art (this session)

Method: web searches for ECG/arrhythmia + hyperdimensional computing, and + FPGA/ASIC, then fetch of the candidate
pages. All figures below come from fetched pages (small-model page summaries for some), NOT from reading the PDFs
in full; each must be re-checked against the paper before it is cited. No identifying project data was sent.

| Work | What it is | Verified how | Relevance |
|---|---|---|---|
| W. Xu and K. K. Parhi, "Multi-Class Classification of Abnormal Heartbeat Detection using Hyperdimensional Computing", J. Signal Process. Syst. 96(8):463-477, 2024, doi 10.1007/s11265-024-01931-w | HDC for multi-class heartbeat detection on MIT-BIH and INCART; mRMR vs AUC-ranked feature selection; over 80% test accuracy in One-vs-One with 100-bit seed hypervectors; compared with SVM and MLP. | Publisher record page (UMN experts) abstract; Springer full text was behind a login and not read. | Direct HDC-for-ECG prior art. Software classification, no FPGA/ASIC in the abstract; hand-picked features, not an event-sparse tokenizer. |
| B. W. Ung, L. Ge, K. K. Parhi, "Premature Ventricular Contraction Beat Classification via Hyperdimensional Computing", Proc. Asilomar 2022, pp. 1306-1310, doi 10.1109/IEEECONF56349.2022.10052044 | **Verified from the free accepted manuscript** (https://par.nsf.gov/servlets/purl/10400855, 5 pages, text read): binary HDC, PVC-vs-normal only, MIT-BIH, 164 hand-crafted features (6 HRV, 22 temporal, 136 spectral) from annotated R peaks, mRMR keeps 5/10/20; three encodings; d = 100-2000; best (Approach 2, 20 features) 97.7% accuracy / 90.4% sensitivity / 98.4% specificity / 85.1% precision / AUC 0.944, versus 99.4% for CNN+LSTM in its Table IV. Evaluation: two recording groups of 22 (paced records excluded), train on first 5 min, test on remaining 25 min. | Earlier HDC-for-ECG prior art, binary PVC only. Uses annotated R peaks and HRV (like NeuroHDC's rhythm binding), has no FPGA/ASIC implementation (stated as future work). **Correction:** my earlier note that its abstract says HD trails SVM for two subjects came from a search summary and is NOT in this paper's text; do not cite it. |
| A. Tran, K. Tran, C. Do, "ECG-LDC: A Hardware-Efficient Low-Dimensional Computing Framework for ECG Arrhythmia Classification", arXiv 2607.09680 (v1; the fetch reported "submitted 13 June 2026" although the id suggests July 2026 - confirm), eess.SP, unreviewed preprint | Low-Dimensional Computing (a VSA relative, not HDC proper), dual codebooks (morphology + R-R), 5 AAMI classes on MIT-BIH, Pynq-Z2 FPGA prototype. | arXiv HTML page extracted; full PDF not read in full. | Closest competitor on the FPGA side. See comparison below. |
| "Always-on Hyperdimensional Heartbeats" (IEEE), HD3C (arXiv 2509.14617) | HDC on heart-sound (phonocardiogram) data, not ECG. | Search summaries only. | Not ECG; do not cite as ECG prior art. |

### ECG-LDC vs NeuroHDC (numbers as extracted from ECG-LDC; NeuroHDC numbers from the frozen paper)

| Item | ECG-LDC (as extracted) | NeuroHDC (submitted) |
|---|---|---|
| Evaluation protocol | MIT-BIH, **random 70/30 split, apparently at beat level** (no patient-wise split described) | Record-grouped StratifiedGroupKFold, 5 folds, no record in both train and test |
| Classes / headline | 5 AAMI classes; accuracy 97.18%, macro-F1 87.38% | MIT-BIH 70.99±5.83 acc / 35.77±6.81 macro-F1 |
| FPGA | Pynq-Z2; core 5,652 LUT / 4,790 FF / 4 BRAM / 0 DSP; full system 8,255 LUT / 8,296 FF / 6 BRAM / 0 DSP | XC7Z010, 5,321 LUT / 8,760 FF / 42 BRAM / 0 DSP (no PS) |
| Clock, power | 50 MHz; full system about 1.71 W (138 mW static + 1,571 mW dynamic, includes the processing system) | 1.0 mW dynamic tool estimate at 1 MHz (re-run at 100 MHz: 0.132 W) |
| Memory / dimension | 3.86 kB model, 256-bit hypervectors | D=4096 |

Cautions for any comparison paragraph:
1. **The accuracy figures are not comparable.** A random beat-level split leaks same-patient beats across train and
   test; NeuroHDC's record-grouped protocol does not. The paper must not set 70.99 against 97.18 without saying so.
2. **The power figures are not comparable**: ECG-LDC's 1.71 W is a full Zynq system including the ARM processing system;
   NeuroHDC's 1.0 mW is an out-of-context PL-only tool estimate at 1 MHz.
3. ECG-LDC uses LDC, not HDC, and trains with gradient-based methods (per its title/abstract); I did not verify details.
4. ECG-LDC lacks a PS-free number and includes an AXI subsystem; NeuroHDC's design is PL-only and includes no host interface.

### Gap status
Closed as far as possible without full-text access: ECG-specific HDC prior art now identified (Xu & Parhi 2024;
Ung, Ge, Parhi 2022) plus a closest FPGA competitor (ECG-LDC). Still needed from the author: read the full texts and
decide the citations; no BibTeX entries were generated here.

### Addendum: Xu and Parhi 2024 abstract (as pasted by the author)
The abstract matches the UMN record already noted: HDC multi-class beat detection on MIT-BIH and INCART; four feature types;
mRMR vs AUC-ranking feature selection; concatenated encoding; AUC-ranking beats mRMR in one-vs-rest; over 80% test accuracy in
one-vs-one with 100-bit seed hypervectors; stable versus SVM and MLP. Closed access (Semantic Scholar reports no open-access PDF),
so nothing beyond the abstract has been read. The Asilomar paper's reference [2] (L. Ge and K. K. Parhi, "Classification using
hyperdimensional computing: a review", IEEE Circuits and Systems Magazine 20(2):30-47, 2020) is a candidate survey citation; it
is known only from that reference list and was not itself opened.

### Positioning consequence
Both Parhi-group papers use hand-crafted features (annotated R peaks, HRV, spectral/wavelet), report software results only,
and (Asilomar) state FPGA implementation as future work. NeuroHDC differs by using a delta-tokenised event-sparse encoding of the
raw window, a zero-MAC datapath, and measured FPGA/ASIC flows. Their protocol is group-specific with training on the same recordings'
first 5 minutes in part, so their accuracy numbers are not comparable to NeuroHDC's record-grouped five-fold results.
