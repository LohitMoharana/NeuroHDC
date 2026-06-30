import sys
import os
import numpy as np
import collections
import pickle

# Add the project root to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.associative_mem import AssociativeMemory
from src.data_loader import MITBIHLoader, PTBLoader, STTLoader, PhysioNetLoader


TARGET_DATASET = "MITBIH"  # Options: "MITBIH", "PTB", "STT", "PHYSIONET"


def main():
    print(f"--- Initializing Spiking-HDC Pipeline ({TARGET_DATASET} Dataset) ---")
    config = SHDEConfig()

    tokenizer = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6])
    encoder = HDCEncoder(config)
    memory = AssociativeMemory(config)

    class_data = collections.defaultdict(list)

    print("\n[Data Preparation] Loading and Pooling Records...")

    if TARGET_DATASET == "MITBIH":
        DATA_DIR = r"D:\Projects\Personal\NeuroHDC\Datasets\MIT-BIH"
        loader = MITBIHLoader(DATA_DIR)
        records_to_load = sorted([f.replace('.csv', '') for f in os.listdir(DATA_DIR) if f.endswith('.csv')])
        for rec in records_to_load:
            if os.path.exists(os.path.join(DATA_DIR, f"{rec}annotations.txt")):
                X_rec, y_rec = loader.load_record(rec)
                for x, y in zip(X_rec, y_rec):
                    class_data[y].append(x)

    elif TARGET_DATASET == "PTB":
        DATA_DIR = r"D:\Projects\Personal\NeuroHDC\Datasets\PTB"
        loader = PTBLoader(DATA_DIR)
        X_rec, y_rec = loader.load_dataset()
        for x, y in zip(X_rec, y_rec):
            class_data[y].append(x)

    elif TARGET_DATASET == "STT":
        DATA_DIR = r"D:\Projects\Personal\NeuroHDC\Datasets\STT"
        loader = STTLoader(DATA_DIR)
        X_rec, y_rec = loader.load_dataset()
        for x, y in zip(X_rec, y_rec):
            class_data[y].append(x)

    elif TARGET_DATASET == "PHYSIONET":
        DATA_DIR = r"D:\Projects\Personal\NeuroHDC\Datasets\PhysioNet"
        loader = PhysioNetLoader(DATA_DIR)
        X_rec, y_rec = loader.load_dataset()
        for x, y in zip(X_rec, y_rec):
            class_data[y].append(x)

    else:
        print("Invalid TARGET_DATASET. Exiting.")
        sys.exit(1)

    if not class_data:
        print(f"ERROR: No data loaded. Check if the directory {DATA_DIR} exists and contains the files.")
        sys.exit(1)

    train_data = []
    test_data = []

    for label, samples in class_data.items():
        np.random.seed(42)
        np.random.shuffle(samples)

        split = int(0.8 * len(samples))
        train_subset = samples[:split]
        test_subset = samples[split:]

        # Balance the dataset appropriately
        max_train = 12000 if label == "Normal" else 3000
        if len(train_subset) > max_train:
            train_subset = train_subset[:max_train]

        for x in train_subset: train_data.append((x, label))
        for x in test_subset: test_data.append((x, label))

    np.random.shuffle(train_data)

    print(f"\n[Phase A] Training One-Shot on {len(train_data)} balanced samples...")
    train_hvs = []
    for wave, label in train_data:
        spikes = tokenizer.encode(wave)
        hv = encoder.encode_sequence(spikes)
        memory.add_to_class(hv, label)
        train_hvs.append((hv, label))

    memory.finalize_prototypes()
    print("One-Shot Training Complete. Vectors bundled into Prototypes.")

    print("\n[Phase A.2] Iterative Boundary Refinement (Fixing False Positives)...")

    for label in memory.prototype_sums:
        memory.prototype_sums[label] = (2 * memory.prototype_sums[label]) - memory.prototype_counts[label]

    EPOCHS = 30
    for epoch in range(EPOCHS):
        mistakes = 0
        np.random.shuffle(train_hvs)

        LR = max(1, int(15 * (1.0 - (epoch / EPOCHS))))

        for hv, true_label in train_hvs:
            pred_label, _ = memory.predict(hv)

            if pred_label != true_label:
                mistakes += 1
                bipolar_hv = np.where(hv > 0, 1, -1).astype(np.int32)

                memory.prototype_sums[pred_label] -= bipolar_hv * LR
                memory.prototype_sums[true_label] += bipolar_hv * LR

        for label in memory.prototype_sums:
            memory.prototypes[label] = (memory.prototype_sums[label] > 0).astype(np.int8)

        acc = 100 * (1 - mistakes / len(train_hvs))
        print(f"  Epoch {epoch + 1:02d}/{EPOCHS} | Train Accuracy: {acc:.2f}% | LR: {LR}")

        if mistakes == 0:
            print("  -> Convergence reached!")
            break

    print("\n[Phase B] Beginning Inference Testing...")
    strict_correct = 0
    binary_correct = 0
    confusion_matrix = {"True_N": 0, "False_Anomaly": 0, "True_Anomaly": 0, "False_N": 0}

    total_hardware_ticks = 0
    active_hardware_ticks = 0

    for wave, true_label in test_data:
        spikes = tokenizer.encode(wave)
        query_hv = encoder.encode_sequence(spikes)

        mid_channel = spikes[1]
        total_hardware_ticks += len(mid_channel)
        active_hardware_ticks += np.count_nonzero(mid_channel)

        pred_label, _ = memory.predict(query_hv)

        if pred_label == true_label:
            strict_correct += 1

        is_true_anomaly = (true_label != "Normal")
        is_pred_anomaly = (pred_label != "Normal")

        if is_true_anomaly == is_pred_anomaly:
            binary_correct += 1
            if not is_true_anomaly:
                confusion_matrix["True_N"] += 1
            else:
                confusion_matrix["True_Anomaly"] += 1
        else:
            if not is_true_anomaly:
                confusion_matrix["False_Anomaly"] += 1
            else:
                confusion_matrix["False_N"] += 1

    total = len(test_data)
    bin_acc = (binary_correct / total) * 100 if total > 0 else 0
    strict_acc = (strict_correct / total) * 100 if total > 0 else 0
    sleep_percentage = ((total_hardware_ticks - active_hardware_ticks) / total_hardware_ticks) * 100

    print("\n=== FINAL PIPELINE RESULTS ===")
    print(f"Dataset: {TARGET_DATASET}")
    print(f"Total Test Samples: {total}")
    print(f"Strict Multi-Class Accuracy: {strict_acc:.2f}% (Exact anomaly match)")
    print(f"Binary Anomaly Detection Accuracy: {bin_acc:.2f}% (Normal vs Any Anomaly)")
    print(f"\nHardware Sparsity (Sleep Time): {sleep_percentage:.2f}%")

    print("\nBinary Confusion Matrix:")
    print(f"  True Normal: {confusion_matrix['True_N']} | False Anomaly (FP): {confusion_matrix['False_Anomaly']}")
    print(f"  True Anomaly: {confusion_matrix['True_Anomaly']} | False Normal (FN): {confusion_matrix['False_N']}")

    model_save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'shde_model_{TARGET_DATASET}.pkl'))
    with open(model_save_path, 'wb') as f:
        pickle.dump(memory.prototypes, f)
    print(f"\n[Model Checkpoint] HDC Prototypes saved to: {model_save_path}")


if __name__ == "__main__":
    main()