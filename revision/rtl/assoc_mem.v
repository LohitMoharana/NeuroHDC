`timescale 1ns / 1ps
// -----------------------------------------------------------------------------
// assoc_mem : Hamming-distance associative memory (REVISION-PREP, not part of
//             the submitted design).
//
// Compares a D-bit query hypervector with NUM_CLASSES stored binary prototypes:
//   dist[c] = popcount(query XOR proto[c])      (XOR array + popcount adder tree)
//   class   = argmin_c dist[c]                   (running minimum comparator)
// No multipliers: all addressing uses incrementing counters / constant shifts.
//
// Folded datapath (same style as top_shde_core): one CHUNK-bit XOR + popcount
// tree per cycle, prototypes streamed from a synchronous ROM (BRAM-inferable).
// Latency = NUM_CLASSES*(D/CHUNK) + 3 cycles after `start`.
//
// Tie-break: strict '<' comparison => lowest class index wins, identical to
// src/associative_mem.py (predict(): `if dist < min_distance`).
//
// Bit order: query[D-1] corresponds to the first character of a *.dat string
// (Verilog literal order). The prototype file must be chunked left-to-right
// into CHUNK-bit lines, class 0 first (see revision/tb/test_assoc_mem.py).
//
// `query` must be held stable from `start` until `done` (it is not latched,
// to avoid a 4096-bit register; top_shde_core keeps final_hv stable).
// -----------------------------------------------------------------------------
module assoc_mem #(
    parameter D           = 4096,
    parameter CHUNK       = 128,
    parameter NUM_CLASSES = 5,
    parameter PROTO_FILE  = "proto_chunks.dat",
    // derived (do not override)
    parameter DW          = $clog2(D + 1),
    parameter CW          = (NUM_CLASSES > 1) ? $clog2(NUM_CLASSES) : 1
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         start,
    input  wire [D-1:0]                 query,
    output reg                          busy,
    output reg                          done,        // 1-cycle pulse
    output reg  [CW-1:0]                class_idx,
    output reg  [DW-1:0]                min_dist
);
    localparam FOLDS = D / CHUNK;
    localparam DEPTH = NUM_CLASSES * FOLDS;
    localparam AW    = $clog2(DEPTH);
    localparam FW    = (FOLDS > 1) ? $clog2(FOLDS) : 1;

    (* ram_style = "block" *) reg [CHUNK-1:0] rom [0:DEPTH-1];
    initial $readmemb(PROTO_FILE, rom);

    // popcount adder tree (synthesis infers the tree from the sum)
    function [DW-1:0] popcount;
        input [CHUNK-1:0] v;
        integer i;
        begin
            popcount = 0;
            for (i = 0; i < CHUNK; i = i + 1)
                popcount = popcount + v[i];
        end
    endfunction

    // ---------------- stage 0: address / query-chunk fetch ----------------
    reg [AW-1:0] addr;
    reg [FW-1:0] fold;
    reg [CW-1:0] cls;
    // Aligned query chunks, selected by the fold counter (a CHUNK-wide FOLDS:1 mux).
    // (An unaligned variable part-select would synthesise a 4096-bit barrel shifter.)
    wire [CHUNK-1:0] qword [0:FOLDS-1];
    genvar gk;
    generate
        for (gk = 0; gk < FOLDS; gk = gk + 1) begin : q_words
            assign qword[gk] = query[D-1-gk*CHUNK -: CHUNK];   // constant slice
        end
    endgenerate
    reg          issuing;

    // ---------------- stage 1 registers (ROM data + query chunk) ----------
    reg [CHUNK-1:0] rom_q, qchunk_q;
    reg             v1, first1, lastc1, lastall1;
    reg [CW-1:0]    cls1;

    // ---------------- stage 2: xor/popcount/accumulate/compare ------------
    reg [DW-1:0] acc;
    reg [DW-1:0] best_dist;
    reg [CW-1:0] best_idx;
    reg          have_best;

    // ROM read in its own un-reset clocked block so the array can infer block RAM
    // (a BRAM output register cannot have an asynchronous reset).
    always @(posedge clk) begin
        if (issuing) rom_q <= rom[addr];
    end

    wire [DW-1:0] pc       = popcount(rom_q ^ qchunk_q);
    wire [DW-1:0] acc_next = (first1 ? {DW{1'b0}} : acc) + pc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 0; done <= 0; issuing <= 0;
            addr <= 0; fold <= 0; cls <= 0;
            v1 <= 0; first1 <= 0; lastc1 <= 0; lastall1 <= 0; cls1 <= 0;
            qchunk_q <= 0;
            acc <= 0; best_dist <= 0; best_idx <= 0; have_best <= 0;
            class_idx <= 0; min_dist <= 0;
        end else begin
            done <= 1'b0;
            v1   <= 1'b0;

            // ---- launch ----
            if (start && !busy) begin
                busy <= 1; issuing <= 1;
                addr <= 0; fold <= 0; cls <= 0;
                have_best <= 0;
            end

            // ---- stage 0 -> 1 : issue ROM read + select query chunk ----
            if (issuing) begin
                qchunk_q <= qword[fold];
                v1       <= 1'b1;
                first1   <= (fold == 0);
                lastc1   <= (fold == FOLDS-1);
                cls1     <= cls;
                lastall1 <= (fold == FOLDS-1) && (cls == NUM_CLASSES-1);

                addr <= addr + 1'b1;
                if (fold == FOLDS-1) begin
                    fold <= 0;
                    if (cls == NUM_CLASSES-1) issuing <= 1'b0;
                    else                      cls <= cls + 1'b1;
                end else begin
                    fold <= fold + 1'b1;
                end
            end

            // ---- stage 1 -> 2 : accumulate + running-min compare ----
            if (v1) begin
                acc <= acc_next;
                if (lastc1) begin
                    if (!have_best || acc_next < best_dist) begin
                        best_dist <= acc_next;
                        best_idx  <= cls1;
                        have_best <= 1'b1;
                    end
                end
                if (lastall1) begin
                    // publish result (compare of last class resolved here)
                    if (!have_best || acc_next < best_dist) begin
                        class_idx <= cls1;  min_dist <= acc_next;
                    end else begin
                        class_idx <= best_idx; min_dist <= best_dist;
                    end
                    done <= 1'b1;
                    busy <= 1'b0;
                end
            end
        end
    end
endmodule
