class SHDEConfig:
    """
    Global hardware and algorithmic parameters for the Spiking-HDC pipeline.
    """
    # HDC Parameters
    D = 4096  # Hypervector dimension (Power of 2 for BRAM optimization)
    SEED = 42  # Fixed PRNG seed for deterministic Item Memory generation

    # Delta-Tokenizer Parameters
    # This acts as our analog-to-spike voltage threshold
    V_TH = 0.2  # Threshold to trigger an up/down spike (tune this per dataset)

    # Data Parameters
    SAMPLING_RATE = 360  # MIT-BIH dataset standard sampling rate (Hz)
    WINDOW_SIZE = 256  # Number of analog samples processed per temporal window