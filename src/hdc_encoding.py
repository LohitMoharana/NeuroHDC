# # import numpy as np
# #
# #
# # # In a real run, this imports from src/config.py
# # # For standalone testing in this file, we mock the config here.
# # class MockConfig:
# #     D = 8192
# #     SEED = 42
# #
# #
# # class HDCEncoder:
# #     def __init__(self, config=MockConfig):
# #         """
# #         Initializes the Item Memory (Dictionary) using deterministic PRNG.
# #         In hardware, this becomes a static ROM block.
# #         """
# #         self.config = config
# #         np.random.seed(self.config.SEED)
# #
# #         # Generate orthogonal boolean hypervectors for our 3 spike states {-1, 0, 1}.
# #         # We use 0 and 1 strictly here to map directly to Verilog wires.
# #         self.item_memory = {
# #             1: np.random.randint(2, size=self.config.D, dtype=np.int8),  # UP Spike
# #             -1: np.random.randint(2, size=self.config.D, dtype=np.int8),  # DOWN Spike
# #             0: np.random.randint(2, size=self.config.D, dtype=np.int8)  # IDLE
# #         }
# #
# #     def permute(self, hv, shift):
# #         """
# #         Cyclic bit-shift (ρ). Represents temporal sequence.
# #         Hardware translation: Zero-cost wire routing on the FPGA fabric.
# #         """
# #         return np.roll(hv, shift)
# #
# #     def bind(self, hv1, hv2):
# #         """
# #         Bitwise XOR binding (⊕).
# #         Hardware translation: Parallel array of 8192 XOR gates.
# #         """
# #         return np.bitwise_xor(hv1, hv2)
# #
# #     def bundle_and_threshold(self, hv_matrix):
# #         """
# #         Element-wise addition followed by a majority gate.
# #         """
# #         N = hv_matrix.shape[0]
# #
# #         # Sum the 1s down the columns
# #         # Hardware translation: Array of small accumulators/Popcount
# #         bit_counts = np.sum(hv_matrix, axis=0)
# #
# #         # Majority thresholding: if count > N/2, it becomes 1, else 0.
# #         # Hardware translation: A simple comparator (e.g., > 127 for a window of 256)
# #         majority_hv = (bit_counts > (N // 2)).astype(np.int8)
# #
# #         return majority_hv
# #
# #     def encode_sequence(self, spike_window):
# #         """
# #         Takes a time-window of spikes and compiles them into a single D-dimensional hypervector.
# #         """
# #         temporal_hvs = []
# #
# #         for t, spike in enumerate(spike_window):
# #             # THE FIX: Ignore '0' (Idle) states so they don't drown out the actual spikes!
# #             if spike == 0:
# #                 continue
# #
# #             # 1. ROM Lookup: Grab the base hypervector from Item Memory
# #             base_hv = self.item_memory[spike]
# #
# #             # 2. Temporal Encoding: Permute it based on its time step (t)
# #             # This remembers sequence without needing a recurrent loop (RNN/LSTM)
# #             time_encoded_hv = self.permute(base_hv, t)
# #
# #             temporal_hvs.append(time_encoded_hv)
# #
# #         # Fallback if the signal was completely flat (no spikes triggered)
# #         if len(temporal_hvs) == 0:
# #             return np.zeros(self.config.D, dtype=np.int8)
# #
# #         # Stack into matrix for hardware-like parallel bundling
# #         hv_matrix = np.vstack(temporal_hvs)
# #
# #         # 3. Superposition: Bundle and apply majority gate to compress back to D-bits
# #         final_encoded_hv = self.bundle_and_threshold(hv_matrix)
# #
# #         return final_encoded_hv
# #
# #
# # if __name__ == "__main__":
# #     # Local verification simulating an 8-tick analog wave converted to spikes
# #     encoder = HDCEncoder()
# #     dummy_spikes = np.array([1, 0, -1, 1, 0, 0, -1, 1])
# #
# #     encoded_hv = encoder.encode_sequence(dummy_spikes)
# #     print(f"Input Spike Window: {dummy_spikes}")
# #     print(f"Output Hypervector Shape: {encoded_hv.shape}")
# #     print(f"Output Hypervector (First 20 bits): {encoded_hv[:20]}")
# #     print(f"Notice it is strictly Boolean: Min {encoded_hv.min()}, Max {encoded_hv.max()}")
# #
# # import numpy as np
# #
# #
# # class HDCEncoder:
# #     def __init__(self, config):
# #         self.config = config
# #         np.random.seed(self.config.SEED)
# #
# #         # Base vectors for spike states
# #         self.item_memory = {
# #             1: np.random.randint(2, size=self.config.D, dtype=np.int8),
# #             -1: np.random.randint(2, size=self.config.D, dtype=np.int8)
# #         }
# #
# #     def encode_sequence(self, spike_window):
# #         """
# #         N-Gram Spatial Encoding: Binds adjacent spikes to capture morphology.
# #         Includes a fallback for sparse inputs to prevent empty-sequence errors.
# #         """
# #         # Filter only active spikes
# #         active_spikes = [s for s in spike_window if s != 0]
# #
# #         # Fallback: if we have zero or one spike, we cannot form pairs (N-grams)
# #         if len(active_spikes) < 2:
# #             if not active_spikes:
# #                 return np.zeros(self.config.D, dtype=np.int8)
# #             # Return base vector for the single spike present
# #             return self.item_memory[active_spikes[0]]
# #
# #         # Create N-Grams (pairs of spikes)
# #         ngrams = []
# #         for i in range(len(active_spikes) - 1):
# #             s1 = active_spikes[i]
# #             s2 = active_spikes[i + 1]
# #             # Bind spike1 with shifted spike2
# #             hv1 = np.roll(self.item_memory[s1], i)
# #             hv2 = np.roll(self.item_memory[s2], i + 1)
# #             ngrams.append(np.bitwise_xor(hv1, hv2))
# #
# #         # Bundle all N-Grams
# #         bundled = np.sum(np.vstack(ngrams), axis=0)
# #         return (bundled > (len(ngrams) // 2)).astype(np.int8)
#
#
# # import numpy as np
# #
# #
# # class HDCEncoder:
# #     def __init__(self, config):
# #         self.config = config
# #         np.random.seed(self.config.SEED)
# #
# #         # Base vectors for spike states (multi-channel input)
# #         # We need a base for 1 and -1 for each of the 3 channels
# #         self.num_channels = 3
# #         self.item_memory = {
# #             (ch, val): np.random.randint(2, size=self.config.D, dtype=np.int8)
# #             for ch in range(self.num_channels)
# #             for val in [1, -1]
# #         }
# #
# #         # Temporal Position Hypervectors (to bind timing information)
# #         self.num_bins = 4
# #         self.pos_vectors = [np.random.randint(2, size=self.config.D, dtype=np.int8)
# #                             for _ in range(self.num_bins)]
# #
# #     def encode_sequence(self, spike_matrix):
# #         """
# #         Temporal Binning Encoding:
# #         Divides the window into 4 temporal bins. Each bin is encoded
# #         individually and bound to a temporal position vector.
# #         """
# #         # spike_matrix shape: (3, WINDOW_SIZE)
# #         bin_size = spike_matrix.shape[1] // self.num_bins
# #         bundled_total = np.zeros(self.config.D, dtype=np.int32)
# #
# #         for b in range(self.num_bins):
# #             start = b * bin_size
# #             end = (b + 1) * bin_size
# #             bin_data = spike_matrix[:, start:end]
# #
# #             bin_hv = np.zeros(self.config.D, dtype=np.int32)
# #
# #             # Aggregate all spikes in this temporal bin
# #             for ch in range(self.num_channels):
# #                 # Positive spikes
# #                 pos_indices = np.where(bin_data[ch] == 1)[0]
# #                 for _ in pos_indices:
# #                     bin_hv += self.item_memory[(ch, 1)]
# #
# #                 # Negative spikes
# #                 neg_indices = np.where(bin_data[ch] == -1)[0]
# #                 for _ in neg_indices:
# #                     bin_hv += self.item_memory[(ch, -1)]
# #
# #             # Bind to Position Vector (using XOR binding)
# #             # Threshold the bin_hv first to keep it boolean
# #             bin_bool = (bin_hv > 0).astype(np.int8)
# #
# #             # Final binding: XOR with the position vector
# #             bundled_total += np.bitwise_xor(bin_bool, self.pos_vectors[b])
# #
# #         # Majority rule thresholding
# #         return (bundled_total > (self.num_bins // 2)).astype(np.int8)
#
#
# # import numpy as np
# #
# #
# # class HDCEncoder:
# #     def __init__(self, config):
# #         self.config = config
# #         np.random.seed(self.config.SEED)
# #
# #         # Base vectors for spike polarity (1 or -1)
# #         # FIX: Changed dtype to np.int32 to safely handle dense spike clusters (pos_count > 127)
# #         self.item_memory = {
# #             1: np.random.randint(2, size=self.config.D, dtype=np.int32),
# #             -1: np.random.randint(2, size=self.config.D, dtype=np.int32)
# #         }
# #
# #         # Temporal Position Hypervectors (The secret to beating CNNs)
# #         # This gives the model "Spatial Awareness" of the QRS complex
# #         # Divides the window into 4 bins (e.g., Pre-QRS, QRS-Up, QRS-Down, Post-QRS)
# #         self.num_bins = 4
# #         self.pos_vectors = [np.random.randint(2, size=self.config.D, dtype=np.int8)
# #                             for _ in range(self.num_bins)]
# #
# #     def encode_sequence(self, spike_train):
# #         """
# #         Temporal Binning Encoding (1D Version):
# #         Divides the 1D spike train into temporal bins and binds them to time vectors.
# #         Replicates CNN spatial sensitivity using pure bitwise operations.
# #         """
# #         # spike_train shape from your DeltaTokenizer is 1D (e.g., 256)
# #         window_size = len(spike_train)
# #         bin_size = window_size // self.num_bins
# #
# #         bundled_total = np.zeros(self.config.D, dtype=np.int32)
# #
# #         for b in range(self.num_bins):
# #             start = b * bin_size
# #             end = (b + 1) * bin_size if b < self.num_bins - 1 else window_size
# #             bin_data = spike_train[start:end]
# #
# #             bin_hv = np.zeros(self.config.D, dtype=np.int32)
# #
# #             # Count positive spikes in this specific time bin
# #             pos_count = np.count_nonzero(bin_data == 1)
# #             if pos_count > 0:
# #                 bin_hv += self.item_memory[1] * pos_count
# #
# #             # Count negative spikes in this specific time bin
# #             neg_count = np.count_nonzero(bin_data == -1)
# #             if neg_count > 0:
# #                 bin_hv += self.item_memory[-1] * neg_count
# #
# #             # Threshold the bin to make it a Boolean Hypervector again
# #             bin_bool = (bin_hv > 0).astype(np.int8)
# #
# #             # Bind to Time Position (This tells HDC *when* the spike happened)
# #             bound_bin = np.bitwise_xor(bin_bool, self.pos_vectors[b])
# #             bundled_total += bound_bin
# #
# #         # Final majority threshold to output the single heartbeat hypervector
# #         return (bundled_total > (self.num_bins // 2)).astype(np.int8)
#
#
# import numpy as np
#
#
# class HDCEncoder:
#     def __init__(self, config):
#         self.config = config
#         np.random.seed(self.config.SEED)
#
#         # Bipolar Vectors (-1 and 1) instead of Boolean (0 and 1).
#         # This is CRITICAL. It allows us to safely multiply by spike counts
#         # (e.g., pos_count = 140) without destroying the magnitude information.
#         self.item_memory = {
#             1: np.random.choice([-1, 1], size=self.config.D).astype(np.int32),
#             -1: np.random.choice([-1, 1], size=self.config.D).astype(np.int32)
#         }
#
#         # Temporal Position Hypervectors (Spatial Awareness)
#         # Also initialized as Bipolar to allow for multiplicative binding
#         self.num_bins = 4
#         self.pos_vectors = [np.random.choice([-1, 1], size=self.config.D).astype(np.int32)
#                             for _ in range(self.num_bins)]
#
#     def encode_sequence(self, spike_train):
#         """
#         Temporal Binning Encoding (Bipolar 1D Version):
#         Preserves spike density and magnitude using bipolar arithmetic.
#         """
#         # spike_train shape from your DeltaTokenizer is 1D (e.g., 256)
#         window_size = len(spike_train)
#         bin_size = window_size // self.num_bins
#
#         bundled_total = np.zeros(self.config.D, dtype=np.int32)
#
#         for b in range(self.num_bins):
#             start = b * bin_size
#             end = (b + 1) * bin_size if b < self.num_bins - 1 else window_size
#             bin_data = spike_train[start:end]
#
#             bin_hv = np.zeros(self.config.D, dtype=np.int32)
#
#             # Scale bipolar base vectors by the exact number of spikes
#             pos_count = np.count_nonzero(bin_data == 1)
#             if pos_count > 0:
#                 bin_hv += self.item_memory[1] * pos_count
#
#             neg_count = np.count_nonzero(bin_data == -1)
#             if neg_count > 0:
#                 bin_hv += self.item_memory[-1] * neg_count
#
#             # Bind to Time Position using Bipolar Multiplication
#             # In bipolar HDC math, multiplication is mathematically equivalent to XOR,
#             # but it preserves the integer scale (density) of bin_hv!
#             bound_bin = bin_hv * self.pos_vectors[b]
#             bundled_total += bound_bin
#
#         # Convert the final accumulated bipolar vector back to standard Boolean {0, 1}.
#         # This makes it perfectly compatible with your AssociativeMemory's XOR logic.
#         return (bundled_total > 0).astype(np.int8)

