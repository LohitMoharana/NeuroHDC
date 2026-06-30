import os

data_dir = "data"

# Read original 8192-bit lines
with open(os.path.join(data_dir, "channel_memory.dat")) as f: ch_lines = [l.strip() for l in f]
with open(os.path.join(data_dir, "item_memory.dat")) as f: item_lines = [l.strip() for l in f]
with open(os.path.join(data_dir, "pos_memory.dat")) as f: pos_lines = [l.strip() for l in f]

def write_chunked(filename, line_list):
    with open(filename, 'w') as f:
        for line in line_list:
            # Split 8192 bits into 64 lines of 128 bits
            for i in range(0, len(line), 128):
                f.write(line[i:i+128] + "\n")

# Generate pure BRAM-compatible files
write_chunked("ch0.dat", [ch_lines[0]])
write_chunked("ch1.dat", [ch_lines[1]])
write_chunked("ch2.dat", [ch_lines[2]])
write_chunked("item_up.dat", [item_lines[0]])
write_chunked("item_dn.dat", [item_lines[1]])
write_chunked("pos.dat", pos_lines)

print("SUCCESS: 8192-bit vectors sliced into 128-bit hardware BRAM blocks!")