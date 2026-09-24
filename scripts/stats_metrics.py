"""Print mean/std/min/max/median of the columns in ``metrics_data.csv``.
"""

import csv
import numpy as np

# Function to read values from the CSV file
def read_metrics_from_csv(csv_file):
    fps_values = []
    latencies = []
    frame_sizes = []
    bitrates = []
    jitters = []
    dropped_frames = []

    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            fps_values.append(float(row[1]))
            latencies.append(float(row[2]))
            frame_sizes.append(int(row[3]))
            bitrates.append(float(row[4]))
            jitters.append(float(row[5]))
            dropped_frames.append(int(row[6]))

    return fps_values, latencies, frame_sizes, bitrates, jitters, dropped_frames

# Function to calculate statistics
def calculate_stats(values):
    mean = np.mean(values)
    std = np.std(values)
    min_val = np.min(values)
    max_val = np.max(values)
    median = np.median(values)
    return mean, std, min_val, max_val, median

# Read data from the CSV file
csv_file = 'metrics_data.csv'  # Update with your actual file path
fps_values, latencies, frame_sizes, bitrates, jitters, dropped_frames = read_metrics_from_csv(csv_file)
# Convert bitrate from kbps to Mbps
bitrate_mbps = [bitrate / 1000 for bitrate in bitrates]

# Calculate statistics for each metric
fps_stats = calculate_stats(fps_values)
latency_stats = calculate_stats(latencies)
frame_size_stats = calculate_stats(frame_sizes)
bitrate_stats = calculate_stats(bitrate_mbps)
jitter_stats = calculate_stats(jitters)
dropped_frames_stats = calculate_stats(dropped_frames)

# Print the statistical values
print(f"FPS - Mean: {fps_stats[0]:.2f}, STD: {fps_stats[1]:.2f}, Min: {fps_stats[2]}, Max: {fps_stats[3]}, Median: {fps_stats[4]}")
print(f"Latency (ms) - Mean: {latency_stats[0]:.2f}, STD: {latency_stats[1]:.2f}, Min: {latency_stats[2]}, Max: {latency_stats[3]}, Median: {latency_stats[4]}")
print(f"Frame Size (bytes) - Mean: {frame_size_stats[0]:.2f}, STD: {frame_size_stats[1]:.2f}, Min: {frame_size_stats[2]}, Max: {frame_size_stats[3]}, Median: {frame_size_stats[4]}")
print(f"Bitrate (Mbps) - Mean: {bitrate_stats[0]:.2f}, STD: {bitrate_stats[1]:.2f}, Min: {bitrate_stats[2]}, Max: {bitrate_stats[3]}, Median: {bitrate_stats[4]}")
print(f"Jitter (ms) - Mean: {jitter_stats[0]:.2f}, STD: {jitter_stats[1]:.2f}, Min: {jitter_stats[2]}, Max: {jitter_stats[3]}, Median: {jitter_stats[4]}")
print(f"Dropped Frames - Mean: {dropped_frames_stats[0]:.2f}, STD: {dropped_frames_stats[1]:.2f}, Min: {dropped_frames_stats[2]}, Max: {dropped_frames_stats[3]}, Median: {dropped_frames_stats[4]}")
