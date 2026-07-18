`timescale 1ns / 1ps

module top_shde_core #(
    parameter D = 4096,
    parameter WINDOW_SIZE = 256,
    parameter CHUNK = 128,
    parameter FOLDS = 32
)(
    input wire clk,
    input wire rst_n,
    input wire signed [15:0] analog_in,
    input wire valid_in,

    output wire [D-1:0] final_hv,
    output wire hv_ready
);

    wire [1:0] spike_ch0, spike_ch1, spike_ch2;
    wire tok_valid_out;

    delta_tokenizer tok_inst (
        .clk(clk),
        .rst_n(rst_n),
        .analog_in(analog_in),
        .valid_in(valid_in),
        .spike_ch0(spike_ch0),
        .spike_ch1(spike_ch1),
        .spike_ch2(spike_ch2),
        .valid_out(tok_valid_out)
    );

    reg [7:0] t_counter;
    wire end_of_window = (t_counter == WINDOW_SIZE - 1) && tok_valid_out;
    reg [7:0] latched_t_counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            t_counter <= 8'd0;
            latched_t_counter <= 8'd0;
        end else if (tok_valid_out) begin
            latched_t_counter <= t_counter;
            if (t_counter == WINDOW_SIZE - 1)
                t_counter <= 8'd0;
            else
                t_counter <= t_counter + 8'd1;
        end
    end

    (* ram_style = "block" *) reg [CHUNK-1:0] ch0_bram [0:FOLDS-1];
    (* ram_style = "block" *) reg [CHUNK-1:0] ch1_bram [0:FOLDS-1];
    (* ram_style = "block" *) reg [CHUNK-1:0] ch2_bram [0:FOLDS-1];
    (* ram_style = "block" *) reg [CHUNK-1:0] item_up_bram [0:FOLDS-1];
    (* ram_style = "block" *) reg [CHUNK-1:0] item_dn_bram [0:FOLDS-1];
    (* ram_style = "block" *) reg [CHUNK-1:0] pos_bram [0:WINDOW_SIZE*FOLDS-1];

    initial begin
`ifdef ASIC_FLOW
        $readmemb("/openlane/designs/neurohdc/src/ch0.dat", ch0_bram);
        $readmemb("/openlane/designs/neurohdc/src/ch1.dat", ch1_bram);
        $readmemb("/openlane/designs/neurohdc/src/ch2.dat", ch2_bram);
        $readmemb("/openlane/designs/neurohdc/src/item_up.dat", item_up_bram);
        $readmemb("/openlane/designs/neurohdc/src/item_dn.dat", item_dn_bram);
        $readmemb("/openlane/designs/neurohdc/src/pos.dat", pos_bram);
`else
        $readmemb("D:/Projects/Personal/NeuroHDC/hw/tb/ch0.dat", ch0_bram);
        $readmemb("D:/Projects/Personal/NeuroHDC/hw/tb/ch1.dat", ch1_bram);
        $readmemb("D:/Projects/Personal/NeuroHDC/hw/tb/ch2.dat", ch2_bram);
        $readmemb("D:/Projects/Personal/NeuroHDC/hw/tb/item_up.dat", item_up_bram);
        $readmemb("D:/Projects/Personal/NeuroHDC/hw/tb/item_dn.dat", item_dn_bram);
        $readmemb("D:/Projects/Personal/NeuroHDC/hw/tb/pos.dat", pos_bram);
`endif
    end

    wire [4:0] rom_addr_out;
    wire core_bram_en; // POWER OPTIMIZATION: BRAM Sleep Wire

    wire [4:0] inv_rom_addr = (FOLDS - 1) - rom_addr_out;
    wire [14:0] pos_bram_addr = (latched_t_counter * FOLDS) + inv_rom_addr;

    reg [CHUNK-1:0] chunk_ch0, chunk_ch1, chunk_ch2;
    reg [CHUNK-1:0] chunk_item_up, chunk_item_dn, chunk_pos_t;

    always @(posedge clk) begin
        // POWER OPTIMIZATION: This strictly infers the BRAM Enable (EN) pin.
        // Vivado will completely power down the BRAMs when core_bram_en is 0.
        if (core_bram_en) begin
            chunk_ch0     <= ch0_bram[inv_rom_addr];
            chunk_ch1     <= ch1_bram[inv_rom_addr];
            chunk_ch2     <= ch2_bram[inv_rom_addr];
            chunk_item_up <= item_up_bram[inv_rom_addr];
            chunk_item_dn <= item_dn_bram[inv_rom_addr];
            chunk_pos_t   <= pos_bram[pos_bram_addr];
        end
    end

    hdc_bind_bundle #(
        .D(D),
        .CHUNK(CHUNK),
        .FOLDS(FOLDS)
    ) hdc_core_inst (
        .clk(clk),
        .rst_n(rst_n),
        .spike_ch0(spike_ch0),
        .spike_ch1(spike_ch1),
        .spike_ch2(spike_ch2),
        .valid_in(tok_valid_out),
        .end_of_window(end_of_window),
        .chunk_ch0(chunk_ch0),
        .chunk_ch1(chunk_ch1),
        .chunk_ch2(chunk_ch2),
        .chunk_item_up(chunk_item_up),
        .chunk_item_down(chunk_item_dn),
        .chunk_pos_t(chunk_pos_t),
        .rom_addr_out(rom_addr_out),
        .bram_en(core_bram_en),
        .final_hv(final_hv),
        .hv_ready(hv_ready)
    );

endmodule