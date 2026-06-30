import numpy as np


class AssociativeMemory:
    def __init__(self, config):
        """
        Initializes the One-Shot Classifier.
        In hardware, the final prototypes will be stored in BRAM.
        """
        self.config = config

        # Accumulators for training
        self.prototype_sums = {}
        self.prototype_counts = {}

        # The finalized binary BRAM maps
        self.prototypes = {}

    def add_to_class(self, hv, class_label):
        """
        One-Shot Training Step.
        Accumulates the encoded D-dimensional hypervectors into a class sum.
        Hardware translation: Parallel array of integer adders.
        """
        if class_label not in self.prototype_sums:
            # Initialize with 32-bit integers just to prevent overflow during accumulation
            self.prototype_sums[class_label] = np.zeros(self.config.D, dtype=np.int32)
            self.prototype_counts[class_label] = 0

        self.prototype_sums[class_label] += hv
        self.prototype_counts[class_label] += 1

    def finalize_prototypes(self):
        """
        Bakes the accumulated vectors into final binary prototypes.
        Hardware translation: A single comparator checking if the count > N/2.
        """
        for class_label in self.prototype_sums:
            count = self.prototype_counts[class_label]
            threshold = count // 2

            # Majority rule: compress the sum back into a pure Boolean vector
            self.prototypes[class_label] = (self.prototype_sums[class_label] > threshold).astype(np.int8)

    def hamming_distance(self, hv1, hv2):
        """
        Calculates the difference between two boolean vectors.
        Hardware translation: Parallel XOR array -> Adder Tree (Popcount).
        """
        xor_result = np.bitwise_xor(hv1, hv2)
        return int(np.sum(xor_result))  # Popcount

    def predict(self, query_hv):
        """
        Compares the live query vector against all saved prototypes in memory.
        Returns the class with the lowest Hamming distance.
        """
        if not self.prototypes:
            raise ValueError("Prototypes not generated. Run finalize_prototypes() first.")

        best_class = None
        min_distance = float('inf')  # In hardware, this is initialized to maximum integer (e.g., 8192)

        distances = {}
        for class_label, proto_hv in self.prototypes.items():
            dist = self.hamming_distance(query_hv, proto_hv)
            distances[class_label] = dist

            # The winning class has the smallest Hamming distance
            if dist < min_distance:
                min_distance = dist
                best_class = class_label

        return best_class, distances


# Local Mock Verification
if __name__ == "__main__":
    # Mocking the configuration
    class MockConfig:
        D = 8192


    config = MockConfig()
    memory = AssociativeMemory(config)

    # 1. Simulating Training Mode
    print("Training on 10 Normal samples and 10 Arrhythmia samples...")
    for _ in range(10):
        # Generate random boolean vectors to simulate encoded normal heartbeats
        mock_normal_hv = np.random.randint(2, size=config.D, dtype=np.int8)
        memory.add_to_class(mock_normal_hv, "Normal")

        # Generate random boolean vectors to simulate encoded arrhythmias
        mock_arrhythmia_hv = np.random.randint(2, size=config.D, dtype=np.int8)
        memory.add_to_class(mock_arrhythmia_hv, "Arrhythmia")

    # 2. Bake the memory (Finalize)
    memory.finalize_prototypes()
    print("Memory Prototypes baked to binary.\n")

    # 3. Simulating Inference Mode
    # Create a random query vector
    query_hv = np.random.randint(2, size=config.D, dtype=np.int8)

    prediction, distances = memory.predict(query_hv)

    print(f"Final Prediction: {prediction}")
    print(f"Hamming Distances: {distances}")
    print(f"Difference: {abs(distances['Normal'] - distances['Arrhythmia'])} bits")