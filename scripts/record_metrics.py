"""GStreamer probe that logs FPS, latency, bitrate, jitter and drops.

Attaches an appsink/pad probe to the receiver pipeline, maps each buffer,
and appends a row to ``metrics_data.csv``. Used to characterise the RTSP
link during the user-study trials; not required for teleoperation.
"""

import sys
import os
sys.path.append('C:/gstreamer-python/lib/site-packages')
os.add_dll_directory('C:/gstreamer-python/bin')
os.environ['PATH'] = 'C:/gstreamer-python/bin'
import gi
import time
import csv
import cv2
import numpy as np

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

init_time = time.time()

class MetricsRecorder:
    def __init__(self, output_file="metrics_data.csv"):
        self.frame_count = 0
        self.total_frame_size = 0
        self.start_time = time.time()
        self.initial_time = None
        self.last_frame_time = None
        self.previous_inter_frame_time = None  # For jitter calculation
        self.jitter_sum = 0  # Accumulate jitter
        self.jitter_count = 0  # Number of jitter measurements
        self.dropped_frames = 0
        self.output_file = output_file

        # Initialize CSV file
        with open(self.output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Time (s)", "FPS", "Latency (ms)", "Frame Size (bytes)",
                             "Bitrate (kbps)", "Jitter (ms)", "Dropped Frames"])

    def calculate_latency(self, buffer):
        """Calculate latency using the buffer's PTS."""
        if buffer.pts != Gst.CLOCK_TIME_NONE:
            pts_sec = buffer.pts / Gst.SECOND  # Convert PTS from nanoseconds to seconds
            latency = (time.time() - init_time - pts_sec) * 1000  # Latency in ms
            return latency
        return None

    def calculate_jitter(self, current_time):
        """Calculate jitter based on inter-frame time differences."""
        if self.last_frame_time is not None:
            inter_frame_time = (current_time - self.last_frame_time) * 1000  # ms
            if self.previous_inter_frame_time is not None:
                jitter = abs(inter_frame_time - self.previous_inter_frame_time)  # Jitter is the absolute variation
                self.jitter_sum += jitter
                self.jitter_count += 1
            self.previous_inter_frame_time = inter_frame_time
        self.last_frame_time = current_time

    def on_frame(self, pad, info):
        current_time = time.time()
        buffer = info.get_buffer()

        # Initialize timestamps
        if self.initial_time is None:
            self.initial_time = current_time

        relative_time = current_time - self.initial_time
        elapsed_time = current_time - self.start_time

        # Extract frame data from the buffer
        frame = None
        if buffer and buffer.get_size() > 0:
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                # Assume the frame is raw grayscale video
                frame_data = np.frombuffer(map_info.data, dtype=np.uint8)
                frame = frame_data.reshape((240, 1280))  # Update resolution to match your stream
                buffer.unmap(map_info)
            else:
                print("Failed to map buffer")

        # Calculate latency using PTS
        latency = self.calculate_latency(buffer)

        # Calculate jitter
        self.calculate_jitter(current_time)

        # Display the frame
        if frame is not None:
            cv2.imshow("Received Frame", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):  # Press 'q' to quit
                return Gst.PadProbeReturn.DROP

        # Frame size
        frame_size = buffer.get_size() if buffer else 0
        self.total_frame_size += frame_size
        self.frame_count += 1

        # Calculate FPS, bitrate, and jitter every second
        if elapsed_time >= 1.0:
            fps = self.frame_count / elapsed_time
            bitrate = (self.total_frame_size * 8) / 1000 / elapsed_time  # kbps
            average_jitter = (self.jitter_sum / self.jitter_count) if self.jitter_count > 0 else 0  # Average jitter

            # Write metrics to CSV
            with open(self.output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([round(relative_time, 2), round(fps, 2), round(latency or 0, 2),
                                 frame_size, round(bitrate, 2), round(average_jitter, 2), self.dropped_frames])

            print(f"Time: {relative_time:.2f}s, FPS: {fps:.2f}, Latency: {latency or 0:.2f}ms, "
                  f"Frame Size: {frame_size} bytes, Bitrate: {bitrate:.2f} kbps, "
                  f"Jitter: {average_jitter:.2f}ms, Dropped Frames: {self.dropped_frames}")

            # Reset counters
            self.frame_count = 0
            self.total_frame_size = 0
            self.start_time = current_time
            self.jitter_sum = 0
            self.jitter_count = 0

        return Gst.PadProbeReturn.OK




# GStreamer pipeline
pipeline_str = (
    "rtspsrc location=rtsp://48.209.18.239:8554/spot-stream latency=0 ! "
    "rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoscale ! "
    "video/x-raw,width=1280,height=240,format=GRAY8 ! appsink name=appsink0"
)

# Create the pipeline
pipeline = Gst.parse_launch(pipeline_str)

# Attach the metrics recorder
metrics_recorder = MetricsRecorder()

appsink = pipeline.get_by_name("appsink0")
if appsink is None:
    print("Failed to find appsink element in the pipeline.")
    exit(1)

appsink_pad = appsink.get_static_pad("sink")
if appsink_pad is not None:
    appsink_pad.add_probe(Gst.PadProbeType.BUFFER, metrics_recorder.on_frame)
else:
    print("Failed to get the sink pad of appsink.")
    exit(1)

# Start the pipeline
pipeline.set_state(Gst.State.PLAYING)

try:
    # Run the main loop
    loop = GLib.MainLoop()
    loop.run()
except KeyboardInterrupt:
    # Stop the pipeline on interrupt
    pipeline.set_state(Gst.State.NULL)
    cv2.destroyAllWindows()
    print("Pipeline stopped.")
