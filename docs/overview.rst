Overview
========

Problem
-------

Regarding control, two aspects must be solved at once:

1. Commanding the robot's **attitude** through head-orientation tracking.
2. Commanding **locomotion** with handheld controllers.

Regarding perception, a real-time streaming method is required to keep a
continuous stereo video feed on the operator HMD, even when the robot is
on a cellular link far from the operator.

Spot already exposes a black-box whole-body controller that accepts
decoupled commands:

* torso orientation (roll, pitch, yaw) in the **body-fixed frame**;
* planar locomotion (linear velocities and heading rate) in the
  **heading frame**.

The heading frame moves with the robot in the horizontal plane and is
independent of torso orientation. The high-level layer designed here
therefore treats torso tracking and locomotion as two parallel tasks.

.. raw:: html
  
  <iframe width="560" height="315" src="https://www.youtube.com/embed/SNHXewitwgQ?si=zCsPA3ZqpFCQf9qG" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>  
|

Why immersive control
---------------------

On the stock tablet controller the operator has only two thumbsticks
and therefore only four of the five required DoF. Walking and looking
must be time-multiplexed. With the HMD the operator walks with the
controllers while the torso follows the head, which removes that mode
switch and the delays it introduces.

Why a cloud + 4G architecture
-----------------------------

The previous generation of this stack used site Wi-Fi, which confined
experiments to an office. The redesigned architecture hosts MediaMTX
(RTSP) and Mosquitto (MQTT) on a public-IP virtual machine (Google Cloud
or Microsoft Azure). The robot reaches that VM through a SIM7600G-H 4G
dongle.

4G is preferred over 5G because coverage is wider (as of 2025, roughly
93 % of the global population versus 55 % for 5G). Gaps matter in
non-residential sites such as harbour container parks, a target
application domain. The design therefore favours availability over peak
bandwidth; hardware-accelerated H.264 encoding on the Jetson keeps the
stereo feed inside that budget.

Repository layout
-----------------

.. code-block:: text

   immersive-spot-teleoperation/
   ├── CMakeLists.txt          # Windows OpenGL / Oculus client
   ├── include/Shader.hpp
   ├── src/main.cpp            # HMD render + input thread
   ├── src/Shader.cpp
   └── scripts/
       ├── oculus_client.py    # named-pipe → MQTT publisher
       ├── record_metrics.py
       ├── plot_metrics.py
       ├── stats_metrics.py
       └── spot_client/
           ├── spot_client.py      # Jetson entry point
           ├── spot_interface.py   # Boston Dynamics SDK wrapper
           ├── spot_controller.py  # LQR + dead-zone locomotion
           └── zed_interface.py    # ZED 2 capture

The last two C++ sources and ``oculus_client.py`` run on the operator
Windows PC. Everything under ``scripts/spot_client/`` runs on the
Jetson Nano mounted on Spot.
