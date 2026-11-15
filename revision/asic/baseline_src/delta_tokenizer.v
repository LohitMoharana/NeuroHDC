`timescale 1ns / 1ps

module delta_tokenizer #(
    parameter signed [15:0] THRESH_0 = 16'sd1638,
    parameter signed [15:0] THRESH_1 = 16'sd8192,
    parameter signed [15:0] THRESH_2 = 16'sd19660
)(
    input  wire              clk,
    input  wire              rst_n,
    input  wire signed [15:0] analog_in,
    input  wire              valid_in,

    output reg  [1:0]        spike_ch0,
    output reg  [1:0]        spike_ch1,
    output reg  [1:0]        spike_ch2,
    output reg               valid_out
);

    localparam [1:0] SPIKE_NONE = 2'b00;
    localparam [1:0] SPIKE_UP   = 2'b01;
    localparam [1:0] SPIKE_DOWN = 2'b10;

    reg signed [15:0] prev_analog;
    reg               first_valid;

    /*
     * Explicit signed 17-bit thresholds.
     *
     * IMPORTANT:
     * The previous implementation used expressions such as
     *
     *     delta <= -THRESH_1
     *
     * together with concatenations such as
     *
     *     {1'b0, THRESH_1}
     *
     * which can introduce unsigned comparison semantics.
     *
     * Keeping both delta and thresholds explicitly signed avoids
     * negative deltas being interpreted as large positive values.
     */

    localparam signed [16:0] TH0_POS = 17'sd1638;
    localparam signed [16:0] TH1_POS = 17'sd8192;
    localparam signed [16:0] TH2_POS = 17'sd19660;

    localparam signed [16:0] TH0_NEG = -17'sd1638;
    localparam signed [16:0] TH1_NEG = -17'sd8192;
    localparam signed [16:0] TH2_NEG = -17'sd19660;

    wire signed [16:0] delta;

    assign delta =
        $signed({analog_in[15], analog_in}) -
        $signed({prev_analog[15], prev_analog});

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            prev_analog <= 16'sd0;
            first_valid <= 1'b1;

            spike_ch0 <= SPIKE_NONE;
            spike_ch1 <= SPIKE_NONE;
            spike_ch2 <= SPIKE_NONE;

            valid_out <= 1'b0;

        end

        else if (valid_in) begin

            prev_analog <= analog_in;
            valid_out   <= 1'b1;

            /*
             * The first valid sample establishes the reference.
             * It does not generate a token.
             */

            if (first_valid) begin

                first_valid <= 1'b0;

                spike_ch0 <= SPIKE_NONE;
                spike_ch1 <= SPIKE_NONE;
                spike_ch2 <= SPIKE_NONE;

            end

            else begin

                /* Channel 0 */

                if (delta >= TH0_POS)
                    spike_ch0 <= SPIKE_UP;

                else if (delta <= TH0_NEG)
                    spike_ch0 <= SPIKE_DOWN;

                else
                    spike_ch0 <= SPIKE_NONE;


                /* Channel 1 */

                if (delta >= TH1_POS)
                    spike_ch1 <= SPIKE_UP;

                else if (delta <= TH1_NEG)
                    spike_ch1 <= SPIKE_DOWN;

                else
                    spike_ch1 <= SPIKE_NONE;


                /* Channel 2 */

                if (delta >= TH2_POS)
                    spike_ch2 <= SPIKE_UP;

                else if (delta <= TH2_NEG)
                    spike_ch2 <= SPIKE_DOWN;

                else
                    spike_ch2 <= SPIKE_NONE;

            end

        end

        else begin

            valid_out <= 1'b0;

            spike_ch0 <= SPIKE_NONE;
            spike_ch1 <= SPIKE_NONE;
            spike_ch2 <= SPIKE_NONE;

        end

    end

endmodule
