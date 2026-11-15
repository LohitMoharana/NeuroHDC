"""cocotb: scaled ASIC wrapper + streaming associative memory vs Python AssociativeMemory (D=N from env).
Random analog windows -> real prototype core -> chunk stream (captured from internal wires) -> RTL class.
Expected class = Python AssociativeMemory.predict() on the captured 256-bit HV with the same 5 prototypes."""
import os, sys, random
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

ROOT = os.environ["NEUROHDC_ROOT"]
sys.path.insert(0, ROOT)
from src.associative_mem import AssociativeMemory  # noqa: E402
MEM = os.path.join(ROOT, "hw/vivado/NeuroHDC/NeuroHDC.ip_user_files/mem_init_files")
LABELS = ["PVC", "PAC", "Normal", "LBBB", "RBBB"]
N_WIN = int(os.environ.get("N_WIN", 4))
GAP = 45
ND = int(os.environ["NDIM"]); FOLDS = ND // 128


@cocotb.test()
async def test_cls(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    with open(os.path.join(MEM, "prototypes.dat")) as f:
        protos = [np.array([int(c) for c in l.strip()], dtype=np.int8) for l in f if l.strip()]
    protos = [p[:ND] for p in protos]
    am = AssociativeMemory(None)
    am.prototypes = {LABELS[i]: protos[i] for i in range(5)}

    dut.rst_n.value = 0; dut.valid_in.value = 0; dut.analog_in.value = 0
    for _ in range(4): await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # Baseline-core simulation artifact: after a FIFO pop the read pointer already points at the next slot, so
    # with slow input the binder reads a never-written (X) FIFO slot. The stub vectors are constants, so a slot
    # written once is correct forever. Prime every slot with a fast burst, then reset (arrays are not reset).
    for t in range(48):
        dut.analog_in.value = 20000 if t % 2 else -20000
        dut.valid_in.value = 1
        await RisingEdge(dut.clk)
    dut.valid_in.value = 0
    for _ in range(600): await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    for _ in range(4): await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    chunks, results = [], []
    async def monitor():
        while True:
            await RisingEdge(dut.clk)
            if dut.internal_chunk_valid.value == 1:
                chunks.append(str(dut.internal_chunk_hv.value))
            if dut.class_valid.value == 1:
                results.append((int(dut.class_idx.value), int(dut.min_dist.value)))
    cocotb.start_soon(monitor())

    rng = random.Random(42)
    for w in range(N_WIN):
        amp = rng.choice([4000, 12000, 30000])
        v = 0
        for t in range(256):
            v = max(-32768, min(32767, v + rng.randint(-amp, amp)))
            dut.analog_in.value = v; dut.valid_in.value = 1
            await RisingEdge(dut.clk)
            dut.valid_in.value = 0
            for _ in range(GAP): await RisingEdge(dut.clk)
    for _ in range(400): await RisingEdge(dut.clk)

    dut._log.info(f"windows driven {N_WIN}; chunks captured {len(chunks)}; class results {len(results)}")
    assert len(chunks) == FOLDS * N_WIN, f"expected {FOLDS*N_WIN} chunks, got {len(chunks)}"
    assert len(results) == N_WIN, f"expected {N_WIN} class results, got {len(results)}"
    mism, hist, nonzero = 0, {}, 0
    for w in range(N_WIN):
        hv = np.array([int(c) for c in "".join(chunks[FOLDS*w:FOLDS*w+FOLDS])], dtype=np.int8)
        nonzero += int(hv.any())
        lab, d = am.predict(hv)
        idx, md = results[w]
        hist[LABELS[idx]] = hist.get(LABELS[idx], 0) + 1
        if LABELS[idx] != lab or md != d[lab]:
            mism += 1
            dut._log.error(f"win {w}: RTL {LABELS[idx]}/{md} vs Python {lab}/{d[lab]}")
    dut._log.info(f"mismatches {mism}/{N_WIN}; windows with non-zero HV {nonzero}; RTL class histogram {hist}")
    assert mism == 0
