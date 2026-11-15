`timescale 1ns / 1ps
// -----------------------------------------------------------------------------
// top_shde_classifier : REVISION-PREP top. top_shde_wrapper (unchanged logic:
// core + static-register MUX serialiser) plus the Hamming associative memory.
// The submitted RTL files are NOT modified; this file only instantiates them.
//
//   core -> final_hv/hv_ready -> static_hv_reg (latched once, as in the wrapper)
//                                   |-> 32-bit MUX serialiser -> hv_data_out/hv_valid_out (unchanged)
//                                   '-> assoc_mem -> class_idx / class_valid / min_dist
//
// static_hv_reg is stable from the cycle after hv_ready until the next heartbeat's
// hv_ready (>= 256 samples later), far longer than the associative-memory latency,
// so assoc_mem needs no extra 4096-bit query register.
//
// QUERY_REV: if 1, query bit i is taken from static_hv_reg bit (D-1-i). This is pure
// wiring (zero logic). It exists because assoc_mem uses "string char 0 = MSB" order;
// the value is fixed by revision/tb/test_top_classifier.py (see its report).
// -----------------------------------------------------------------------------
module top_shde_classifier_D2048 #(
    parameter QUERY_REV   = 0,
    parameter NUM_CLASSES = 5,
    parameter PROTO_FILE  = "proto_chunks.dat"
)(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire signed [15:0]   analog_in,
    input  wire                 valid_in,

    output wire [31:0]          hv_data_out,
    output wire                 hv_valid_out,

    output wire [2:0]           class_idx,
    output wire                 class_valid,   // 1-cycle pulse
    output wire [11:0]          min_dist
);
    wire [2047:0] internal_final_hv;
    wire          internal_hv_ready;

    top_shde_core #(.D(2048), .WINDOW_SIZE(256), .CHUNK(128), .FOLDS(16)) core_inst (
        .clk(clk), .rst_n(rst_n), .analog_in(analog_in), .valid_in(valid_in),
        .final_hv(internal_final_hv), .hv_ready(internal_hv_ready)
    );

    // ---- identical to top_shde_wrapper ----
    reg [2047:0] static_hv_reg;
    reg [5:0]    mux_sel;
    reg          is_transmitting;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            static_hv_reg <= 0; mux_sel <= 0; is_transmitting <= 1'b0;
        end else begin
            if (internal_hv_ready) begin
                static_hv_reg <= internal_final_hv; mux_sel <= 0; is_transmitting <= 1'b1;
            end else if (is_transmitting) begin
                if (mux_sel == 6'd63) is_transmitting <= 1'b0;
                else                   mux_sel <= mux_sel + 1'b1;
            end
        end
    end
    wire [10:0] shift_amt = {mux_sel, 5'd0};
    assign hv_data_out  = static_hv_reg >> shift_amt;
    assign hv_valid_out = is_transmitting;

    // ---- added: associative memory ----
    reg am_start;                      // static_hv_reg is valid one cycle after hv_ready
    always @(posedge clk or negedge rst_n)
        if (!rst_n) am_start <= 1'b0; else am_start <= internal_hv_ready;

    wire [2047:0] query;
    genvar i;
    generate
        for (i = 0; i < 2048; i = i + 1) begin : q_map
            assign query[i] = (QUERY_REV != 0) ? static_hv_reg[2047 - i] : static_hv_reg[i];
        end
    endgenerate

    wire am_busy;
    wire [2:0]  am_cls;
    wire [11:0] am_dist;
    assoc_mem #(.D(2048), .CHUNK(128), .NUM_CLASSES(NUM_CLASSES), .PROTO_FILE(PROTO_FILE)) am_inst (
        .clk(clk), .rst_n(rst_n), .start(am_start), .query(query),
        .busy(am_busy), .done(class_valid), .class_idx(am_cls), .min_dist(am_dist)
    );
    assign class_idx = am_cls;
    assign min_dist  = am_dist;
endmodule
