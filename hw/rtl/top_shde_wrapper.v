`timescale 1ns / 1ps

module top_shde_wrapper (
    input wire clk,
    input wire rst_n,
    input wire signed [15:0] analog_in,
    input wire valid_in,

    output wire [31:0] hv_data_out,
    output wire hv_valid_out
);

    wire [4095:0] internal_final_hv;
    wire internal_hv_ready;

    top_shde_core #(
        .D(4096),
        .WINDOW_SIZE(256),
        .CHUNK(128),
        .FOLDS(32)
    ) core_inst (
        .clk(clk),
        .rst_n(rst_n),
        .analog_in(analog_in),
        .valid_in(valid_in),
        .final_hv(internal_final_hv),
        .hv_ready(internal_hv_ready)
    );

    // --- POWER OPTIMIZATION: Static MUX Serialization ---
    // Instead of a power-hungry 4096-bit shift register, we hold the register
    // completely static and sweep a MUX across it. Zero Flip-Flop toggling!
    reg [4095:0] static_hv_reg;
    reg [6:0] mux_sel;
    reg is_transmitting;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            static_hv_reg <= 0;
            mux_sel <= 0;
            is_transmitting <= 1'b0;
        end else begin
            if (internal_hv_ready) begin
                // Latch the massive hypervector ONCE.
                // The FFs will not toggle again until the next heartbeat!
                static_hv_reg <= internal_final_hv;
                mux_sel <= 0;
                is_transmitting <= 1'b1;
            end else if (is_transmitting) begin
                if (mux_sel == 7'd127) begin
                    is_transmitting <= 1'b0;
                end else begin
                    mux_sel <= mux_sel + 1'b1;
                end
            end
        end
    end

    // Dynamically select the 32-bit chunk without shifting
    wire [11:0] shift_amt = {mux_sel, 5'd0}; // mux_sel * 32
    assign hv_data_out = static_hv_reg >> shift_amt;
    assign hv_valid_out = is_transmitting;

endmodule