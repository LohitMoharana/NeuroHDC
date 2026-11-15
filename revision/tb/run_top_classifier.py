"""Build + run test_top_classifier with Icarus. Usage: python revision/tb/run_top_classifier.py [QUERY_REV 0|1]"""
import os, sys
from pathlib import Path
from cocotb_tools.runner import get_runner, get_results

here = Path(__file__).resolve().parent
root = here.parents[1]
rev = int(sys.argv[1]) if len(sys.argv) > 1 else 0
mem = root / "hw/vivado/NeuroHDC/NeuroHDC.ip_user_files/mem_init_files"
build = here / f"build_top_rev{rev}"
build.mkdir(exist_ok=True)
CHUNK, D = 128, 4096
with open(build / "proto_chunks.dat", "w") as f:
    for line in (l.strip() for l in open(mem / "prototypes.dat") if l.strip()):
        for i in range(0, D, CHUNK):
            f.write(line[i:i + CHUNK] + "\n")
os.environ.update(NEUROHDC_ROOT=str(root), QUERY_REV=str(rev))
os.environ["PYTHONPATH"] = os.pathsep.join([str(here), os.environ.get("PYTHONPATH", "")])
r = get_runner("icarus")
r.build(sources=[root / "hw/rtl/delta_tokenizer.v", root / "hw/rtl/hdc_bind_bundle.v", root / "hw/rtl/top_shde_core.v",
                 root / "revision/rtl/assoc_mem.v", root / "revision/rtl/top_shde_classifier.v"],
        hdl_toplevel="top_shde_classifier", build_dir=build, always=True,
        parameters={"QUERY_REV": rev})
xml = r.test(hdl_toplevel="top_shde_classifier", test_module="test_top_classifier",
             build_dir=build, test_dir=build, results_xml=build / "results.xml")
passed, failed = get_results(xml)
print(f"RESULT QUERY_REV={rev}: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
