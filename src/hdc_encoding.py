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