import os
import gc
import numpy as np
import pandas as pd
import wfdb
from scipy.io import loadmat
from src.config import SHDEConfig


class MITBIHLoader:
    def __init__(self, data_dir):
        """
        Points to the directory containing your pairs of .csv and .txt files.
        """
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

    def parse_annotations(self, txt_path):
        """
        Parses the MIT-BIH annotations.txt file to extract beat locations and labels.
        """
        annotations = []
        with open(txt_path, 'r') as f:
            lines = f.readlines()
            for line in lines[1:]:  # Skip header if it exists
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        sample_idx = int(parts[1])
                        beat_type = parts[2]
                        annotations.append((sample_idx, beat_type))
                    except ValueError:
                        continue
        return annotations

    def load_record(self, record_id):
        """
        Loads a single record and slices it into labeled windows.
        """
        csv_path = os.path.join(self.data_dir, f"{record_id}.csv")
        txt_path = os.path.join(self.data_dir, f"{record_id}annotations.txt")

        if not os.path.exists(csv_path) or not os.path.exists(txt_path):
            print(f"Warning: Files for record {record_id} not found.")
            return [], []

        # 1. Load the continuous analog signal
        df = pd.read_csv(csv_path)
        signal_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        analog_signal = df[signal_col].values

        # 2. GLOBAL Z-Score Normalization (Hardware-equivalent slow AGC)
        # We normalize the ENTIRE record once using standard deviation.
        # This ignores sudden massive outlier peaks (like sensor bumps) that
        # would otherwise squash the rest of the signal in Peak Normalization.
        mean_val = np.mean(analog_signal)
        std_val = np.std(analog_signal)

        if std_val > 0:
            analog_signal = (analog_signal - mean_val) / std_val

        # 3. Load the beat annotations
        annotations = self.parse_annotations(txt_path)

        X_windows = []
        y_labels = []

        # Top 5 Medical Classes instead of a binary catch-all
        valid_beats = {
            'N': 'Normal',
            'V': 'PVC',  # Premature ventricular contraction
            'L': 'LBBB',  # Left bundle branch block
            'R': 'RBBB',  # Right bundle branch block
            'A': 'PAC'  # Atrial premature beat
        }

        # 4. Slice the signal into windows
        for sample_idx, beat_type in annotations:
            if sample_idx < self.half_window or sample_idx > len(analog_signal) - self.half_window:
                continue

            # Strict filtering: We only keep clean, defined beat types
            if beat_type in valid_beats:
                label = valid_beats[beat_type]
            else:
                continue

            # Slice the window
            start_idx = sample_idx - self.half_window
            end_idx = sample_idx + self.half_window
            window = analog_signal[start_idx:end_idx]

            X_windows.append(window)
            y_labels.append(label)

        return X_windows, y_labels

class PTBLoader:
    """
    Loader for the Raw PTB Diagnostic ECG Database (Folder full of sXXXXX.csv files).
    Extracts continuous signals, segments heartbeats via peak detection, and assigns labels.
    """

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

        # Comprehensive list of known Healthy Control prefixes in the PTB dataset.
        self.healthy_prefixes = [
            's0273', 's0274', 's0281', 's0287', 's0291', 's0292', 's0293',
            's0294', 's0295', 's0296', 's0297', 's0298', 's0299', 's0300',
            's0301', 's0302', 's0303', 's0304', 's0305', 's0306', 's0315',
            's0324', 's0325'
        ]

    def _get_label(self, filename):
        if any(hp in filename for hp in self.healthy_prefixes):
            return "Normal"
        else:
            return "Myocardial Infarction"

    def load_dataset(self, max_beats_per_file=20):
        X_windows = []
        y_labels = []

        csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]

        if not csv_files:
            print(f"Warning: No CSV files found in {self.data_dir}.")
            return [], []

        print(
            f"  -> Found {len(csv_files)} raw PTB recordings. Extracting up to {max_beats_per_file} beats per file...")

        for idx, filename in enumerate(csv_files):
            filepath = os.path.join(self.data_dir, filename)
            label = self._get_label(filename)

            try:
                df = pd.read_csv(filepath, usecols=[1], skiprows=1, engine='c')
                continuous_signal = df.iloc[:, 0].values

                threshold = np.max(continuous_signal) * 0.6
                peaks = np.where(continuous_signal > threshold)[0]

                valid_peaks = []
                last_peak = -1000
                for p in peaks:
                    if p - last_peak > 250:
                        valid_peaks.append(p)
                        last_peak = p

                beats_extracted = 0
                for p in valid_peaks:
                    if beats_extracted >= max_beats_per_file:
                        break

                    if p >= self.half_window and p < len(continuous_signal) - self.half_window:
                        start_idx = p - self.half_window
                        end_idx = p + self.half_window
                        window = continuous_signal[start_idx:end_idx]

                        window = window - np.mean(window)
                        peak_val = np.max(np.abs(window))
                        if peak_val > 0:
                            window = window / peak_val

                        X_windows.append(window)
                        y_labels.append(label)
                        beats_extracted += 1

                del df
                del continuous_signal
                if idx % 50 == 0:
                    gc.collect()

            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue

        print(f"  -> Successfully extracted {len(X_windows)} individual heartbeats from PTB.")
        return X_windows, y_labels

