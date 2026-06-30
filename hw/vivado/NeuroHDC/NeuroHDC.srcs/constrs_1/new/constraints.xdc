# Define the main clock frequency as 100 MHz (10.000 ns period)
# This prevents Vivado from assuming a 1 GHz clock and hallucinating 64W of power!
create_clock -period 1000.000 -name clk -waveform {0.000 500.000} [get_ports clk]