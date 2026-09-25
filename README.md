# Overview
[![DOI](https://zenodo.org/badge/920733245.svg)](https://doi.org/10.5281/zenodo.22940195)

# Immersive Spot Teleoperation

**Immersive Spot Teleoperation** is an end-to-end stack for remote control of a Boston Dynamics Spot quadruped from a Meta Quest 2 headset. The operator commands torso attitude from head orientation and planar locomotion from handheld thumbsticks, while stereo video from a ZED 2 camera is compressed on a Jetson Nano and relayed through a public-IP cloud server.

**Dataset:** [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22937199.svg)](https://doi.org/10.5281/zenodo.22937199)

**[Documentation](https://aliy98.github.io/immersive-spot-teleoperation/index.html)** · **[Get Started](https://aliy98.github.io/immersive-spot-teleoperation/installation.html)** · **[API reference](https://aliy98.github.io/immersive-spot-teleoperation/api.html)**

**Authors:** Ali Yousefi, Carmine Tommaso Recchiuto, Antonio Sgorbissa — RICE Lab, DIBRIS, University of Genova.

<p align="left">
<img src="https://github.com/user-attachments/assets/0fdac2aa-7100-4caa-9191-df72cb55c8be" width="150" title="rice_logo">
</p>

**Key features**

- **Five-DoF immersive control** — torso pitch and yaw track the HMD with an infinite-horizon LQR while locomotion runs in parallel from the Quest thumbsticks. The stock Spot tablet cannot command looking and walking at the same time.
- **Head-orientation tracking** — HMD IMU pitch/yaw become the LQR reference; roll is unused; commands are saturated at ±0.5 rad before they reach the Boston Dynamics whole-body controller.
- **Thumbstick locomotion** — right stick maps to heading-frame linear velocities, left stick maps to yaw rate, with a dead-zone policy.
- **Hardware-accelerated stereo streaming** — a GStreamer pipeline on the Jetson encodes ZED 2 frames with `nvv4l2h264enc` and publishes them over RTSP (MediaMTX).
- **Cloud + cellular architecture** — MQTT (Mosquitto) carries 20 Hz control and RTSP carries video through a Google Cloud or Azure VM; the robot uses a SIM7600G-H 4G dongle instead of site Wi-Fi.
- **Matched field of view** — streamed frames are cropped so the HMD view is comparable to the tablet controller used in the user study.
- **Link-loss handling** — the Jetson probes connectivity and restarts the modem service if the 4G uplink drops.
- **Evaluation helpers** — scripts to record, plot, and summarise FPS, latency, bitrate, jitter, and dropped frames.

## Installation

See the **[Installation guide](https://aliy98.github.io/immersive-spot-teleoperation/installation.html)** for full instructions on the Windows operator PC, the Jetson payload, and the cloud VM.

Build the Sphinx documentation locally:

```bash
python -m pip install -r docs/requirements.txt
python -m sphinx -b html docs docs/build/html
```

## Commands

| Command | Where | Description |
| --- | --- | --- |
| `sudo systemctl start mosquitto` | Cloud VM | Start the MQTT broker |
| `./mediamtx` | Cloud VM | Start the RTSP server |
| `python spot_client.py <cloud-ip> ZED` | Jetson | Control loop + ZED RTSP publisher |
| `"ZED Stereo Passthrough.exe" <cloud-ip> ZED` | Windows | Decode the stream and render to the Quest 2 |
| `python scripts/oculus_client.py <cloud-ip>` | Windows | Publish HMD / thumbstick samples to MQTT |
| `python scripts/record_metrics.py` | Windows | Log RTSP link metrics to CSV |
| `python scripts/plot_metrics.py` | Any | Plot FPS, bitrate, latency, and jitter |
| `python scripts/stats_metrics.py` | Any | Print mean / std / min / max / median |

Bring the nodes up in that order: cloud, robot, operator renderer, then the MQTT bridge.

## Pipeline

The system is a three-node loop:

1. **Sense** — the Jetson grabs ZED 2 stereo frames (or Spot onboard cameras), crops them to the study FoV, and hardware-encodes H.264.
2. **Relay** — MediaMTX serves `rtsp://<cloud-ip>:8554/spot-stream`; Mosquitto forwards `oculus/inputs`.
3. **Present** — the Windows client decodes the stream, draws left/right textures in the HMD, and writes six floats to `\\.\pipe\MyPipe`.
4. **Command** — `oculus_client.py` publishes those floats; the Jetson LQR + dead-zone map applies torso and locomotion commands through the Spot SDK.

## Control

Two tasks run in the same loop and are independent of each other:

- **Torso orientation (2 DoF)** — discrete integrator $x_{k+1}=x_k+u_k$ with an infinite-horizon LQR ($Q=10I$, $R=I$, $t_{\mathrm{step}}=0.05,\mathrm{s}$). The HMD pitch axis is sign-flipped to match the robot body-fixed frame.
- **Locomotion (3 DoF)** — heading-frame $v^X$, $v^Y$, and $\omega^Z$ from the Quest sticks after a 0.5 dead zone, saturated at 0.5 m/s and 0.5 rad/s. SDK commands expire after 0.6 s.

The operator can walk while looking around; torso orientation does not change walking direction.

## Roadmap

Potential future extensions include:

- **Additional camera sources** — tighter support for Spot onboard cameras without a ZED 2.
- **5G and multi-operator relays** — optional high-bandwidth links where coverage exists.
- **On-headset clients** — reduce the tethered Windows PC in the loop.
- **Richer mobility modes** — stair and obstacle hints exposed from the high-level layer.
- **Broader platform support** — the same HMD + cloud pattern on other quadrupeds.

## Disclaimer

This repository is research software provided **as-is**, without warranty of any kind. Operating a Spot robot involves inherent physical risk. Users are responsible for leases, e-stops, site permissions, and safe deployment on public networks. Do not commit robot credentials; configure address and account locally before running `spot_interface.py`.

## Citation

If you use this software, please cite *Design and User Evaluation of an Immersive Teleoperation System for a Quadruped Robot* (Yousefi, Recchiuto, Sgorbissa). Code: https://github.com/aliy98/immersive-spot-teleoperation

© 2025 RICE Lab — DIBRIS, University of Genova.

