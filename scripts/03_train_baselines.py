import sys
import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.data_loader import MITBIHLoader, PTBLoader, STTLoader, PhysioNetLoader

# ==========================================
# CONFIGURATION TOGGLE
# ==========================================
TARGET_DATASET = "MITBIH"  # Options: "MITBIH", "PTB", "STT", "PHYSIONET"
EPOCHS = 15
BATCH_SIZE = 64
KFOLDS = 5
BASE_SEED = 42
MAX_NORMAL = 12000
MAX_ANOMALY = 3000


class ECG_1D_CNN(nn.Module):
    """
    Lightweight 1D-CNN designed to establish a Deep Learning baseline.
    Input size: (Batch, 1 Channel, 256 Samples)
    """

    def __init__(self, num_classes):
        super(ECG_1D_CNN, self).__init__()

        self.conv1 = nn.Conv1d(in_channels=1, out_channels=16, kernel_size=7, padding=3)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2)  # 256 -> 128

        self.conv2 = nn.Conv1d(in_channels=16, out_channels=32, kernel_size=5, padding=2)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2)  # 128 -> 64

        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(32 * 64, 128)
        self.relu3 = nn.ReLU()
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.pool1(self.relu1(self.conv1(x)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = self.flatten(x)
        x = self.relu3(self.fc1(x))
        x = self.fc2(x)
        return x


def load_dataset_with_groups(target):
    """Mirrors the group-extraction logic in 01_train_python.py exactly, so
    the CNN baseline is split on the identical patient/record boundaries as
    NeuroHDC. Returns X_all, y_all, groups_all, DATA_DIR."""
    PROJ_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    X_all, y_all, groups_all = [], [], []

    if target == "MITBIH":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "MIT-BIH")
        loader = MITBIHLoader(DATA_DIR)
        records = sorted([f.replace('.csv', '') for f in os.listdir(DATA_DIR) if f.endswith('.csv')])
        for rec in records:
            if not os.path.exists(os.path.join(DATA_DIR, f"{rec}annotations.txt")):
                continue
            X_rec, y_rec = loader.load_record(rec)
            X_all.extend(X_rec)
            y_all.extend(y_rec)
            groups_all.extend([rec] * len(y_rec))  # group = record id
        return X_all, y_all, groups_all, DATA_DIR

    if target == "PTB":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "PTB")
        loader = PTBLoader(DATA_DIR)
    elif target == "STT":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "STT")
        loader = STTLoader(DATA_DIR)
    elif target == "PHYSIONET":
        DATA_DIR = os.path.join(PROJ_DIR, "Datasets", "PhysioNet")
        loader = PhysioNetLoader(DATA_DIR)
    else:
        print("Invalid TARGET_DATASET. Exiting.")
        sys.exit(1)

    X_rec, y_rec, g_rec = loader.load_dataset()  # these loaders now return groups too
    X_all.extend(X_rec)
    y_all.extend(y_rec)
    groups_all.extend(g_rec)
    return X_all, y_all, groups_all, DATA_DIR


