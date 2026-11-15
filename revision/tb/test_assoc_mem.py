"""cocotb testbench: RTL assoc_mem vs the Python model (src/associative_mem.py).

For every query hypervector, checks that the RTL predicted class AND minimum
Hamming distance equal AssociativeMemory.predict() of the Python model.
Stimulus sets:
  golden : the 2 committed golden heartbeat HVs (golden_expected_hv.dat)
  beats  : real MIT-BIH beats encoded by the Python encoder
  synth  : seeded random / near-prototype / all-0 / all-1 queries
  ties   : queries built to be exactly equidistant from two prototypes
"""
import os, sys, random
import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

ROOT = os.environ["NEUROHDC_ROOT"]
sys.path.insert(0, ROOT)
from src.associative_mem import AssociativeMemory  # noqa: E402

MEM = os.path.join(ROOT, "hw/vivado/NeuroHDC/NeuroHDC.ip_user_files/mem_init_files")
D = 4096
N_BEATS = int(os.environ.get("N_BEATS", 300))
LABELS = ["PVC", "PAC", "Normal", "LBBB", "RBBB"]  # order of hw/tb/data/class_labels.txt


def load_lines(p):
    with open(p) as f:
        return [l.strip() for l in f if l.strip()]


def s2a(s):
    return np.array([1 if c == "1" else 0 for c in s], dtype=np.int8)


def a2int(a):  # string char 0 -> MSB (Verilog literal order)
    return int("".join("1" if v else "0" for v in a), 2)


def build_model():
    protos = [s2a(s) for s in load_lines(os.path.join(MEM, "prototypes.dat"))]
    assert len(protos) == 5 and all(len(p) == D for p in protos)
    am = AssociativeMemory(None)
    am.prototypes = {LABELS[i]: protos[i] for i in range(5)}  # insertion order = class index
    return am, protos


async def run_query(dut, q_int):
    dut.query.value = q_int
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0
    n = 1
    while True:
        await RisingEdge(dut.clk)
        n += 1
        if dut.done.value == 1:
            return int(dut.class_idx.value), int(dut.min_dist.value), n
        assert n < 5000, "timeout waiting for done"


def beat_hvs(n):
    from src.config import SHDEConfig
    from src.hdc_encoding import HDCEncoder
    from src.tokenizer import DeltaTokenizer
    from src.data_loader import MITBIHLoader
    enc, tok = HDCEncoder(SHDEConfig()), DeltaTokenizer(thresholds=[0.05, 0.25, 0.6])
    ld = MITBIHLoader(os.path.join(os.environ["NEUROHDC_DATA"], "MIT-BIH"))
    out = []
    for rec in ["100", "106", "200", "207", "212", "214"]:
        X, y = ld.load_record(rec)
        for w, lab in zip(X, y):
            out.append((lab, enc.encode_sequence(tok.encode(w))))
    random.Random(42).shuffle(out)
    return out[:n]


@cocotb.test()
async def test_assoc_mem(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.start.value = 0
    dut.query.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    am, protos = build_model()
    stats, mism, lat = {}, [], [0]

    async def check(tag, set_name, hv):
        py_lab, dists = am.predict(hv)
        py_idx, py_min = LABELS.index(py_lab), dists[py_lab]
        idx, md, cyc = await run_query(dut, a2int(hv))
        s = stats.setdefault(set_name, [0, 0])
        s[0] += 1
        if idx != py_idx or md != py_min:
            s[1] += 1
            mism.append((tag, "rtl", idx, md, "py", py_idx, py_min))
        lat[0] = cyc
        return idx, py_idx

    for i, s in enumerate(load_lines(os.path.join(MEM, "golden_expected_hv.dat"))):
        idx, py_idx = await check(f"golden{i}", "golden", s2a(s))
        dut._log.info(f"golden beat {i}: RTL class={LABELS[idx]}  Python class={LABELS[py_idx]}")

    conf = {}
    for lab, hv in beat_hvs(N_BEATS):
        idx, _ = await check(lab, "beats", hv)
        conf[(lab, LABELS[idx])] = conf.get((lab, LABELS[idx]), 0) + 1

    rng = np.random.default_rng(42)
    for k in range(200):
        await check(f"rand{k}", "synth", rng.integers(0, 2, D, dtype=np.int8))
    for c in range(5):
        await check(f"proto{c}", "synth", protos[c].copy())
        for nflip in (1, 100, 1000, 1900):
            hv = protos[c].copy()
            hv[rng.choice(D, nflip, replace=False)] ^= 1
            await check(f"proto{c}-flip{nflip}", "synth", hv)
    await check("all0", "synth", np.zeros(D, dtype=np.int8))
    await check("all1", "synth", np.ones(D, dtype=np.int8))

    n_ties = 0
    for a in range(5):
        for b in range(a + 1, 5):
            diff = np.nonzero(protos[a] != protos[b])[0]
            hv = protos[a].copy()
            half = diff[: len(diff) // 2]
            hv[half] = protos[b][half]
            da, db = int((hv != protos[a]).sum()), int((hv != protos[b]).sum())
            py_lab, dists = am.predict(hv)
            exact_tie_is_min = (da == db) and dists[LABELS[a]] == min(dists.values())
            n_ties += int(exact_tie_is_min)
            await check(f"tie{a}{b}(da={da},db={db},tie_is_min={exact_tie_is_min})", "ties", hv)

    for k, v in stats.items():
        dut._log.info(f"SET {k:7s}: {v[0]:4d} queries, {v[1]} mismatches")
    dut._log.info(f"forced ties that were the minimum (lowest-index rule exercised): {n_ties}")
    dut._log.info(f"latency start->done: {lat[0]} cycles")
    dut._log.info(f"(true label, RTL label) counts on python-encoded beats [agreement test, not accuracy]: {conf}")
    for m in mism[:10]:
        dut._log.error(f"MISMATCH {m}")
    assert not mism, f"{len(mism)} RTL/Python mismatches"
