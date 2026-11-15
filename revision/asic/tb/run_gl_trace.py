"""usage: python run_gl_trace.py <rtl|gl> <out.json> [gl_dir]  (gl_dir holds top_shde_wrapper_cls.nl.v, sky130_fd_sc_hd.v, primitives.v)"""
import os, sys
from pathlib import Path
from cocotb_tools.runner import get_runner, get_results
mode, out = sys.argv[1], str(Path(sys.argv[2]).resolve())
here = Path(__file__).resolve().parent; asic = here.parent
build = here / f"build_{mode}"; build.mkdir(exist_ok=True)
os.environ["TRACE_OUT"] = out
os.environ["PYTHONPATH"] = os.pathsep.join([str(here), os.environ.get("PYTHONPATH", "")])
r = get_runner("icarus")
if mode == "rtl":
    srcs = [asic/"baseline_src/delta_tokenizer.v", asic/"baseline_src/hdc_bind_bundle.v", asic/"baseline_src/top_shde_core.v",
            asic/"rtl/proto_rom256.v", asic/"rtl/assoc_mem_stream.v", asic/"rtl/top_shde_wrapper_cls.v"]
    args = []
else:
    g = Path(sys.argv[3])
    srcs = [g/"primitives.v", g/"sky130_fd_sc_hd.v", g/"top_shde_wrapper_cls.nl.v"]
    args = ["-DFUNCTIONAL", "-DUNIT_DELAY=#0", "-DNO_PRIMITIVES_TIMING"]
r.build(sources=srcs, hdl_toplevel="top_shde_wrapper_cls", build_dir=build, always=True, build_args=args)
xml = r.test(hdl_toplevel="top_shde_wrapper_cls", test_module="test_gl_trace", build_dir=build, test_dir=build, results_xml=build/"results.xml")
p, f = get_results(xml); print(f"RESULT {mode}: {p} passed, {f} failed"); sys.exit(1 if f else 0)
