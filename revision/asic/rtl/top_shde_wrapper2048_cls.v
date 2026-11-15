`timescale 1ns / 1ps
// -----------------------------------------------------------------------------
// top_shde_wrapper2048_cls : FULL-SIZE (D = 128 x 16 = 2048, 256-sample window) version of the
// ASIC prototype wrapper + streaming associative memory. REVISION-PREP, no memory macros.
// Same prototype core/binder RTL as the 256-bit ASIC run (stub constant vectors, token FIFO),
// only parameters change. The chunk FIFO holds the full 16-chunk hypervector (as the FPGA wrapper's
// static register does) and a 4-word serialiser drains it as 32-bit words.
// -----------------------------------------------------------------------------
module top_shde_wrapper2048_cls (
    input  wire              clk,
    input  wire              rst_n,
    input  wire signed [15:0] analog_in,
    input  wire              valid_in,
    output wire [31:0]       hv_data_out,
    output wire              hv_valid_out,
    output wire [2:0]        class_idx,
    output wire [11:0]       min_dist,
    output wire              class_valid
);
    localparam integer WINDOW_SIZE = 256;
    localparam integer CHUNK       = 128;
    localparam integer FOLDS       = 16;
    localparam integer WORDS       = CHUNK / 32;
    localparam integer FIFO_PTR_W  = $clog2(FOLDS);

    wire [CHUNK-1:0] internal_chunk_hv;
    wire             internal_chunk_valid;
    wire             dbg_push, dbg_pop;
    wire [7:0]       dbg_cnt;

    top_shde_core #(.WINDOW_SIZE(WINDOW_SIZE), .CHUNK(CHUNK), .FOLDS(FOLDS), .FIFO_DEPTH(16)) core_inst (
        .clk(clk), .rst_n(rst_n), .analog_in(analog_in), .valid_in(valid_in),
        .chunk_hv(internal_chunk_hv), .chunk_hv_valid(internal_chunk_valid),
        .debug_fifo_push(dbg_push), .debug_fifo_pop(dbg_pop), .debug_fifo_count(dbg_cnt)
    );

    reg [CHUNK-1:0] chunk_fifo [0:FOLDS-1];
    reg [FIFO_PTR_W-1:0] wr_ptr, rd_ptr;
    reg [FIFO_PTR_W:0]   count;
    reg [CHUNK-1:0]      ser_reg;
    reg [1:0]            word_cnt;
    reg                  streaming;

    wire do_push = internal_chunk_valid && (count < FOLDS);
    wire do_pop  = !streaming && (count != 0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0; rd_ptr <= 0; count <= 0; ser_reg <= 0; word_cnt <= 0; streaming <= 1'b0;
        end else begin
            if (do_push) begin
                chunk_fifo[wr_ptr] <= internal_chunk_hv;
                wr_ptr <= (wr_ptr == FOLDS-1) ? 0 : wr_ptr + 1'b1;
            end
            if (do_pop) begin
                ser_reg <= chunk_fifo[rd_ptr];
                rd_ptr  <= (rd_ptr == FOLDS-1) ? 0 : rd_ptr + 1'b1;
                streaming <= 1'b1; word_cnt <= 0;
            end else if (streaming) begin
                if (word_cnt == WORDS-1) streaming <= 1'b0;
                else                     word_cnt <= word_cnt + 1'b1;
            end
            case ({do_push, do_pop})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end

    assign hv_data_out  = ser_reg[word_cnt*32 +: 32];
    assign hv_valid_out = streaming;

    assoc_mem_stream2048 #(.CHUNK(CHUNK), .FOLDS(FOLDS), .NUM_CLASSES(5)) am_inst (
        .clk(clk), .rst_n(rst_n), .chunk(internal_chunk_hv), .chunk_valid(internal_chunk_valid),
        .class_idx(class_idx), .min_dist(min_dist), .class_valid(class_valid)
    );
endmodule
