import sys
import os
import numpy as np
import pickle

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import SHDEConfig
from src.tokenizer import DeltaTokenizer
from src.hdc_encoding import HDCEncoder
from src.associative_mem import AssociativeMemory
from src.data_loader import MITBIHLoader, PTBLoader, STTLoader, PhysioNetLoader
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score

# ==========================================
# TEST PHYSIONET WITH RHYTHM BINDING!
# ==========================================
TARGET_DATASET = "PHYSIONET"  # Options: "MITBIH", "PTB", "STT", "PHYSIONET"

# Rhythm binding is now unlocked for BOTH MITBIH and PHYSIONET.
USE_RHYTHM_BINDING = False

BASE_SEED = 42
MAX_NORMAL = 12000
MAX_ANOMALY = 3000
EPOCHS = 30

RR_SHORT_RATIO = 0.85
RR_LONG_RATIO = 1.15
RR_BUCKETS = ["SHORT", "NORMAL", "LONG"]


# ---------------------------------------------------------------------------
# Rhythm-binding utilities
# ---------------------------------------------------------------------------

def bipolar(v):
    return np.where(np.asarray(v) > 0, 1, -1).astype(np.int32)


def bind_rhythm(hv, rhythm_hv):
    bound_bipolar = bipolar(hv) * rhythm_hv
    return np.where(bound_bipolar > 0, 1, 0).astype(np.int8)


def make_rhythm_codebook(dim, seed=BASE_SEED):
    rng = np.random.RandomState(seed)
    return {bucket: bipolar(rng.choice([-1, 1], size=dim)) for bucket in RR_BUCKETS}


def bucket_rr(rr_interval, local_median_rr):
    if local_median_rr is None or local_median_rr <= 0:
        return "NORMAL"
    ratio = rr_interval / local_median_rr
    if ratio < RR_SHORT_RATIO: return "SHORT"
    if ratio > RR_LONG_RATIO: return "LONG"
    return "NORMAL"


# ---------------------------------------------------------------------------
# Data loading -- every dataset now returns (X, y, rr, groups)
# ---------------------------------------------------------------------------

