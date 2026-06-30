import numpy as np

class DeltaTokenizer:
    def __init__(self, thresholds=[0.1, 0.45, 0.8]):
        # Ensure thresholds is always a list to prevent iteration errors
        if isinstance(thresholds, (float, int)):
            self.thresholds = [float(thresholds)]
        else:
            self.thresholds = thresholds

    def encode(self, wave):
        """
        Returns a multi-channel spike array.
        Returns a (len(thresholds), WINDOW_SIZE) matrix.
        """
        diff = np.diff(wave, prepend=wave[0])
        # diff = np.diff(np.diff(wave, prepend=wave[0]), prepend=0)
        spikes = []
        for t in self.thresholds:
            s = np.zeros_like(wave)
            s[diff > t] = 1
            s[diff < -t] = -1
            spikes.append(s)
        return np.array(spikes) # Shape (N_thresholds, WINDOW_SIZE)