def main():
    print(f"--- Initializing 1D-CNN Baseline ({TARGET_DATASET} Dataset) ---")
    print("--- Split: StratifiedGroupKFold (patient/record-level, matches NeuroHDC protocol) ---")

    X_all, y_all, groups_all, DATA_DIR = load_dataset_with_groups(TARGET_DATASET)

    if not X_all:
        print(f"ERROR: No data loaded. Check if the directory {DATA_DIR} exists.")
        sys.exit(1)

    X_all = np.array(X_all)
    y_all = np.array(y_all)
    groups_all = np.array(groups_all)

    n_groups = len(np.unique(groups_all))
    print(f"Loaded {len(X_all)} beats from {n_groups} distinct records/patients.")
    if n_groups < KFOLDS:
        print(f"[WARNING] Only {n_groups} distinct records/patients found -- "
              f"{KFOLDS}-fold group-aware CV needs at least {KFOLDS}.")

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y_all)
    num_classes = len(label_encoder.classes_)
    normal_class_idx = label_encoder.transform(["Normal"])[0]

    # StratifiedGroupKFold: identical splitting guarantee as 01_train_python.py --
    # no beat from the same patient/record appears in both train and test.
    kf = StratifiedGroupKFold(n_splits=KFOLDS, shuffle=True, random_state=BASE_SEED)

    fold_strict_accs, fold_bin_accs, fold_f1s = [], [], []

    print(f"\n=== Starting {KFOLDS}-Fold Group-Aware Cross Validation for CNN ===")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    for fold, (train_idx, test_idx) in enumerate(kf.split(X_all, y_encoded, groups=groups_all)):
        print(f"\n--- FOLD {fold + 1}/{KFOLDS} ---")

        train_groups = set(groups_all[train_idx])
        test_groups = set(groups_all[test_idx])
        overlap = train_groups & test_groups
        if overlap:
            print(f"[ERROR] {len(overlap)} record(s) appear in BOTH train and test -- "
                  f"group split failed. Aborting.")
            sys.exit(1)

        rng = np.random.RandomState(BASE_SEED + fold)
        torch.manual_seed(BASE_SEED + fold)

        X_train_fold, y_train_fold = X_all[train_idx], y_encoded[train_idx]
        X_test_fold, y_test_fold = X_all[test_idx], y_encoded[test_idx]

        X_train_balanced, y_train_balanced = [], []
        for cls_idx in range(num_classes):
            cls_indices = np.where(y_train_fold == cls_idx)[0]
            rng.shuffle(cls_indices)

            is_normal = (cls_idx == normal_class_idx)
            max_train = MAX_NORMAL if is_normal else MAX_ANOMALY
            selected = cls_indices[:max_train]

            for idx in selected:
                X_train_balanced.append(X_train_fold[idx])
                y_train_balanced.append(y_train_fold[idx])

        print(f"[Train] {len(X_train_balanced)} balanced samples ({len(train_groups)} records)")
        print(f"[Test]  {len(X_test_fold)} samples ({len(test_groups)} held-out records)")

        X_t_train = torch.tensor(np.array(X_train_balanced), dtype=torch.float32).unsqueeze(1)
        y_t_train = torch.tensor(y_train_balanced, dtype=torch.long)

        X_t_test = torch.tensor(X_test_fold, dtype=torch.float32).unsqueeze(1)
        y_t_test = torch.tensor(y_test_fold, dtype=torch.long)

        dataset_train = TensorDataset(X_t_train, y_t_train)
        loader_train = DataLoader(dataset_train, batch_size=BATCH_SIZE, shuffle=True)

        model = ECG_1D_CNN(num_classes).to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)

        model.train()
        for epoch in range(EPOCHS):
            for batch_X, batch_y in loader_train:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        model.eval()
        with torch.no_grad():
            outputs = model(X_t_test.to(device))
            _, preds = torch.max(outputs, 1)
            preds = preds.cpu().numpy()

        strict_acc = (preds == y_test_fold).mean() * 100

        true_anomalies = (y_test_fold != normal_class_idx)
        pred_anomalies = (preds != normal_class_idx)
        bin_acc = (true_anomalies == pred_anomalies).mean() * 100

        macro_f1 = f1_score(y_test_fold, preds, average='macro') * 100

        fold_strict_accs.append(strict_acc)
        fold_bin_accs.append(bin_acc)
        fold_f1s.append(macro_f1)

        print(f"Fold {fold + 1} Results -> Strict Acc: {strict_acc:.2f}% | "
              f"Binary Acc: {bin_acc:.2f}% | Macro F1: {macro_f1:.2f}%")

    print("\n=== FINAL CNN BASELINE RESULTS ===")
    print(f"Dataset: {TARGET_DATASET}")
    print(f"Split: StratifiedGroupKFold (patient/record-level, matches NeuroHDC protocol)")
    print(f"Strict Multi-Class Accuracy: {np.mean(fold_strict_accs):.2f}% \u00b1 {np.std(fold_strict_accs):.2f}%")
    print(f"Binary Anomaly Detection Accuracy: {np.mean(fold_bin_accs):.2f}% \u00b1 {np.std(fold_bin_accs):.2f}%")
    print(f"Macro F1-Score: {np.mean(fold_f1s):.2f}% \u00b1 {np.std(fold_f1s):.2f}%")


if __name__ == "__main__":
    main()