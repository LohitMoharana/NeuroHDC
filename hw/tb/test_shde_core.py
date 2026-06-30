import os
import numpy as np
import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
from cocotb.clock import Clock


@cocotb.test()
async def test_shde_core(dut):
    """Test the Folded Spiking-HDC Core with Dynamic Dimension Emulation"""

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.rst_n.value = 0
    dut.valid_in.value = 0
    dut.analog_in.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    data_dir = os.path.join(os.path.dirname(__file__), 'data')

    analog_stimulus = []
    with open(os.path.join(data_dir, 'golden_stimulus_analog.dat'), 'r') as f:
        for line in f:
            analog_stimulus.append([int(x) for x in line.strip().split()])

    # Load the base BRAM states as bipolar numpy arrays to emulate the exact Verilog bitwise math
    def load_bipolar_mem(filename):
        mem = []
        with open(os.path.join(data_dir, filename), 'r') as f:
            for line in f:
                mem.append(np.array([1 if c == '1' else -1 for c in line.strip()], dtype=np.int32))
        return mem

    ch_mem = load_bipolar_mem('channel_memory.dat')
    item_mem = load_bipolar_mem('item_memory.dat')
    pos_mem = load_bipolar_mem('pos_memory.dat')

    # --- DYNAMIC DIMENSION DETECTION ---
    # Automatically adapts to D=4096 or D=8192 so numpy never crashes
    D_len = len(pos_mem[0])
    dut._log.info(f"Dynamically detected D = {D_len} bits from memory files.")

    # Constants to match Verilog tokenizer integer thresholds
    THRESH = [1638, 8191, 19660]

    for i, wave in enumerate(analog_stimulus):
        dut._log.info(f"--- Streaming Heartbeat {i + 1}/{len(analog_stimulus)} ---")

        dut.rst_n.value = 0
        await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        await RisingEdge(dut.clk)

        # Array size dynamically matches the exact size exported by Python
        bundled_total = np.zeros(D_len, dtype=np.int32)
        prev_val = 0

        for t, val in enumerate(wave):
            dut.analog_in.value = val
            dut.valid_in.value = 1
            await RisingEdge(dut.clk)
            dut.valid_in.value = 0

            delta = 0 if t == 0 else (val - prev_val)
            prev_val = val

            for ch in range(3):
                polarity = 0
                if delta >= THRESH[ch]:
                    polarity = 1
                elif delta <= -THRESH[ch]:
                    polarity = -1

                if polarity != 0:
                    item_vec = item_mem[0] if polarity == 1 else item_mem[1]
                    bundled_total += ch_mem[ch] * item_vec * pos_mem[t]

            if t == len(wave) - 1:
                break

            # Wait for folding loop to complete (Safe for FOLDS=32)
            for _ in range(45):
                await RisingEdge(dut.clk)

        expected_bin_str = "".join(['1' if v > 0 else '0' for v in bundled_total])

        while True:
            await ReadOnly()
            if dut.hv_ready.value == 1:
                break
            await RisingEdge(dut.clk)

        actual_bin_str = str(dut.final_hv.value)

        dut._log.info(f"Emulated (First 32 bits): {expected_bin_str[:32]}")
        dut._log.info(f"Verilog  (First 32 bits): {actual_bin_str[:32]}")

        dist_direct = sum(c1 != c2 for c1, c2 in zip(actual_bin_str, expected_bin_str))
        dist_reversed = sum(c1 != c2 for c1, c2 in zip(actual_bin_str[::-1], expected_bin_str))

        hamming_dist = min(dist_direct, dist_reversed)

        dut._log.info(f"Hamming Distance: {hamming_dist} bits.")
        assert hamming_dist == 0, f"Hardware mismatch! Off by {hamming_dist} bits."

        await RisingEdge(dut.clk)

    dut._log.info("SUCCESS: Zero-Multiplier Verilog matches Python perfectly!")


if __name__ == "__main__":
    import subprocess
    import sys

    os.environ["COCOTB_TEST_MODULES"] = "test_shde_core"
    os.environ["COCOTB_TOPLEVEL"] = "top_shde_core"

    cocotb_base = os.path.dirname(cocotb.__file__)
    site_packages = os.path.dirname(cocotb_base)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([os.getcwd(), site_packages, os.path.dirname(site_packages)])
    env["PYGPI_PYTHON_BIN"] = sys.executable

    proj_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rtl"))
    sources = [os.path.join(proj_path, "delta_tokenizer.v"),
               os.path.join(proj_path, "hdc_bind_bundle.v"),
               os.path.join(proj_path, "top_shde_core.v")]

    # --- NEW: AUTO-CHUNKER ---
    # Replaces fix_bram.py. Automatically slices the exact dimensions from data/
    # to feed Vivado/Icarus, ensuring you never hit a dimension mismatch warning again.
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    CHUNK = 128


    def chunk_and_copy(src_file, line_idx, dst_file):
        src_path = os.path.join(data_dir, src_file)
        dst_path = os.path.join(os.path.dirname(__file__), dst_file)
        if not os.path.exists(src_path): return
        with open(src_path, 'r') as f:
            lines = [l.strip() for l in f]
        with open(dst_path, 'w') as f:
            if line_idx is not None:
                line = lines[line_idx]
                for i in range(0, len(line), CHUNK):
                    f.write(line[i:i + CHUNK] + '\n')
            else:
                for line in lines:
                    for i in range(0, len(line), CHUNK):
                        f.write(line[i:i + CHUNK] + '\n')


    print("Auto-chunking memory files for Vivado/Icarus...")
    chunk_and_copy('channel_memory.dat', 0, 'ch0.dat')
    chunk_and_copy('channel_memory.dat', 1, 'ch1.dat')
    chunk_and_copy('channel_memory.dat', 2, 'ch2.dat')
    chunk_and_copy('item_memory.dat', 0, 'item_up.dat')
    chunk_and_copy('item_memory.dat', 1, 'item_dn.dat')
    chunk_and_copy('pos_memory.dat', None, 'pos.dat')

    subprocess.run(["iverilog", "-o", "sim.vvp", "-s", "top_shde_core"] + sources, check=True)
    subprocess.run(["vvp", "-M", os.path.join(cocotb_base, "libs"), "-m", "cocotbvpi_icarus", "sim.vvp"], env=env,
                   check=True)