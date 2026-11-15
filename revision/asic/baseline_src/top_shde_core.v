`timescale 1ns / 1ps

module top_shde_core #(
    parameter WINDOW_SIZE = 32,
    parameter CHUNK       = 32,
    parameter FOLDS       = 8,
    parameter FIFO_DEPTH  = 32
)(
    input wire clk,
    input wire rst_n,

    input wire signed [15:0] analog_in,
    input wire               valid_in,

    output wire [CHUNK-1:0] chunk_hv,
    output wire             chunk_hv_valid,

    output wire             debug_fifo_push,
    output wire             debug_fifo_pop,
    output wire [7:0]       debug_fifo_count
);

    // ================================================================
    // FIFO POINTER WIDTH
    // ================================================================

    localparam integer FIFO_PTR_W =
        (FIFO_DEPTH <= 2) ? 1 : $clog2(FIFO_DEPTH);

    // ================================================================
    // TOKENIZER
    // ================================================================

    wire [1:0] spike_ch0;
    wire [1:0] spike_ch1;
    wire [1:0] spike_ch2;

    wire tok_valid_out;

    delta_tokenizer tok_inst (

        .clk        (clk),
        .rst_n      (rst_n),
        .analog_in  (analog_in),
        .valid_in   (valid_in),

        .spike_ch0  (spike_ch0),
        .spike_ch1  (spike_ch1),
        .spike_ch2  (spike_ch2),

        .valid_out  (tok_valid_out)

    );

    // ================================================================
    // WINDOW COUNTER
    // ================================================================

    reg [7:0] t_counter;

    wire end_of_window =
        (t_counter == WINDOW_SIZE - 1) &&
        tok_valid_out;

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            t_counter <= 8'd0;

        end

        else if (tok_valid_out) begin

            if (t_counter == WINDOW_SIZE - 1)
                t_counter <= 8'd0;

            else
                t_counter <= t_counter + 8'd1;

        end

    end

    // ================================================================
    // TOKEN ACTIVITY
    // ================================================================

    wire token_is_active =
        (spike_ch0 != 2'b00) ||
        (spike_ch1 != 2'b00) ||
        (spike_ch2 != 2'b00);

    // ================================================================
    // REFERENCE VECTOR STORAGE
    //
    // These remain the deterministic prototype/reference vectors
    // already used by the existing architecture.
    // ================================================================

    wire core_bram_en;

    reg [CHUNK-1:0] stub_ch0;
    reg [CHUNK-1:0] stub_ch1;
    reg [CHUNK-1:0] stub_ch2;

    reg [CHUNK-1:0] stub_up;
    reg [CHUNK-1:0] stub_dn;
    reg [CHUNK-1:0] stub_pos;

    /*
     * Keep deterministic values for the ASIC prototype.
     *
     * These values are deliberately initialized rather than left
     * unknown, allowing functional verification to remain
     * reproducible in RTL simulation.
     */

    integer s;

    initial begin

        stub_ch0 = {CHUNK{1'b0}};
        stub_ch1 = {CHUNK{1'b0}};
        stub_ch2 = {CHUNK{1'b0}};

        stub_up  = {CHUNK{1'b0}};
        stub_dn  = {CHUNK{1'b0}};
        stub_pos = {CHUNK{1'b0}};

        /*
         * Deterministic reference patterns.
         *
         * The exact reference-vector generation can later be replaced
         * by the BRAM implementation without changing the FIFO/binder
         * control protocol.
         */

        for (s = 0; s < CHUNK; s = s + 1) begin

            stub_ch0[s] = (s % 2);
            stub_ch1[s] = ((s / 2) % 2);
            stub_ch2[s] = ((s / 4) % 2);

            stub_up[s]  = ((s % 3) == 0);
            stub_dn[s]  = ((s % 5) == 0);
            stub_pos[s] = ((s % 7) == 0);

        end

    end

    // ================================================================
    // TOKEN FIFO
    //
    // IMPORTANT:
    //
    // The original prototype used a 16-entry FIFO while the binder
    // takes substantially more than one clock per token.
    //
    // A 32-entry FIFO is required to absorb one complete 32-sample
    // window without dropping tokens.
    // ================================================================

    reg [1:0] fifo_sp0 [0:FIFO_DEPTH-1];
    reg [1:0] fifo_sp1 [0:FIFO_DEPTH-1];
    reg [1:0] fifo_sp2 [0:FIFO_DEPTH-1];

    reg fifo_eow [0:FIFO_DEPTH-1];

    reg [CHUNK-1:0] fifo_ch0 [0:FIFO_DEPTH-1];
    reg [CHUNK-1:0] fifo_ch1 [0:FIFO_DEPTH-1];
    reg [CHUNK-1:0] fifo_ch2 [0:FIFO_DEPTH-1];

    reg [CHUNK-1:0] fifo_up  [0:FIFO_DEPTH-1];
    reg [CHUNK-1:0] fifo_dn  [0:FIFO_DEPTH-1];
    reg [CHUNK-1:0] fifo_pos [0:FIFO_DEPTH-1];

    reg [FIFO_PTR_W-1:0] fifo_wr_ptr;
    reg [FIFO_PTR_W-1:0] fifo_rd_ptr;

    reg [FIFO_PTR_W:0] fifo_count;

    wire fifo_empty =
        (fifo_count == 0);

    wire fifo_full =
        (fifo_count == FIFO_DEPTH);

    // ================================================================
    // BINDER INTERFACE
    // ================================================================

    wire binder_ready_for_token;

    wire fifo_push;
    wire fifo_pop;

    /*
     * Every tokenizer event is preserved.
     *
     * Zero-spike events are intentionally stored because the final
     * tokenizer event carries end_of_window.
     */

    assign fifo_push =
        tok_valid_out &&
        !fifo_full;

    /*
     * The binder consumes one token only while IDLE.
     */

    assign fifo_pop =
        !fifo_empty &&
        binder_ready_for_token;

    // ================================================================
    // FIFO OUTPUT
    // ================================================================

    wire [1:0] binder_sp0 =
        fifo_sp0[fifo_rd_ptr];

    wire [1:0] binder_sp1 =
        fifo_sp1[fifo_rd_ptr];

    wire [1:0] binder_sp2 =
        fifo_sp2[fifo_rd_ptr];

    wire binder_eow =
        fifo_eow[fifo_rd_ptr];

    wire [CHUNK-1:0] binder_ch0 =
        fifo_ch0[fifo_rd_ptr];

    wire [CHUNK-1:0] binder_ch1 =
        fifo_ch1[fifo_rd_ptr];

    wire [CHUNK-1:0] binder_ch2 =
        fifo_ch2[fifo_rd_ptr];

    wire [CHUNK-1:0] binder_up =
        fifo_up[fifo_rd_ptr];

    wire [CHUNK-1:0] binder_dn =
        fifo_dn[fifo_rd_ptr];

    wire [CHUNK-1:0] binder_pos =
        fifo_pos[fifo_rd_ptr];

    // ================================================================
    // FIFO WRITE
    // ================================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            fifo_wr_ptr <= 0;

        end

        else if (fifo_push) begin

            fifo_sp0[fifo_wr_ptr] <= spike_ch0;
            fifo_sp1[fifo_wr_ptr] <= spike_ch1;
            fifo_sp2[fifo_wr_ptr] <= spike_ch2;

            fifo_eow[fifo_wr_ptr] <= end_of_window;

            fifo_ch0[fifo_wr_ptr] <= stub_ch0;
            fifo_ch1[fifo_wr_ptr] <= stub_ch1;
            fifo_ch2[fifo_wr_ptr] <= stub_ch2;

            fifo_up[fifo_wr_ptr] <= stub_up;
            fifo_dn[fifo_wr_ptr] <= stub_dn;
            fifo_pos[fifo_wr_ptr] <= stub_pos;

            if (fifo_wr_ptr == FIFO_DEPTH - 1)
                fifo_wr_ptr <= 0;

            else
                fifo_wr_ptr <= fifo_wr_ptr + 1'b1;

        end

    end

    // ================================================================
    // FIFO READ POINTER
    // ================================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            fifo_rd_ptr <= 0;

        end

        else if (fifo_pop) begin

            if (fifo_rd_ptr == FIFO_DEPTH - 1)
                fifo_rd_ptr <= 0;

            else
                fifo_rd_ptr <= fifo_rd_ptr + 1'b1;

        end

    end

    // ================================================================
    // FIFO COUNT
    //
    // Correctly handles simultaneous push/pop.
    // ================================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            fifo_count <= 0;

        end

        else begin

            case ({fifo_push, fifo_pop})

                2'b10:
                    fifo_count <= fifo_count + 1'b1;

                2'b01:
                    fifo_count <= fifo_count - 1'b1;

                default:
                    fifo_count <= fifo_count;

            endcase

        end

    end

    // ================================================================
    // DEBUG SIGNALS
    // ================================================================

    assign debug_fifo_push =
        fifo_push;

    assign debug_fifo_pop =
        fifo_pop;

    assign debug_fifo_count =
        {{(8-(FIFO_PTR_W+1)){1'b0}}, fifo_count};

    // ================================================================
    // HDC BINDER
    // ================================================================

    hdc_bind_bundle #(
        .CHUNK(CHUNK),
        .FOLDS(FOLDS)
    ) hdc_core_inst (

        .clk(clk),
        .rst_n(rst_n),

        .spike_ch0(binder_sp0),
        .spike_ch1(binder_sp1),
        .spike_ch2(binder_sp2),

        .valid_in(fifo_pop),

        .chunk_ch0(binder_ch0),
        .chunk_ch1(binder_ch1),
        .chunk_ch2(binder_ch2),

        .chunk_item_up(binder_up),
        .chunk_item_down(binder_dn),
        .chunk_pos_t(binder_pos),

        .end_of_window(binder_eow),

        .bram_en(core_bram_en),

        .ready_for_token(binder_ready_for_token),

        .chunk_hv(chunk_hv),
        .chunk_hv_valid(chunk_hv_valid)

    );

endmodule
