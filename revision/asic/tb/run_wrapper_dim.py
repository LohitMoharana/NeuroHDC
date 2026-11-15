import os, sys
N = int(sys.argv[1])
from pathlib import Path
from cocotb_tools.runner import get_runner, get_results
here = Path(__file__).resolve().parent
asic = here.parent
root = asic.parents[1]
build = here / f"build{N}"; build.mkdir(exist_ok=True)
os.environ.update(NEUROHDC_ROOT=str(root), NDIM=str(N))
os.environ["PYTHONPATH"] = os.pathsep.join([str(here), os.environ.get("PYTHONPATH", "")])
r = get_runner("icarus")
r.build(sources=[asic/"baseline_src/delta_tokenizer.v", asic/"baseline_src/hdc_bind_bundle.v", asic/"baseline_src/top_shde_core.v",
                 asic/"rtl"/f"proto_rom{N}.v", asic/"rtl"/f"assoc_mem_stream{N}.v", asic/"rtl"/f"top_shde_wrapper{N}_cls.v"],
        hdl_toplevel=f"top_shde_wrapper{N}_cls", build_dir=build, always=True)
xml = r.test(hdl_toplevel=f"top_shde_wrapper{N}_cls", test_module="test_wrapper_dim", build_dir=build, test_dir=build,
             results_xml=build/"results.xml")
p, f = get_results(xml)
print(f"RESULT: {p} passed, {f} failed"); sys.exit(1 if f else 0)
