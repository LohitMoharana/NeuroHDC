import sys
import os
import pickle
import numpy as np

# Add the project root to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import SHDEConfig
from src.hdc_encoding import HDCEncoder
from src.tokenizer import DeltaTokenizer
from src.data_loader import MITBIHLoader, PTBLoader, STTLoader, PhysioNetLoader

# ==========================================
# CONFIGURATION TOGGLE
# ==========================================
TARGET_DATASET = "STT"  # Options: "MITBIH", "PTB", "STT", "PHYSIONET"


def bipolar_to_binstr(vec):
    """Converts a Numpy array of Bipolar {-1, 1} or Boolean {0, 1} values into '0's and '1's."""
    return "".join(['1' if v > 0 else '0' for v in vec])


def main():
    print(f"--- Phase 2: Exporting {TARGET_DATASET} HDC Memory to Hardware ---")

    PROJ_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    EXPORT_DIR = os.path.join(PROJ_DIR, 'hw', 'tb', 'data')
    os.makedirs(EXPORT_DIR, exist_ok=True)

    config = SHDEConfig()
    encoder = HDCEncoder(config)

    # 1. Export Base Memory
    print("\n[1] Exporting Base Memory Vectors...")
    with open(os.path.join(EXPORT_DIR, 'channel_memory.dat'), 'w') as f:
        for ch_vec in encoder.channel_memory: f.write(bipolar_to_binstr(ch_vec) + "\n")
    with open(os.path.join(EXPORT_DIR, 'item_memory.dat'), 'w') as f:
        f.write(bipolar_to_binstr(encoder.item_memory[1]) + "\n")
        f.write(bipolar_to_binstr(encoder.item_memory[-1]) + "\n")
    with open(os.path.join(EXPORT_DIR, 'pos_memory.dat'), 'w') as f:
        for pos_vec in encoder.pos_memory: f.write(bipolar_to_binstr(pos_vec) + "\n")

    # 2. Export Trained Prototypes
    print("\n[2] Exporting Trained Prototypes...")
    proto_path = os.path.join(PROJ_DIR, f'nhdc__{TARGET_DATASET}.pkl')
    if not os.path.exists(proto_path):
        print(f"  -> ERROR: {proto_path} not found! Run 01_train_python.py first.")
        sys.exit(1)

    with open(proto_path, 'rb') as f:
        prototypes = pickle.load(f)

    class_list = list(prototypes.keys())
    with open(os.path.join(EXPORT_DIR, 'class_labels.txt'), 'w') as f:
        for idx, label in enumerate(class_list): f.write(f"{idx}: {label}\n")

    with open(os.path.join(EXPORT_DIR, 'prototypes.dat'), 'w') as f:
        for label in class_list: f.write(bipolar_to_binstr(prototypes[label]) + "\n")

    # 3. Export Golden Test Stimulus
    print(f"\n[3] Generating Golden Test Vectors for {TARGET_DATASET}...")
    tokenizer = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6])

    # Handle the unpack error by catching the extra return value (groups)
    if TARGET_DATASET == "MITBIH":
        loader = MITBIHLoader(os.path.join(PROJ_DIR, "Datasets", "MIT-BIH"))
        X_rec, y_rec = loader.load_record("100")  # Simplified for MIT-BIH
    elif TARGET_DATASET in ["PTB", "STT", "PHYSIONET"]:
        loader_map = {"PTB": PTBLoader, "STT": STTLoader, "PHYSIONET": PhysioNetLoader}
        loader = loader_map[TARGET_DATASET](os.path.join(PROJ_DIR, "Datasets", TARGET_DATASET))
        # Unpack up to 3 values: X, y, groups
        data = loader.load_dataset(max_beats_per_file=5)
        X_rec, y_rec = data[0], data[1]

    # Find one normal and one anomaly beat
    normal_wave, arr_wave = None, None
    normal_label, arr_label = None, None
    for wave, label in zip(X_rec, y_rec):
        if label == "Normal" and normal_wave is None:
            normal_wave, normal_label = wave, label
        elif label != "Normal" and arr_wave is None:
            arr_wave, arr_label = wave, label
        if normal_wave is not None and arr_wave is not None: break

    test_waves = [(normal_wave, normal_label), (arr_wave, arr_label)]

    # ... (Rest of file writing logic remains the same)
    with open(os.path.join(EXPORT_DIR, 'golden_stimulus_analog.dat'), 'w') as f_analog, \
            open(os.path.join(EXPORT_DIR, 'golden_stimulus_spikes.dat'), 'w') as f_spikes, \
            open(os.path.join(EXPORT_DIR, 'golden_expected_hv.dat'), 'w') as f_hv:
        for wave, label in test_waves:
            if wave is None: continue
            f_analog.write(" ".join([str(val) for val in (wave * 32767).astype(np.int16)]) + "\n")
            spikes = tokenizer.encode(wave)
            spike_str = "".join(['01_' if s == 1 else '10_' if s == -1 else '00_' for s in spikes.flatten()])
            f_spikes.write(f"{spike_str.strip('_')}\n")
            f_hv.write(bipolar_to_binstr(encoder.encode_sequence(spikes)) + "\n")
            print(f"  -> Extracted '{label}' Golden Vector.")


if __name__ == "__main__":
    main()