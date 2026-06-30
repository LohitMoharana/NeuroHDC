`timescale 1ns / 1ps

module hdc_bind_bundle #(
    parameter D = 4096,
    parameter CHUNK = 128,
    parameter FOLDS = 32
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

    output reg [4:0] rom_addr_out,
    output wire bram_en, // POWER OPTIMIZATION: Export BRAM sleep signal
    output reg [D-1:0] final_hv,
    output reg hv_ready
);

    localparam IDLE = 2'b00;
    localparam READ_WAIT = 2'b01;
    localparam BIND = 2'b10;
    localparam EVAL = 2'b11;

    reg [1:0] state;
    reg [5:0] fetch_idx;
    reg [4:0] bind_idx;
    reg [1:0] l_sp0, l_sp1, l_sp2;
    reg l_eow;

    // Wake BRAM up slightly before and during the BIND math
    assign bram_en = (state == READ_WAIT) || (state == BIND);
    wire is_bind = (state == BIND);

    // POWER OPTIMIZATION: By adding "is_bind", these XOR trees output pure 0s
    // during IDLE, preventing downstream adders from toggling randomly.
    wire [CHUNK-1:0] bound_ch0 = (is_bind && l_sp0 == 2'b01) ? (chunk_ch0 ~^ chunk_item_up ~^ chunk_pos_t) :
                                 (is_bind && l_sp0 == 2'b10) ? (chunk_ch0 ~^ chunk_item_down ~^ chunk_pos_t) : {CHUNK{1'b0}};

    wire [CHUNK-1:0] bound_ch1 = (is_bind && l_sp1 == 2'b01) ? (chunk_ch1 ~^ chunk_item_up ~^ chunk_pos_t) :
                                 (is_bind && l_sp1 == 2'b10) ? (chunk_ch1 ~^ chunk_item_down ~^ chunk_pos_t) : {CHUNK{1'b0}};

    wire [CHUNK-1:0] bound_ch2 = (is_bind && l_sp2 == 2'b01) ? (chunk_ch2 ~^ chunk_item_up ~^ chunk_pos_t) :
                                 (is_bind && l_sp2 == 2'b10) ? (chunk_ch2 ~^ chunk_item_down ~^ chunk_pos_t) : {CHUNK{1'b0}};

    (* ram_style = "distributed" *) reg [CHUNK*8-1:0] accum_mem [0:FOLDS-1];
    wire [CHUNK*8-1:0] read_acc = accum_mem[bind_idx];

    integer r;
    initial begin
        for (r = 0; r < FOLDS; r = r + 1) accum_mem[r] = 0;
    end

    wire signed [7:0] acc_val [0:CHUNK-1];
    wire [CHUNK*8-1:0] packed_next_acc;
    wire [CHUNK-1:0] eval_bits;

    genvar g;
    generate
        for (g = 0; g < CHUNK; g = g + 1) begin : acc_math
            assign acc_val[g] = read_acc[g*8 +: 8];

            // POWER OPTIMIZATION: Force adders to 0 during IDLE.
            // This prevents 128 adder circuits from constantly firing.
            wire signed [7:0] add0 = (is_bind && l_sp0 != 2'b00) ? (bound_ch0[g] ? 8'sd1 : -8'sd1) : 8'sd0;
            wire signed [7:0] add1 = (is_bind && l_sp1 != 2'b00) ? (bound_ch1[g] ? 8'sd1 : -8'sd1) : 8'sd0;
            wire signed [7:0] add2 = (is_bind && l_sp2 != 2'b00) ? (bound_ch2[g] ? 8'sd1 : -8'sd1) : 8'sd0;

            wire signed [7:0] sum = acc_val[g] + add0 + add1 + add2;
            assign packed_next_acc[g*8 +: 8] = sum;
            assign eval_bits[g] = (acc_val[g] > 8'sd0) ? 1'b1 : 1'b0;
        end
    endgenerate

    always @(posedge clk) begin
        if (state == BIND) begin
            accum_mem[bind_idx] <= packed_next_acc;
        end else if (state == EVAL) begin
            accum_mem[bind_idx] <= {CHUNK*8{1'b0}};
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            fetch_idx <= 0;
            bind_idx <= 0;
            rom_addr_out <= 0;
            hv_ready <= 1'b0;
            final_hv <= 0;
        end else begin
            hv_ready <= 1'b0;

            case (state)
                IDLE: begin
                    if (valid_in) begin
                        l_sp0 <= spike_ch0;
                        l_sp1 <= spike_ch1;
                        l_sp2 <= spike_ch2;
                        l_eow <= end_of_window;

                        if (spike_ch0 == 2'b00 && spike_ch1 == 2'b00 && spike_ch2 == 2'b00) begin
                            if (end_of_window) begin
                                state <= EVAL;
                                bind_idx <= 0;
                            end
                        end else begin
                            state <= READ_WAIT;
                            rom_addr_out <= 0;
                            fetch_idx <= 1;
                        end
                    end
                end

                READ_WAIT: begin
                    rom_addr_out <= fetch_idx[4:0];
                    fetch_idx <= fetch_idx + 1;
                    bind_idx <= 0;
                    state <= BIND;
                end

                BIND: begin
                    if (fetch_idx < FOLDS) begin
                        rom_addr_out <= fetch_idx[4:0];
                        fetch_idx <= fetch_idx + 1;
                    end

                    if (bind_idx == FOLDS - 1) begin
                        if (l_eow) begin
                            state <= EVAL;
                            bind_idx <= 0;
                        end else begin
                            state <= IDLE;
                        end
                    end else begin
                        bind_idx <= bind_idx + 1;
                    end
                end

                EVAL: begin
                    final_hv <= { eval_bits, final_hv[D-1:CHUNK] };

                    if (bind_idx == FOLDS - 1) begin
                        hv_ready <= 1'b1;
                        state <= IDLE;
                    end else begin
                        bind_idx <= bind_idx + 1;
                    end
                end
            endcase
        end
    end
endmodule