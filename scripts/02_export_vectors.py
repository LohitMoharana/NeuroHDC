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
# Ensure this matches what you used in training!
# ==========================================
TARGET_DATASET = "MITBIH"  # Options: "MITBIH", "PTB", "STT", "PHYSIONET"


def bipolar_to_binstr(vec):
    """
    Converts a Numpy array of Bipolar {-1, 1} or Boolean {0, 1} values
    into a continuous string of '0's and '1's for Verilog $readmemb().
    """
    return "".join(['1' if v > 0 else '0' for v in vec])


def main():
    print(f"--- Phase 2: Exporting {TARGET_DATASET} HDC Memory to Hardware ---")

    # Paths setup
    PROJ_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    EXPORT_DIR = os.path.join(PROJ_DIR, 'hw', 'tb', 'data')
    os.makedirs(EXPORT_DIR, exist_ok=True)

    config = SHDEConfig()
    encoder = HDCEncoder(config)

    # 1. Export Base Memory (Channel, Item, Position)
    print("\n[1] Exporting Base Memory Vectors...")
    with open(os.path.join(EXPORT_DIR, 'channel_memory.dat'), 'w') as f:
        for ch_vec in encoder.channel_memory: f.write(bipolar_to_binstr(ch_vec) + "\n")
    with open(os.path.join(EXPORT_DIR, 'item_memory.dat'), 'w') as f:
        f.write(bipolar_to_binstr(encoder.item_memory[1]) + "\n")
        f.write(bipolar_to_binstr(encoder.item_memory[-1]) + "\n")
    with open(os.path.join(EXPORT_DIR, 'pos_memory.dat'), 'w') as f:
        for pos_vec in encoder.pos_memory: f.write(bipolar_to_binstr(pos_vec) + "\n")
    print(f"  -> Saved Base Vectors to {EXPORT_DIR}")

    # 2. Export Trained Prototypes
    print("\n[2] Exporting Trained Prototypes...")
    proto_path = os.path.join(PROJ_DIR, f'shde_model_{TARGET_DATASET}.pkl')

    if not os.path.exists(proto_path):
        print(f"  -> ERROR: {proto_path} not found! Run 01_train_python.py first.")
        sys.exit(1)

    with open(proto_path, 'rb') as f:
        prototypes = pickle.load(f)

    class_list = list(prototypes.keys())
    with open(os.path.join(EXPORT_DIR, 'class_labels.txt'), 'w') as f:
        for idx, label in enumerate(class_list):
            f.write(f"{idx}: {label}\n")

    with open(os.path.join(EXPORT_DIR, 'prototypes.dat'), 'w') as f:
        for label in class_list:
            f.write(bipolar_to_binstr(prototypes[label]) + "\n")
    print("  -> Saved Prototypes & Label Map.")

    # 3. Export Golden Test Stimulus
    print(f"\n[3] Generating Golden Test Vectors for {TARGET_DATASET}...")
    tokenizer = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6])

    normal_wave, arr_wave = None, None
    normal_label, arr_label = None, None

    if TARGET_DATASET == "MITBIH":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "MIT-BIH")
        loader = MITBIHLoader(DATA_DIR)
        records = sorted([f.replace('.csv', '') for f in os.listdir(DATA_DIR) if f.endswith('.csv')])
        if records:
            X_rec, y_rec = loader.load_record(records[0])
        else:
            X_rec, y_rec = [], []

    elif TARGET_DATASET == "PTB":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "PTB")
        loader = PTBLoader(DATA_DIR)
        X_rec, y_rec = loader.load_dataset()

    elif TARGET_DATASET == "STT":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "STT")
        loader = STTLoader(DATA_DIR)
        # Load just a few beats to extract a quick golden vector
        X_rec, y_rec = loader.load_dataset(max_beats_per_file=5)

    elif TARGET_DATASET == "PHYSIONET":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "PhysioNet")
        loader = PhysioNetLoader(DATA_DIR)
        # Load just a few beats to extract a quick golden vector
        X_rec, y_rec = loader.load_dataset(max_beats_per_file=5)

    for wave, label in zip(X_rec, y_rec):
        if label == "Normal" and normal_wave is None:
            normal_wave = wave
            normal_label = label
        elif label != "Normal" and arr_wave is None:
            arr_wave = wave
            arr_label = label
        if normal_wave is not None and arr_wave is not None:
            break

    test_waves = [(normal_wave, normal_label), (arr_wave, arr_label)]

    with open(os.path.join(EXPORT_DIR, 'golden_stimulus_analog.dat'), 'w') as f_analog, \
            open(os.path.join(EXPORT_DIR, 'golden_stimulus_spikes.dat'), 'w') as f_spikes, \
            open(os.path.join(EXPORT_DIR, 'golden_expected_hv.dat'), 'w') as f_hv:

        for wave, label in test_waves:
            if wave is None: continue

            wave_int16 = (wave * 32767).astype(np.int16)
            f_analog.write(" ".join([str(val) for val in wave_int16]) + "\n")

            spikes = tokenizer.encode(wave)
            spike_str = ""
            for ch in range(spikes.shape[0]):
                for t in range(spikes.shape[1]):
                    val = spikes[ch, t]
                    if val == 1:
                        spike_str += "01_"
                    elif val == -1:
                        spike_str += "10_"
                    else:
                        spike_str += "00_"
            f_spikes.write(f"{spike_str.strip('_')}\n")

            hv = encoder.encode_sequence(spikes)
            f_hv.write(bipolar_to_binstr(hv) + "\n")

            print(f"  -> Extracted '{label}' Golden Vector.")

    print(f"\nExport complete. All files ready for Vivado/Cocotb in {EXPORT_DIR}")


if __name__ == "__main__":
    main()