"""Generate D=N variants (N=1024, 2048) of the 4096 wrapper + streaming AM + prototype ROM (CHUNK=128, FOLDS=N/128).
Everything except FOLDS/widths/module names is identical to the 4096 files. Usage: python gen_variant.py 1024 2048"""
import os, sys, re, subprocess
here = os.path.dirname(os.path.abspath(__file__)); rtl = os.path.join(here, "rtl")
for N in map(int, sys.argv[1:]):
    F = N // 128; dw = N.bit_length()          # $clog2(N+1) == N.bit_length() for a power of two N
    subprocess.check_call([sys.executable, os.path.join(here, "gen_proto_rom.py"), str(N), "128", f"proto_rom{N}"])
    am = open(os.path.join(rtl, "assoc_mem_stream4096.v")).read()
    am = am.replace("assoc_mem_stream4096", f"assoc_mem_stream{N}").replace("proto_rom4096", f"proto_rom{N}")
    am = am.replace("parameter FOLDS       = 32", f"parameter FOLDS       = {F}")
    open(os.path.join(rtl, f"assoc_mem_stream{N}.v"), "w").write(am)
    w = open(os.path.join(rtl, "top_shde_wrapper4096_cls.v")).read()
    w = w.replace("top_shde_wrapper4096_cls", f"top_shde_wrapper{N}_cls").replace("assoc_mem_stream4096", f"assoc_mem_stream{N}")
    w = w.replace("localparam integer FOLDS       = 32", f"localparam integer FOLDS       = {F}")
    w = w.replace("output wire [12:0]       min_dist", f"output wire [{dw-1}:0]       min_dist")
    w = w.replace("D = 128 x 32 = 4096", f"D = 128 x {F} = {N}").replace("32-chunk", f"{F}-chunk")
    open(os.path.join(rtl, f"top_shde_wrapper{N}_cls.v"), "w").write(w)
    print("generated", N, "folds", F, "min_dist bits", dw)
