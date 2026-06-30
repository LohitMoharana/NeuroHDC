`timescale 1ns / 1ps

module delta_tokenizer #(
    // Hardware Thresholds mapped to 16-bit signed integers
    parameter THRESH_0 = 16'sd1638,  // ~0.05
    parameter THRESH_1 = 16'sd8192,  // ~0.25
    parameter THRESH_2 = 16'sd19660  // ~0.60
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire signed [15:0] analog_in,
    input  wire        valid_in,

    // Output Spike Channels: 2-bit wire (00=Flat, 01=Up Spike, 10=Down Spike)
    output reg  [1:0]  spike_ch0,
    output reg  [1:0]  spike_ch1,
    output reg  [1:0]  spike_ch2,
    output reg         valid_out
);

    reg signed [15:0] prev_analog;
    reg first_valid;

    // Hardware Subtraction (The Delta)
    wire signed [16:0] delta = analog_in - prev_analog;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prev_analog <= 16'd0;
            first_valid <= 1'b1;
            spike_ch0   <= 2'b00;
            spike_ch1   <= 2'b00;
            spike_ch2   <= 2'b00;
            valid_out   <= 1'b0;
        end else if (valid_in) begin
            // Shift the register
            prev_analog <= analog_in;
            valid_out   <= 1'b1;

            if (first_valid) begin
                // Suppress the phantom spike on the very first sample
                first_valid <= 1'b0;
                spike_ch0 <= 2'b00;
                spike_ch1 <= 2'b00;
                spike_ch2 <= 2'b00;
            end else begin
                // Channel 0 (P-Wave / Low Threshold)
                if (delta >= THRESH_0)       spike_ch0 <= 2'b01; // +1
                else if (delta <= -THRESH_0) spike_ch0 <= 2'b10; // -1
                else                         spike_ch0 <= 2'b00; // 0

                // Channel 1 (QRS Complex / Mid Threshold)
                if (delta >= THRESH_1)       spike_ch1 <= 2'b01; // +1
                else if (delta <= -THRESH_1) spike_ch1 <= 2'b10; // -1
                else                         spike_ch1 <= 2'b00; // 0

                // Channel 2 (Sharp Peak / High Threshold)
                if (delta >= THRESH_2)       spike_ch2 <= 2'b01; // +1
                else if (delta <= -THRESH_2) spike_ch2 <= 2'b10; // -1
                else                         spike_ch2 <= 2'b00; // 0
            end

        end else begin
            valid_out <= 1'b0;
            spike_ch0 <= 2'b00;
            spike_ch1 <= 2'b00;
            spike_ch2 <= 2'b00;
        end
    end

endmodule