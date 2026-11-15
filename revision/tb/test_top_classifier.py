"""End-to-end cocotb test of top_shde_classifier (submitted core + wrapper logic + assoc_mem).

Streams the 2 committed golden analog heartbeats through the RTL and checks
  1. static_hv_reg == golden_expected_hv.dat   (encoder bit-exact; also reveals the bit order),
  2. serialised hv_data_out words == static_hv_reg,
  3. RTL class_idx/min_dist == Python AssociativeMemory.predict on the golden HV.
Run with QUERY_REV=0 and 1 (runner env) - only the matching order can pass check 3.
"""
import os, sys
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

ROOT = os.environ["NEUROHDC_ROOT"]
sys.path.insert(0, ROOT)
from src.associative_mem import AssociativeMemory  # noqa: E402

MEM = os.path.join(ROOT, "hw/vivado/NeuroHDC/NeuroHDC.ip_user_files/mem_init_files")
LABELS = ["PVC", "PAC", "Normal", "LBBB", "RBBB"]
D = 4096


def lines(p):
    with open(p) as f:
        return [l.strip() for l in f if l.strip()]


@cocotb.test()
async def test_top(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    stim = [[int(x) for x in l.split()] for l in lines(os.path.join(MEM, "golden_stimulus_analog.dat"))]
    gold = lines(os.path.join(MEM, "golden_expected_hv.dat"))
    protos = [np.array([int(c) for c in s], dtype=np.int8) for s in lines(os.path.join(MEM, "prototypes.dat"))]
    am = AssociativeMemory(None)
    am.prototypes = {LABELS[i]: protos[i] for i in range(5)}
    rev = int(os.environ.get("QUERY_REV", 0))
    dut._log.info(f"QUERY_REV={rev}")

    for b, wave in enumerate(stim):
        dut.rst_n.value = 0; dut.valid_in.value = 0; dut.analog_in.value = 0
        for _ in range(3): await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        await RisingEdge(dut.clk)

        words, got_cls = [], None
        n_cycles = 0

        async def tick():
            nonlocal got_cls, n_cycles
            await RisingEdge(dut.clk)
            n_cycles += 1
            if dut.hv_valid_out.value == 1:
                words.append(int(dut.hv_data_out.value))
            if dut.class_valid.value == 1 and got_cls is None:
                got_cls = (int(dut.class_idx.value), int(dut.min_dist.value), n_cycles)

        for t, v in enumerate(wave):
            dut.analog_in.value = v; dut.valid_in.value = 1
            await tick()
            dut.valid_in.value = 0
            if t == len(wave) - 1:
                break
            for _ in range(45): await tick()
        for _ in range(3000):                       # drain: hv_ready, serialiser (128 words), AM (~165 cycles)
            await tick()
            if got_cls is not None and len(words) >= 128: break
        assert got_cls is not None, "no class_valid pulse"

        sh = dut.static_hv_reg.value.to_unsigned()
        s_str = format(sh, f"0{D}b")
        orient = "direct (char0=MSB)" if s_str == gold[b] else "reversed (char0=LSB)" if s_str[::-1] == gold[b] else "MISMATCH"
        dut._log.info(f"beat {b}: static_hv_reg vs golden HV -> {orient}")
        assert orient != "MISMATCH", "encoder output differs from golden HV"
        # serialiser check (unchanged function)
        assert len(words) >= 128, f"serialiser produced {len(words)} words"
        rebuilt = sum(w << (32 * k) for k, w in enumerate(words[:128]))
        assert rebuilt == sh, "serialised words do not rebuild static_hv_reg"
        # classifier check
        hv = np.array([int(c) for c in gold[b]], dtype=np.int8)
        py_lab, dists = am.predict(hv)
        idx, md, cyc = got_cls
        dut._log.info(f"beat {b}: RTL class={LABELS[idx]} dist={md} | Python class={py_lab} dist={dists[py_lab]} "
                      f"| all python dists={dists}")
        assert LABELS[idx] == py_lab and md == dists[py_lab], \
            f"RTL/Python mismatch (QUERY_REV={rev}, hv orientation {orient})"
    dut._log.info("PASS: encoder bit-exact, serialiser intact, classifier matches Python")
