import os
import gc
import numpy as np
import pandas as pd
import wfdb
from scipy.io import loadmat
from src.config import SHDEConfig

class MITBIHLoader:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

    def parse_annotations(self, txt_path):
        annotations = []
        with open(txt_path, 'r') as f:
            lines = f.readlines()
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        sample_idx = int(parts[1])
                        beat_type = parts[2]
                        annotations.append((sample_idx, beat_type))
                    except ValueError:
                        continue
        return annotations

    def load_record(self, record_id, return_peaks=False):
        csv_path = os.path.join(self.data_dir, f"{record_id}.csv")
        txt_path = os.path.join(self.data_dir, f"{record_id}annotations.txt")

        if not os.path.exists(csv_path) or not os.path.exists(txt_path):
            return ([], [], []) if return_peaks else ([], [])

        df = pd.read_csv(csv_path)
        signal_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        analog_signal = df[signal_col].values
        annotations = self.parse_annotations(txt_path)

        X_windows, y_labels, peak_indices = [], [], []

        valid_beats = {
            'N': 'Normal',
            'V': 'PVC',
            'L': 'LBBB',
            'R': 'RBBB',
            'A': 'PAC',
        }

        for sample_idx, beat_type in annotations:
            if sample_idx < self.half_window or sample_idx > len(analog_signal) - self.half_window:
                continue
            if beat_type not in valid_beats:
                continue
            label = valid_beats[beat_type]

            start_idx = sample_idx - self.half_window
            end_idx = sample_idx + self.half_window
            window = analog_signal[start_idx:end_idx]

            window = window - np.mean(window)
            peak_val = np.percentile(np.abs(window), 98)
            if peak_val > 0:
                window = np.clip(window, -peak_val, peak_val)
                window = window / peak_val

            X_windows.append(window)
            y_labels.append(label)
            peak_indices.append(sample_idx)

        if return_peaks:
            return X_windows, y_labels, peak_indices
        return X_windows, y_labels


class PTBLoader:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

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
        X_windows, y_labels, groups = [], [], []
        csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]

        if not csv_files:
            return [], [], []

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
                    if beats_extracted >= max_beats_per_file: break
                    if p >= self.half_window and p < len(continuous_signal) - self.half_window:
                        start_idx = p - self.half_window
                        end_idx = p + self.half_window
                        window = continuous_signal[start_idx:end_idx]

                        window = window - np.mean(window)
                        peak_val = np.max(np.abs(window))
                        if peak_val > 0: window = window / peak_val

                        X_windows.append(window)
                        y_labels.append(label)
                        groups.append(filename)
                        beats_extracted += 1

                del df, continuous_signal
                if idx % 50 == 0: gc.collect()

            except Exception as e:
                continue

        return X_windows, y_labels, groups


class STTLoader:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.window_size = SHDEConfig.WINDOW_SIZE
        self.half_window = self.window_size // 2

    def load_dataset(self, max_beats_per_file=150):
        X_windows, y_labels, groups = [], [], []
        dat_files = [f for f in os.listdir(self.data_dir) if f.endswith('.dat')]

        if not dat_files:
            return [], [], []

        for idx, filename in enumerate(dat_files):
            record_name = filename.replace('.dat', '')
            record_path = os.path.join(self.data_dir, record_name)

            try:
                record = wfdb.rdrecord(record_path)
                annotation = wfdb.rdann(record_path, 'atr')

                continuous_signal = record.p_signal[:, 0]
                continuous_signal = np.nan_to_num(continuous_signal)

                normal_indices, anomaly_indices = [], []

                for sample_idx, symbol in zip(annotation.sample, annotation.symbol):
                    if symbol in ['N', '\u00b7']: normal_indices.append(sample_idx)
                    elif symbol in ['V', 'S', 'F', 'A', 'a', 'J', 'j', 'E', 'e']: anomaly_indices.append(sample_idx)

                np.random.shuffle(normal_indices)
                np.random.shuffle(anomaly_indices)

                half_limit = max_beats_per_file // 2
                selected_samples = [(s, "Normal") for s in normal_indices[:half_limit]] + \
                                   [(s, "ST_Anomaly") for s in anomaly_indices[:half_limit]]

                for sample_idx, label in selected_samples:
                    if sample_idx >= self.half_window and sample_idx < len(continuous_signal) - self.half_window:
                        start_idx = sample_idx - self.half_window
                        end_idx = sample_idx + self.half_window
                        window = continuous_signal[start_idx:end_idx].copy()

                        pr_baseline = np.mean(window[:40])
                        window = window - pr_baseline

                        peak_val = np.max(np.abs(window))
                        if peak_val > 0: window = window / peak_val

                        X_windows.append(window)
                        y_labels.append(label)
                        groups.append(record_name)

                del continuous_signal, record, annotation
                if idx % 20 == 0: gc.collect()

            except Exception as e:
                continue

        return X_windows, y_labels, groups


class PhysioNetLoader:
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

    def load_dataset(self, max_beats_per_file=15, return_rhythm=False):
        X_windows, y_labels, groups, rr_buckets = [], [], [], []
        mat_files = [f for f in os.listdir(self.data_dir) if f.endswith('.mat')]

        label_translation = {'N': 'Normal', 'A': 'AFib', 'O': 'Other_Anomaly', '~': 'Noisy'}

        for filename in mat_files:
            record_id = filename.replace('.mat', '')
            raw_label = self.reference_map.get(record_id, 'N')
            label = label_translation.get(raw_label, 'Normal')
            filepath = os.path.join(self.data_dir, filename)

            try:
                mat_data = loadmat(filepath)
                continuous_signal = np.nan_to_num(mat_data['val'][0].astype(float))

                downsample_factor = 4
                downsampled_signal = continuous_signal[::downsample_factor]

                threshold = np.max(downsampled_signal) * 0.6
                peaks = np.where(downsampled_signal > threshold)[0]

                valid_peaks, last_peak = [], -1000
                for p in peaks:
                    if p - last_peak > (200 // downsample_factor):
                        valid_peaks.append(p)
                        last_peak = p

                # Extract Rhythm features just like MIT-BIH
                if return_rhythm and len(valid_peaks) > 0:
                    rr_intervals = np.diff(valid_peaks, prepend=valid_peaks[0])
                    local_median = np.median(rr_intervals[rr_intervals > 0]) if np.any(rr_intervals > 0) else None
                else:
                    rr_intervals = [0] * len(valid_peaks)
                    local_median = None

                beats_extracted = 0
                for i, p in enumerate(valid_peaks):
                    if beats_extracted >= max_beats_per_file: break
                    if p >= self.half_window and p < len(downsampled_signal) - self.half_window:
                        window = downsampled_signal[p - self.half_window: p + self.half_window]

                        window = window - np.mean(window)
                        peak_val = np.percentile(np.abs(window), 98)
                        if peak_val > 0: window = np.clip(window, -peak_val, peak_val) / peak_val

                        if return_rhythm:
                            if i == 0 or local_median is None or local_median <= 0:
                                bucket = "NORMAL"
                            else:
                                ratio = rr_intervals[i] / local_median
                                if ratio < 0.85: bucket = "SHORT"
                                elif ratio > 1.15: bucket = "LONG"
                                else: bucket = "NORMAL"
                            rr_buckets.append(bucket)

                        X_windows.append(window)
                        y_labels.append(label)
                        groups.append(record_id)
                        beats_extracted += 1

                del mat_data, continuous_signal, downsampled_signal
            except Exception:
                pass

        if return_rhythm:
            return X_windows, y_labels, groups, rr_buckets
        return X_windows, y_labels, groups