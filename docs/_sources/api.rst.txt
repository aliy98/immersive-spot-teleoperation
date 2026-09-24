API reference
=============

Annotated reference for every script and compiled source in the
repository. Behaviour matches the *Technical approach* section of the
manuscript. Docstrings were added in-tree so the same text is available
from the source files and from this page.

Message and command layouts
---------------------------

MQTT topic ``oculus/inputs`` (JSON list, 20 Hz)::

    [pitch_hmd, yaw_hmd, roll_hmd, stick_x, stick_y, stick_yaw]

Named pipe ``\\.\pipe\MyPipe`` (Windows, 24 bytes, ``struct`` format
``6f``): the same six floats, little-endian.

Vector applied by :meth:`SpotInterface.set_controls`::

    [u_yaw, u_pitch, 0.0, v_x, v_y, omega_z]
     \---- LQR 3-vector ----/  \-- locomotion --/

RTSP URL published by both stream loops::

    rtsp://<cloud-ip>:8554/spot-stream

.. toctree::
   :maxdepth: 2

   api_spot_client
   api_spot_controller
   api_spot_interface
   api_zed
   api_oculus
   api_metrics
   api_cpp
