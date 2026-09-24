"""Plot FPS/bitrate and latency/jitter from ``metrics_data.csv``.
"""

import matplotlib.pyplot as plt
import csv

# Initialize data lists
timestamps, fps_values, bitrates, latencies, jitters = ([] for _ in range(5))

# Read metrics data
with open("metrics_data.csv", 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        timestamps.append(float(row[0]))
        fps_values.append(float(row[1]))
        latencies.append(float(row[2]))
        bitrates.append(float(row[4]))
        jitters.append(float(row[5]))

# Convert bitrate from kbps to Mbps
bitrate_mbps = [bitrate / 1000 for bitrate in bitrates]

plt.rcParams.update({'font.size': 16})  # Increase default font size


# Create a figure with 2 subplots
fig, ax = plt.subplots(2, 1, figsize=(10, 8))

# Plot FPS and Bitrate in the first subplot
ax[0].plot(timestamps, fps_values, label="Frame rate (fps)", color="blue")
ax[0].plot(timestamps, bitrate_mbps, label="Bitrate (Mbps)", color="red")
ax[0].set_title("Frame rate and Bitrate Over Time")
ax[0].set_xlabel("Time (s)")
ax[0].set_ylabel("Value")
ax[0].legend(loc="upper right")

# Plot Latency and Jitter in the second subplot
ax[1].plot(timestamps, latencies, label="Latency (ms)", color="green")
ax[1].plot(timestamps, jitters, label="Jitter (ms)", color="purple")
ax[1].set_title("Latency and Jitter Over Time")
ax[1].set_xlabel("Time (s)")
ax[1].set_ylabel("Value (ms)")
ax[1].legend(loc="upper right")

# Adjust layout to prevent overlap
plt.tight_layout()

# Show the plots
plt.show()
