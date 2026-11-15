"""Generate D=N (1024, 2048) copies of the FPGA wrapper (baseline) and the classifier top for Vivado scaling runs.
The submitted RTL is NOT modified: the core is already parameterised (D, WINDOW_SIZE, CHUNK, FOLDS), so only the two wrapper
files (which hard-code 4096) are re-generated here by text substitution. CHUNK=128, WINDOW_SIZE=256 stay as submitted.
Also writes vivado/proto_chunks_<N>.dat = first N/128 chunk lines of each of the 5 classes (first N bits of each prototype).
Usage: python gen_dim_rtl.py 1024 2048"""
import os, sys, re, math
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
base_w = open(os.path.join(root, "hw", "rtl", "top_shde_wrapper.v")).read()
base_c = open(os.path.join(here, "rtl", "top_shde_classifier.v")).read()
proto = [l.strip() for l in open(os.path.join(here, "vivado", "proto_chunks.dat")) if l.strip()]
assert len(proto) == 160
for N in map(int, sys.argv[1:]):
    F = N // 128; words = N // 32; mb = int(math.log2(words)); sa = int(math.log2(N)); dw = N.bit_length()
    def sub(t, name_old, name_new):
        t = t.replace(name_old, name_new)
        t = t.replace("[4095:0]", f"[{N-1}:0]").replace("4095 - i", f"{N-1} - i").replace("i < 4096", f"i < {N}")
        t = t.replace(".D(4096)", f".D({N})").replace(".FOLDS(32)", f".FOLDS({F})")
        t = t.replace("reg [6:0] mux_sel", f"reg [{mb-1}:0] mux_sel").replace("reg [6:0]    mux_sel", f"reg [{mb-1}:0]    mux_sel")
        t = t.replace("mux_sel == 7'd127", f"mux_sel == {mb}'d{words-1}")
        t = t.replace("wire [11:0] shift_amt = {mux_sel, 5'd0};", f"wire [{sa-1}:0] shift_amt = {{mux_sel, 5'd0}};")
        t = t.replace("[12:0]", f"[{dw-1}:0]")
        return t
    w = sub(base_w, "module top_shde_wrapper", f"module top_shde_wrapper_D{N}")
    c = sub(base_c, "module top_shde_classifier", f"module top_shde_classifier_D{N}")
    for pat in ("4096", "7'd127", "[11:0]", "[6:0]"):
        assert pat not in w.replace("4096-bit", "").replace("Instead of a power-hungry 4096-bit", "") or pat == "4096", (pat, "wrapper")
    open(os.path.join(here, "rtl", "dim", f"top_shde_wrapper_D{N}.v"), "w").write(w)
    open(os.path.join(here, "rtl", "dim", f"top_shde_classifier_D{N}.v"), "w").write(c)
    with open(os.path.join(here, "vivado", f"proto_chunks_{N}.dat"), "w") as f:
        for cls in range(5):
            for k in range(F): f.write(proto[cls * 32 + k] + "\n")
    print("generated", N, "folds", F, "mux bits", mb, "shift bits", sa, "dist bits", dw)
