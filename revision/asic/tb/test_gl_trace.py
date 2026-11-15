"""Port-level trace of the scaled classifier wrapper (RTL or gate-level netlist). Same stimulus as test_wrapper_cls.py but
uses ONLY top-level ports (no internal wires), so the identical test runs on RTL and on the synthesised sky130 netlist.
Writes every class_valid result and every hv_valid_out word to $TRACE_OUT (JSON) for an RTL-vs-gate comparison."""
import os, json, random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

N_WIN = int(os.environ.get("N_WIN", 12))
GAP = 25

@cocotb.test()
async def trace(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    # prime-then-reset prologue (identical to test_wrapper_cls.py: the baseline FIFO read pointer issue)
    dut.rst_n.value = 0; dut.valid_in.value = 0; dut.analog_in.value = 0
    for _ in range(4): await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    for t in range(256):
        dut.analog_in.value = 20000 if t % 2 else -20000
        dut.valid_in.value = 1
        await RisingEdge(dut.clk)
    dut.valid_in.value = 0
    for _ in range(600): await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    for _ in range(4): await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    cls, hv = [], []
    async def monitor():
        cyc = 0
        while True:
            await RisingEdge(dut.clk); cyc += 1
            if str(dut.class_valid.value) == "1":
                cls.append([cyc, str(dut.class_idx.value), str(dut.min_dist.value)])
            if str(dut.hv_valid_out.value) == "1":
                hv.append([cyc, str(dut.hv_data_out.value)])
    cocotb.start_soon(monitor())

    rng = random.Random(42)
    for w in range(N_WIN):
        amp = rng.choice([4000, 12000, 30000]); v = 0
        for t in range(32):
            v = max(-32768, min(32767, v + rng.randint(-amp, amp)))
            dut.analog_in.value = v; dut.valid_in.value = 1
            await RisingEdge(dut.clk)
            dut.valid_in.value = 0
            for _ in range(GAP): await RisingEdge(dut.clk)
    for _ in range(400): await RisingEdge(dut.clk)
    json.dump(dict(n_win=N_WIN, class_results=cls, hv_words=hv), open(os.environ["TRACE_OUT"], "w"))
    dut._log.info(f"class results {len(cls)}, hv words {len(hv)}")
    assert len(cls) == N_WIN
