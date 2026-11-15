`timescale 1ns / 1ps
// -----------------------------------------------------------------------------
// assoc_mem_stream2048 : streaming Hamming associative memory for the scaled ASIC
// prototype (REVISION-PREP; separate from the submitted RTL).
// The HDC core emits one hypervector as FOLDS chunks of CHUNK bits (chunk_hv /
// chunk_hv_valid). For every chunk, each class accumulates
//     dist[c] += popcount(chunk XOR proto[c][k])        (XOR + popcount adder tree)
// and after the last chunk the minimum-distance class is selected (strict '<' =>
// lowest index wins ties, same as src/associative_mem.py). No multipliers, no query
// register, no memory macros: prototypes are a combinational constant ROM.
// -----------------------------------------------------------------------------
module assoc_mem_stream2048 #(
    parameter CHUNK       = 128,
    parameter FOLDS       = 16,
    parameter NUM_CLASSES = 5,
    parameter DW          = $clog2(CHUNK*FOLDS + 1),
    parameter KW          = $clog2(FOLDS)
)(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire [CHUNK-1:0]     chunk,
    input  wire                 chunk_valid,
    output reg  [2:0]           class_idx,
    output reg  [DW-1:0]        min_dist,
    output reg                  class_valid     // 1-cycle pulse, after the last chunk
);
    reg [KW-1:0] k;
    reg          cmp_pending;
    reg [DW-1:0] acc [0:NUM_CLASSES-1];

    wire [NUM_CLASSES*CHUNK-1:0] words;
    proto_rom2048 rom_i (.k(k), .words(words));

    function [DW-1:0] popcount;
        input [CHUNK-1:0] v;
        integer i;
        begin
            popcount = 0;
            for (i = 0; i < CHUNK; i = i + 1) popcount = popcount + v[i];
        end
    endfunction

    wire [DW-1:0] acc_next [0:NUM_CLASSES-1];
    genvar c;
    generate
        for (c = 0; c < NUM_CLASSES; c = c + 1) begin : cls
            assign acc_next[c] = ((k == 0) ? {DW{1'b0}} : acc[c])
                               + popcount(chunk ^ words[c*CHUNK +: CHUNK]);
        end
    endgenerate

    integer j;
    reg [DW-1:0] best_d;
    reg [2:0]    best_i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            k <= 0; cmp_pending <= 1'b0; class_valid <= 1'b0;
            class_idx <= 0; min_dist <= 0;
            for (j = 0; j < NUM_CLASSES; j = j + 1) acc[j] <= 0;
        end else begin
            class_valid <= 1'b0;
            if (chunk_valid) begin
                for (j = 0; j < NUM_CLASSES; j = j + 1) acc[j] <= acc_next[j];
                if (k == FOLDS-1) begin k <= 0; cmp_pending <= 1'b1; end
                else              k <= k + 1'b1;
            end
            if (cmp_pending) begin           // one cycle after the last chunk: acc[] holds final distances
                best_d = acc[0]; best_i = 3'd0;
                for (j = 1; j < NUM_CLASSES; j = j + 1)
                    if (acc[j] < best_d) begin best_d = acc[j]; best_i = j[2:0]; end
                class_idx <= best_i; min_dist <= best_d;
                class_valid <= 1'b1; cmp_pending <= 1'b0;
            end
        end
    end
endmodule
