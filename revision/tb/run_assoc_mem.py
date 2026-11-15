"""Build + run the assoc_mem cocotb test with Icarus (cocotb 2.0 runner; no make needed).
Usage: python revision/tb/run_assoc_mem.py [datasets_dir]   (env AM_CHUNK, N_BEATS optional)"""
import os, sys
from pathlib import Path
from cocotb_tools.runner import get_runner

here = Path(__file__).resolve().parent
root = here.parents[1]
data = Path(sys.argv[1] if len(sys.argv) > 1 else root / "Datasets")
mem = root / "hw/vivado/NeuroHDC/NeuroHDC.ip_user_files/mem_init_files"
D, CHUNK = 4096, int(os.environ.get("AM_CHUNK", 128))
build = here / "build"
build.mkdir(exist_ok=True)

# chunk prototypes left->right into CHUNK-bit lines, class 0 first
with open(build / "proto_chunks.dat", "w") as f:
    for line in (l.strip() for l in open(mem / "prototypes.dat") if l.strip()):
        assert len(line) == D
        for i in range(0, D, CHUNK):
            f.write(line[i:i + CHUNK] + "\n")

os.environ.update(NEUROHDC_ROOT=str(root), NEUROHDC_DATA=str(data))
os.environ["PYTHONPATH"] = os.pathsep.join([str(here), os.environ.get("PYTHONPATH", "")])
r = get_runner("icarus")
r.build(sources=[root / "revision/rtl/assoc_mem.v"], hdl_toplevel="assoc_mem",
        build_dir=build, always=True,
        parameters={"D": D, "CHUNK": CHUNK, "NUM_CLASSES": 5})
xml = r.test(hdl_toplevel="assoc_mem", test_module="test_assoc_mem", build_dir=build,
             test_dir=build, results_xml=build / "results.xml")  # cwd: $readmemb path
from cocotb_tools.runner import get_results
passed, failed = get_results(xml)
print(f"RESULT: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
