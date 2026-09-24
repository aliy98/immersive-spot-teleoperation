Evaluation scripts
==================

Not on the teleoperation critical path. They characterise the RTSP link
(FPS, latency, bitrate, jitter, dropped frames) during trials.

``scripts/record_metrics.py``
-----------------------------

.. py:class:: MetricsRecorder(output_file="metrics_data.csv")

   GStreamer pad probe. Writes a CSV with columns
   ``Time, FPS, Latency (ms), Frame Size, Bitrate (kbps), Jitter (ms),
   Dropped Frames``.

   .. py:method:: calculate_latency(buffer)

      Compare buffer PTS with wall-clock time started at import.

   .. py:method:: calculate_jitter(current_time)

      Absolute difference of successive inter-frame intervals.

   .. py:method:: on_frame(pad, info)

      Map the buffer as ``uint8 (240, 1280)`` gray and append one CSV
      row.

``scripts/plot_metrics.py``
---------------------------

Reads ``metrics_data.csv`` and draws two stacked axes: frame-rate +
bitrate (Mbps), then latency + jitter (ms).

``scripts/stats_metrics.py``
----------------------------

.. py:function:: read_metrics_from_csv(csv_file)

   Return the six numeric columns as Python lists.

.. py:function:: calculate_stats(values)

   ``(mean, std, min, max, median)`` via NumPy.
