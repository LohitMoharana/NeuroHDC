`timescale 1ns / 1ps

module top_shde_wrapper (
    input  wire              clk,
    input  wire              rst_n,
    input  wire signed [15:0] analog_in,
    input  wire              valid_in,

    output wire [31:0]       hv_data_out,
    output wire              hv_valid_out
);

    // ================================================================
    // SMALL-SCALE ASIC PROTOTYPE
    //
    // WINDOW_SIZE = 32
    // CHUNK       = 32
    // FOLDS       = 8
    //
    // Total hypervector = 8 × 32 = 256 bits
    //
    // The architecture remains:
    //
    // tokenizer -> FIFO -> HDC binder -> accumulator -> evaluator
    //
    // The wrapper serializes the eight 32-bit chunks.
    // ================================================================

    localparam integer WINDOW_SIZE = 32;
    localparam integer CHUNK       = 32;
    localparam integer FOLDS       = 8;
    localparam integer FIFO_DEPTH  = 8;

    localparam integer FIFO_PTR_W =
        (FIFO_DEPTH <= 2) ? 1 : $clog2(FIFO_DEPTH);

    // ================================================================
    // HDC CORE
    // ================================================================

    wire [CHUNK-1:0] internal_chunk_hv;
    wire             internal_chunk_valid;

    wire             debug_fifo_push;
    wire             debug_fifo_pop;
    wire [7:0]       debug_fifo_count;

    top_shde_core #(
        .WINDOW_SIZE (WINDOW_SIZE),
        .CHUNK       (CHUNK),
        .FOLDS       (FOLDS),
        .FIFO_DEPTH  (16)
    ) core_inst (
        .clk             (clk),
        .rst_n           (rst_n),
        .analog_in       (analog_in),
        .valid_in        (valid_in),

        .chunk_hv        (internal_chunk_hv),
        .chunk_hv_valid  (internal_chunk_valid),

        .debug_fifo_push (debug_fifo_push),
        .debug_fifo_pop  (debug_fifo_pop),
        .debug_fifo_count(debug_fifo_count)
    );

    // ================================================================
    // CHUNK FIFO
    //
    // Each entry = one 32-bit HDC chunk.
    //
    // Eight chunks = one complete 256-bit hypervector.
    // ================================================================

    reg [CHUNK-1:0] chunk_fifo [0:FIFO_DEPTH-1];

    reg [FIFO_PTR_W-1:0] fifo_wr_ptr;
    reg [FIFO_PTR_W-1:0] fifo_rd_ptr;

    reg [FIFO_PTR_W:0] fifo_count;

    // ================================================================
    // OUTPUT STATE
    // ================================================================

    reg [CHUNK-1:0] shift_reg;
    reg             streaming;

    // ================================================================
    // SEQUENTIAL CONTROL
    // ================================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            fifo_wr_ptr <= {FIFO_PTR_W{1'b0}};
            fifo_rd_ptr <= {FIFO_PTR_W{1'b0}};
            fifo_count  <= {(FIFO_PTR_W+1){1'b0}};

            shift_reg   <= {CHUNK{1'b0}};
            streaming   <= 1'b0;

        end

        else begin

            // --------------------------------------------------------
            // Store newly generated HDC chunk.
            // --------------------------------------------------------

            if (internal_chunk_valid &&
                (fifo_count < FIFO_DEPTH)) begin

                chunk_fifo[fifo_wr_ptr] <= internal_chunk_hv;

                if (fifo_wr_ptr == FIFO_DEPTH-1)
                    fifo_wr_ptr <= {FIFO_PTR_W{1'b0}};
                else
                    fifo_wr_ptr <= fifo_wr_ptr + 1'b1;

            end

            // --------------------------------------------------------
            // Load one complete 32-bit chunk to output.
            //
            // Since CHUNK == 32, no additional shifting is necessary.
            // --------------------------------------------------------

            if (!streaming && (fifo_count != 0)) begin

                shift_reg <= chunk_fifo[fifo_rd_ptr];

                if (fifo_rd_ptr == FIFO_DEPTH-1)
                    fifo_rd_ptr <= {FIFO_PTR_W{1'b0}};
                else
                    fifo_rd_ptr <= fifo_rd_ptr + 1'b1;

                streaming <= 1'b1;

            end

            // --------------------------------------------------------
            // Output one chunk for one clock.
            // --------------------------------------------------------

            else if (streaming) begin

                shift_reg <= {CHUNK{1'b0}};
                streaming <= 1'b0;

            end

            // --------------------------------------------------------
            // FIFO count.
            // --------------------------------------------------------

            case ({
                internal_chunk_valid &&
                (fifo_count < FIFO_DEPTH),

                !streaming &&
                (fifo_count != 0)
            })

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
    // OUTPUT
    // ================================================================

    assign hv_data_out  = shift_reg;

    assign hv_valid_out = streaming;

endmodule