import numpy as np


class HDCEncoder:
    def __init__(self, config):
        self.config = config
        np.random.seed(self.config.SEED)

        # 1. Channel Vectors (Low, Mid, High thresholds)
        self.num_channels = 3
        self.channel_memory = [np.random.choice([-1, 1], size=self.config.D).astype(np.int32)
                               for _ in range(self.num_channels)]

        # 2. Polarity Vectors (Up-spike vs Down-spike)
        self.item_memory = {
            1: np.random.choice([-1, 1], size=self.config.D).astype(np.int32),
            -1: np.random.choice([-1, 1], size=self.config.D).astype(np.int32)
        }

        # 3. Exact Temporal Position Vectors
        # One unique hypervector for every possible index in the 256-sample window
        self.pos_memory = [np.random.choice([-1, 1], size=self.config.D).astype(np.int32)
                           for _ in range(self.config.WINDOW_SIZE)]

    def encode_sequence(self, spike_matrix):
        """
        Exact Temporal Binding:
        HV = Sum( Channel * Polarity * Exact_Time_Index )
        Only executes math on ACTIVE spikes, making it incredibly fast and sparse.
        """
        if spike_matrix.ndim == 1:
            spike_matrix = spike_matrix.reshape(1, -1)

        num_channels, window_size = spike_matrix.shape
        bundled_total = np.zeros(self.config.D, dtype=np.int32)

        # Iterate through the channels
        for ch in range(min(num_channels, self.num_channels)):

            # Find the exact indices where spikes occurred (Sparsity > 97%)
            active_indices = np.nonzero(spike_matrix[ch])[0]

            for t in active_indices:
                spike_polarity = spike_matrix[ch, t]

                # Bipolar Binding (Multiplication)
                # We bind the Channel ID + The Spike Polarity + The Exact Time Index
                bound_hv = self.channel_memory[ch] * self.item_memory[spike_polarity] * self.pos_memory[t]

                # Accumulate
                bundled_total += bound_hv

        # Final majority threshold to output the Boolean hypervector
        # If no spikes fired at all, it safely returns an empty vector
        return (bundled_total > 0).astype(np.int8)