class STTLoader:
    """
    Loader for the European ST-T Database.
    Reads WFDB .dat/.hea files and uses .atr files to extract perfectly
    ground-truthed clinical anomalies.
    """

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

    # Increased max beats to 150 to provide enough data for HDC to generalize
    def load_dataset(self, max_beats_per_file=150):
        X_windows = []
        y_labels = []

        dat_files = [f for f in os.listdir(self.data_dir) if f.endswith('.dat')]

        if not dat_files:
            print(f"Warning: No .dat files found in {self.data_dir}.")
            return [], []

        print(f"  -> Found {len(dat_files)} ST-T recordings. Extracting up to {max_beats_per_file} beats per file...")

        for idx, filename in enumerate(dat_files):
            record_name = filename.replace('.dat', '')
            record_path = os.path.join(self.data_dir, record_name)

            try:
                # Read BOTH the raw signal and the clinical annotations
                record = wfdb.rdrecord(record_path)
                annotation = wfdb.rdann(record_path, 'atr')

                continuous_signal = record.p_signal[:, 0]
                continuous_signal = np.nan_to_num(continuous_signal)

                normal_indices = []
                anomaly_indices = []

                # Sort all beats in the entire file into buckets
                for sample_idx, symbol in zip(annotation.sample, annotation.symbol):
                    if symbol in ['N', '·']:
                        normal_indices.append(sample_idx)
                    elif symbol in ['V', 'S', 'F', 'A', 'a', 'J', 'j', 'E', 'e']:
                        anomaly_indices.append(sample_idx)

                # Shuffle to ensure we grab beats from the middle/end of the recording
                np.random.shuffle(normal_indices)
                np.random.shuffle(anomaly_indices)

                # Take a balanced slice (half normals, half anomalies)
                half_limit = max_beats_per_file // 2
                selected_samples = [(s, "Normal") for s in normal_indices[:half_limit]] + \
                                   [(s, "ST_Anomaly") for s in anomaly_indices[:half_limit]]

                for sample_idx, label in selected_samples:
                    if sample_idx >= self.half_window and sample_idx < len(continuous_signal) - self.half_window:
                        start_idx = sample_idx - self.half_window
                        end_idx = sample_idx + self.half_window
                        window = continuous_signal[start_idx:end_idx].copy()

                        # --- NEW SMART AGC FOR ST-T ---
                        # Instead of zero-meaning the whole window, anchor the zero-line
                        # to the first 40 samples (the quiet PR-segment).
                        # This preserves the DC-shift of the ST-elevation!
                        pr_baseline = np.mean(window[:40])
                        window = window - pr_baseline

                        peak_val = np.max(np.abs(window))
                        if peak_val > 0:
                            window = window / peak_val

                        X_windows.append(window)
                        y_labels.append(label)

                del continuous_signal
                del record
                del annotation
                if idx % 20 == 0:
                    gc.collect()

            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue

        return X_windows, y_labels

class PhysioNetLoader:
    """
    Loader for the PhysioNet/CinC Challenge (e.g., 2017 AFib Dataset).
    Reads .mat files directly and maps them using REFERENCE.csv.
    """

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

        self.reference_map = {}
        ref_path = os.path.join(self.data_dir, "REFERENCE.csv")
        if os.path.exists(ref_path):
            with open(ref_path, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) == 2:
                        self.reference_map[parts[0]] = parts[1]

    def load_dataset(self, max_beats_per_file=15):
        X_windows = []
        y_labels = []

        mat_files = [f for f in os.listdir(self.data_dir) if f.endswith('.mat')]
        print(f"  -> Found {len(mat_files)} PhysioNet .mat recordings. Mapping to REFERENCE.csv...")

        # Explicitly drop the '~' (Noisy) class to prevent poisoning the HDC prototypes
        label_translation = {
            'N': 'Normal',
            'A': 'AFib',
            'O': 'Other_Anomaly'
        }

        for filename in mat_files:
            record_id = filename.replace('.mat', '')
            raw_label = self.reference_map.get(record_id, 'N')

            if raw_label not in label_translation:
                continue  # Skip noisy unreadable files

            label = label_translation[raw_label]
            filepath = os.path.join(self.data_dir, filename)

            try:
                mat_data = loadmat(filepath)
                continuous_signal = mat_data['val'][0].astype(float)
                continuous_signal = np.nan_to_num(continuous_signal)

                # --- THE FIX: RHYTHM COMPRESSION ---
                # PhysioNet is 300Hz. 256 samples = 0.85s (Only 1 beat).
                # By downsampling by 4, 256 samples = 3.4 seconds (3-4 beats).
                # This allows the tokenizer to see the irregular R-R intervals of AFib!
                downsample_factor = 4
                downsampled_signal = continuous_signal[::downsample_factor]

                threshold = np.max(downsampled_signal) * 0.6
                peaks = np.where(downsampled_signal > threshold)[0]

                valid_peaks = []
                last_peak = -1000
                for p in peaks:
                    # Adjust refractory period for the downsampled signal (~200ms)
                    if p - last_peak > (200 // downsample_factor):
                        valid_peaks.append(p)
                        last_peak = p

                beats_extracted = 0
                for p in valid_peaks:
                    if beats_extracted >= max_beats_per_file: break

                    if p >= self.half_window and p < len(downsampled_signal) - self.half_window:
                        window = downsampled_signal[p - self.half_window: p + self.half_window].copy()

                        # Zero-mean and Soft-clip to handle severe baseline wander in ambulatory data
                        window = window - np.mean(window)
                        peak_val = np.percentile(np.abs(window), 98)
                        if peak_val > 0:
                            window = np.clip(window, -peak_val, peak_val) / peak_val

                        X_windows.append(window)
                        y_labels.append(label)
                        beats_extracted += 1

                del mat_data
                del continuous_signal
                del downsampled_signal

            except Exception as e:
                pass

        return X_windows, y_labels
