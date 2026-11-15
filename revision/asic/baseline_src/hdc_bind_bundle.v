`timescale 1ns / 1ps

module hdc_bind_bundle #(
    parameter CHUNK = 32,
    parameter FOLDS = 8
)(
    input wire clk,
    input wire rst_n,

    input wire [1:0] spike_ch0,
    input wire [1:0] spike_ch1,
    input wire [1:0] spike_ch2,

    input wire valid_in,

    input wire [CHUNK-1:0] chunk_ch0,
    input wire [CHUNK-1:0] chunk_ch1,
    input wire [CHUNK-1:0] chunk_ch2,

    input wire [CHUNK-1:0] chunk_item_up,
    input wire [CHUNK-1:0] chunk_item_down,
    input wire [CHUNK-1:0] chunk_pos_t,

    input wire end_of_window,

    output wire bram_en,
    output wire ready_for_token,

    output reg [CHUNK-1:0] chunk_hv,
    output reg              chunk_hv_valid
);

    // ================================================================
    // FSM
    // ================================================================

    localparam IDLE      = 2'b00;
    localparam READ_WAIT = 2'b01;
    localparam BIND      = 2'b10;
    localparam EVAL      = 2'b11;

    reg [1:0] state;

    assign ready_for_token = (state == IDLE);

    reg [5:0] fetch_idx;
    reg [4:0] bind_idx;

    reg [1:0] l_sp0;
    reg [1:0] l_sp1;
    reg [1:0] l_sp2;
    reg       l_eow;

    // ================================================================
    // BRAM / binding activity
    // ================================================================

    assign bram_en =
        (state == READ_WAIT) ||
        (state == BIND);

    wire is_bind = (state == BIND);

    // ================================================================
    // Binding equations
    // ================================================================

    wire [CHUNK-1:0] bound_ch0 =
        (is_bind && l_sp0 == 2'b01) ?
            (chunk_ch0 ~^ chunk_item_up ~^ chunk_pos_t) :
        (is_bind && l_sp0 == 2'b10) ?
            (chunk_ch0 ~^ chunk_item_down ~^ chunk_pos_t) :
            {CHUNK{1'b0}};

    wire [CHUNK-1:0] bound_ch1 =
        (is_bind && l_sp1 == 2'b01) ?
            (chunk_ch1 ~^ chunk_item_up ~^ chunk_pos_t) :
        (is_bind && l_sp1 == 2'b10) ?
            (chunk_ch1 ~^ chunk_item_down ~^ chunk_pos_t) :
            {CHUNK{1'b0}};

    wire [CHUNK-1:0] bound_ch2 =
        (is_bind && l_sp2 == 2'b01) ?
            (chunk_ch2 ~^ chunk_item_up ~^ chunk_pos_t) :
        (is_bind && l_sp2 == 2'b10) ?
            (chunk_ch2 ~^ chunk_item_down ~^ chunk_pos_t) :
            {CHUNK{1'b0}};

    // ================================================================
    // Accumulator memory
    //
    // One accumulator entry per fold.
    //
    // Each entry contains CHUNK signed 8-bit accumulators.
    // ================================================================

    (* ram_style = "distributed" *)
    reg [CHUNK*8-1:0] accum_mem [0:FOLDS-1];

    wire [CHUNK*8-1:0] read_acc =
        accum_mem[bind_idx];

    integer r;

    initial begin

        for (r = 0; r < FOLDS; r = r + 1)
            accum_mem[r] = {CHUNK*8{1'b0}};

    end

    // ================================================================
    // Accumulator math
    // ================================================================

    wire signed [7:0] acc_val [0:CHUNK-1];

    wire [CHUNK*8-1:0] packed_next_acc;

    wire [CHUNK-1:0] eval_bits;

    genvar g;

    generate

        for (g = 0; g < CHUNK; g = g + 1) begin : acc_math

            assign acc_val[g] =
                read_acc[g*8 +: 8];

            wire signed [7:0] add0 =
                (is_bind && l_sp0 != 2'b00) ?
                    (bound_ch0[g] ? 8'sd1 : -8'sd1) :
                    8'sd0;

            wire signed [7:0] add1 =
                (is_bind && l_sp1 != 2'b00) ?
                    (bound_ch1[g] ? 8'sd1 : -8'sd1) :
                    8'sd0;

            wire signed [7:0] add2 =
                (is_bind && l_sp2 != 2'b00) ?
                    (bound_ch2[g] ? 8'sd1 : -8'sd1) :
                    8'sd0;

            assign packed_next_acc[g*8 +: 8] =
                acc_val[g] + add0 + add1 + add2;

            /*
             * IMPORTANT:
             *
             * eval_bits is derived from the accumulator value
             * currently selected by bind_idx.
             *
             * This value is captured into chunk_hv during EVAL.
             */

            assign eval_bits[g] =
                (acc_val[g] > 8'sd0) ? 1'b1 : 1'b0;

        end

    endgenerate

    // ================================================================
    // Accumulator write
    // ================================================================

    always @(posedge clk) begin

        if (state == BIND) begin

            accum_mem[bind_idx] <= packed_next_acc;

        end

        /*
         * DO NOT clear the accumulator during EVAL.
         *
         * Clearing during the same EVAL sequence that samples
         * eval_bits makes the output timing unnecessarily fragile.
         *
         * The accumulator is cleared when the corresponding EVAL
         * result has already been registered.
         */

        else if (state == EVAL) begin

            accum_mem[bind_idx] <=
                {CHUNK*8{1'b0}};

        end

    end

    // ================================================================
    // FSM
    // ================================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            state          <= IDLE;

            fetch_idx      <= 6'd0;
            bind_idx       <= 5'd0;

            l_sp0          <= 2'b00;
            l_sp1          <= 2'b00;
            l_sp2          <= 2'b00;
            l_eow          <= 1'b0;

            chunk_hv       <= {CHUNK{1'b0}};
            chunk_hv_valid <= 1'b0;

        end

        else begin

            /*
             * chunk_hv_valid is a one-cycle pulse.
             */

            chunk_hv_valid <= 1'b0;

            case (state)

                // ====================================================
                // IDLE
                // ====================================================

                IDLE: begin

                    if (valid_in) begin

                        l_sp0 <= spike_ch0;
                        l_sp1 <= spike_ch1;
                        l_sp2 <= spike_ch2;
                        l_eow <= end_of_window;

                        /*
                         * Zero-token:
                         *
                         * Nothing needs to be accumulated.
                         *
                         * However, if this is the EOW token, the
                         * complete window is now ready for evaluation.
                         */

                        if (
                            spike_ch0 == 2'b00 &&
                            spike_ch1 == 2'b00 &&
                            spike_ch2 == 2'b00
                        ) begin

                            if (end_of_window) begin

                                bind_idx <= 5'd0;
                                state    <= EVAL;

                            end

                        end

                        /*
                         * Active token:
                         *
                         * First perform the reference-vector read
                         * phase, then bind across all folds.
                         */

                        else begin

                            fetch_idx <= 6'd1;
                            state     <= READ_WAIT;

                        end

                    end

                end


                // ====================================================
                // READ_WAIT
                // ====================================================

                READ_WAIT: begin

                    /*
                     * One explicit wait state models the reference
                     * memory read latency.
                     */

                    fetch_idx <= fetch_idx + 6'd1;
                    bind_idx  <= 5'd0;

                    state <= BIND;

                end


                // ====================================================
                // BIND
                // ====================================================

                BIND: begin

                    /*
                     * One fold is processed per clock.
                     */

                    if (fetch_idx < FOLDS)
                        fetch_idx <= fetch_idx + 6'd1;

                    if (bind_idx == FOLDS - 1) begin

                        /*
                         * This token has now been completely consumed.
                         *
                         * Only the token carrying EOW can transition
                         * the binder into EVAL.
                         */

                        if (l_eow) begin

                            bind_idx <= 5'd0;
                            state    <= EVAL;

                        end

                        else begin

                            state <= IDLE;

                        end

                    end

                    else begin

                        bind_idx <= bind_idx + 5'd1;

                    end

                end


                // ====================================================
                // EVAL
                // ====================================================

                EVAL: begin

                    /*
                     * Capture the sign decision of the selected
                     * accumulator fold.
                     */

                    chunk_hv       <= eval_bits;
                    chunk_hv_valid <= 1'b1;

                    /*
                     * The accumulator selected by bind_idx is cleared
                     * only after its value has been sampled above.
                     */

                    if (bind_idx == FOLDS - 1) begin

                        /*
                         * Final fold.
                         *
                         * Next cycle the binder becomes available
                         * for the next window.
                         */

                        state <= IDLE;

                    end

                    else begin

                        bind_idx <= bind_idx + 5'd1;

                    end

                end


                default: begin

                    state <= IDLE;

                end

            endcase

        end

    end

endmodule