def load_dataset(target, rhythm_enabled):
    PROJ_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    X_all, y_all, rr_all, groups_all = [], [], [], []

    if target == "MITBIH":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "MIT-BIH")
        loader = MITBIHLoader(DATA_DIR)
        records = sorted([f.replace('.csv', '') for f in os.listdir(DATA_DIR) if f.endswith('.csv')])

        for rec in records:
            if not os.path.exists(os.path.join(DATA_DIR, f"{rec}annotations.txt")):
                continue

            if rhythm_enabled:
                X_rec, y_rec, peak_idx_rec = loader.load_record(rec, return_peaks=True)
            else:
                X_rec, y_rec = loader.load_record(rec)
                peak_idx_rec = None

            if peak_idx_rec is not None and len(peak_idx_rec) > 0:
                peak_idx_rec = np.asarray(peak_idx_rec)
                rr_intervals = np.diff(peak_idx_rec, prepend=peak_idx_rec[0])
                local_median = np.median(rr_intervals[rr_intervals > 0]) if np.any(rr_intervals > 0) else None

                rr_buckets_rec = []
                for i, rr in enumerate(rr_intervals):
                    if i == 0:
                        rr_buckets_rec.append("NORMAL")
                    else:
                        rr_buckets_rec.append(bucket_rr(rr, local_median))
            else:
                rr_buckets_rec = [None] * len(y_rec)

            X_all.extend(X_rec)
            y_all.extend(y_rec)
            rr_all.extend(rr_buckets_rec)
            groups_all.extend([rec] * len(y_rec))

        return X_all, y_all, rr_all, groups_all, DATA_DIR

    elif target == "PHYSIONET":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "PhysioNet")
        loader = PhysioNetLoader(DATA_DIR)

        if rhythm_enabled:
            X_rec, y_rec, g_rec, rr_rec = loader.load_dataset(return_rhythm=True)
        else:
            X_rec, y_rec, g_rec = loader.load_dataset(return_rhythm=False)
            rr_rec = [None] * len(y_rec)

        X_all.extend(X_rec)
        y_all.extend(y_rec)
        rr_all.extend(rr_rec)
        groups_all.extend(g_rec)

        return X_all, y_all, rr_all, groups_all, DATA_DIR

    elif target == "PTB":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "PTB")
        loader = PTBLoader(DATA_DIR)
    elif target == "STT":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "STT")
        loader = STTLoader(DATA_DIR)
    else:
        print("Invalid TARGET_DATASET. Exiting.")
        sys.exit(1)

    X_rec, y_rec, g_rec = loader.load_dataset()
    X_all.extend(X_rec)
    y_all.extend(y_rec)
    rr_all.extend([None] * len(y_rec))
    groups_all.extend(g_rec)
    return X_all, y_all, rr_all, groups_all, DATA_DIR


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"--- Initializing Spiking-HDC Pipeline ({TARGET_DATASET} Dataset) ---")
    config = SHDEConfig()

    tokenizer = DeltaTokenizer(thresholds=[0.05, 0.25, 0.6])
    encoder = HDCEncoder(config)

    # Allow rhythm binding on PhysioNet!
    rhythm_enabled = USE_RHYTHM_BINDING and (TARGET_DATASET in ["MITBIH", "PHYSIONET"])
    if USE_RHYTHM_BINDING and not rhythm_enabled:
        print(f"[NOTE] Rhythm binding requested but only implemented for MITBIH/PHYSIONET; "
              f"running {TARGET_DATASET} morphology-only.")

    print("\n[Data Preparation] Loading and Pooling Records...")
    X_all, y_all, rr_all, groups_all, DATA_DIR = load_dataset(TARGET_DATASET, rhythm_enabled)

    if not X_all:
        print(f"ERROR: No data loaded. Check if the directory {DATA_DIR} exists.")
        sys.exit(1)

    X_all = np.array(X_all, dtype=object)
    y_all = np.array(y_all)
    rr_all = np.array(rr_all, dtype=object)
    groups_all = np.array(groups_all)

    n_groups = len(np.unique(groups_all))
    print(f"    Loaded {len(X_all)} total beats from {n_groups} distinct records/patients.")
    print(f"    Rhythm binding active: {rhythm_enabled}")

    rhythm_codebook = make_rhythm_codebook(dim=config.D) if rhythm_enabled else None

    kf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=BASE_SEED)

    fold_strict_accs, fold_bin_accs, fold_f1s = [], [], []

    print(f"\n=== Starting 5-Fold Group-Aware Cross Validation for Spiking-HDC ===")

    model_save_path = None

    for fold, (train_idx, test_idx) in enumerate(kf.split(X_all, y_all, groups=groups_all)):
        print(f"\n--- FOLD {fold + 1}/5 ---")

        train_groups = set(groups_all[train_idx])
        test_groups = set(groups_all[test_idx])
        overlap = train_groups & test_groups
        if overlap:
            print(f"[ERROR] {len(overlap)} record(s) appear in BOTH train and test "
                  f"for this fold -- group split failed. Aborting.")
            sys.exit(1)

        rng = np.random.RandomState(BASE_SEED + fold)
        memory = AssociativeMemory(config)

        X_train_fold, y_train_fold, rr_train_fold = X_all[train_idx], y_all[train_idx], rr_all[train_idx]
        X_test_fold, y_test_fold, rr_test_fold = X_all[test_idx], y_all[test_idx], rr_all[test_idx]

        train_data = []
        for label in np.unique(y_train_fold):
            label_indices = np.where(y_train_fold == label)[0]
            rng.shuffle(label_indices)

            cap = MAX_NORMAL if label == "Normal" else MAX_ANOMALY
            for idx in label_indices[:cap]:
                train_data.append((X_train_fold[idx], label, rr_train_fold[idx]))

        rng.shuffle(train_data)

        print(f"[Phase A] Training One-Shot on {len(train_data)} balanced samples "
              f"({len(train_groups)} records)...")
        train_hvs = []
        for wave, label, rr_bucket in train_data:
            spikes = tokenizer.encode(wave)
            hv = encoder.encode_sequence(spikes)

            if rhythm_enabled:
                bucket = rr_bucket if rr_bucket is not None else "NORMAL"
                hv = bind_rhythm(hv, rhythm_codebook[bucket])

            memory.add_to_class(hv, label)
            train_hvs.append((hv, label))

        memory.finalize_prototypes()

        print("[Phase A.2] Iterative Boundary Refinement (Fixing False Positives)...")
        for label in memory.prototype_sums:
            memory.prototype_sums[label] = (2 * memory.prototype_sums[label]) - memory.prototype_counts[label]

        for epoch in range(EPOCHS):
            mistakes = 0
            rng.shuffle(train_hvs)
            LR = max(1, int(15 * (1.0 - (epoch / EPOCHS))))

            for hv, true_label in train_hvs:
                pred_label, _ = memory.predict(hv)
                if pred_label != true_label:
                    mistakes += 1
                    bipolar_hv = bipolar(hv)
                    memory.prototype_sums[pred_label] -= bipolar_hv * LR
                    memory.prototype_sums[true_label] += bipolar_hv * LR

            for label in memory.prototype_sums:
                memory.prototypes[label] = (memory.prototype_sums[label] > 0).astype(np.int8)

            if mistakes == 0:
                break

        print(f"[Phase B] Inference Testing on {len(test_groups)} held-out records...")
        strict_correct, binary_correct = 0, 0
        y_true_strict, y_pred_strict = [], []

        for wave, true_label, rr_bucket in zip(X_test_fold, y_test_fold, rr_test_fold):
            spikes = tokenizer.encode(wave)
            query_hv = encoder.encode_sequence(spikes)

            if rhythm_enabled:
                bucket = rr_bucket if rr_bucket is not None else "NORMAL"
                query_hv = bind_rhythm(query_hv, rhythm_codebook[bucket])

            pred_label, _ = memory.predict(query_hv)

            if pred_label == true_label: strict_correct += 1
            y_true_strict.append(true_label)
            y_pred_strict.append(pred_label)

            # Taxonomy alignment: AAMI EC57 groups LBBB/RBBB into Normal (N).
            if TARGET_DATASET == "MITBIH":
                aami_normal = ["Normal", "LBBB", "RBBB"]
                is_true_anomaly = (true_label not in aami_normal)
                is_pred_anomaly = (pred_label not in aami_normal)
            else:
                is_true_anomaly = (true_label != "Normal")
                is_pred_anomaly = (pred_label != "Normal")

            if is_true_anomaly == is_pred_anomaly: binary_correct += 1

        total = len(y_test_fold)
        bin_acc = (binary_correct / total) * 100 if total > 0 else 0
        strict_acc = (strict_correct / total) * 100 if total > 0 else 0

        # Taxonomy alignment: PhysioNet CinC ignores 'Noisy' in Macro F1 calculation.
        eval_labels = list(set(y_true_strict) | set(y_pred_strict))
        if TARGET_DATASET == "PHYSIONET" and "Noisy" in eval_labels:
            eval_labels.remove("Noisy")

        fold_f1 = f1_score(y_true_strict, y_pred_strict, labels=eval_labels, average='macro') * 100

        fold_strict_accs.append(strict_acc)
        fold_bin_accs.append(bin_acc)
        fold_f1s.append(fold_f1)

        print(
            f"Fold {fold + 1} Results -> Strict Acc: {strict_acc:.2f}% | Binary Acc: {bin_acc:.2f}% | Macro F1: {fold_f1:.2f}%")

        if fold == 4:
            suffix = "_rhythm" if rhythm_enabled else ""
            model_save_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', f'nhdc__{TARGET_DATASET}{suffix}.pkl'))
            with open(model_save_path, 'wb') as f:
                pickle.dump(memory.prototypes, f)

    print("\n=== FINAL PIPELINE RESULTS ===")
    print(f"Dataset: {TARGET_DATASET}")
    print(f"Rhythm Binding: {'ENABLED' if rhythm_enabled else 'disabled'}")
    print(f"Split: StratifiedGroupKFold (record/patient-level, no leakage)")
    print(f"Total Cross-Validation Samples: {len(X_all)}")
    print(f"Strict Multi-Class Accuracy: {np.mean(fold_strict_accs):.2f}% \u00b1 {np.std(fold_strict_accs):.2f}%")
    print(f"Binary Anomaly Detection Accuracy: {np.mean(fold_bin_accs):.2f}% \u00b1 {np.std(fold_bin_accs):.2f}%")
    print(f"Macro F1-Score: {np.mean(fold_f1s):.2f}% \u00b1 {np.std(fold_f1s):.2f}%")
    if model_save_path:
        print(f"\n[Model Checkpoint] Fold 5 HDC Prototypes saved to: {model_save_path}")


if __name__ == "__main__":
    main()