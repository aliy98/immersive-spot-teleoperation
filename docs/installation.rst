Installation
============

Three machines are required: the operator PC, the Jetson on Spot, and a
cloud VM.

Operator PC (Windows 64-bit)
----------------------------

* Windows 10/11 x64
* Python ≥ 3.7
* CMake
* Visual Studio 2022
* `Oculus SDK for Windows <https://developer.oculus.com/downloads/package/oculus-sdk-for-windows/>`_ ≥ 1.17
* `CUDA Toolkit <https://developer.nvidia.com/cuda-downloads>`_
* GLEW (shipped with the ZED SDK)
* `SDL2 <https://github.com/libsdl-org/SDL/releases/tag/release-2.30.1>`_
* `GStreamer <https://gstreamer.freedesktop.org/documentation/installing/on-windows.html>`_
* OpenCV **built with GStreamer**
  (`tutorial <https://galaktyk.medium.com/how-to-build-opencv-with-gstreamer-b11668fa09c>`_)
* ``paho-mqtt`` (``pip install paho-mqtt``)
* ZED SDK 3.x

CMake cache variables that must be set (see root ``CMakeLists.txt``):

.. code-block:: cmake

   OCULUS_PATH   # e.g. C:\ovr_sdk_win_0.17.0\OculusSDK
   SDL_PATH      # e.g. C:\SDL2-2.0.3

Build steps:

1. Clone the repository and create a ``build`` folder in the root.
2. Open *cmake-gui*, set the source and build folders.
3. Generate a Visual Studio Win64 solution.
4. Open the solution, switch to **Release**, fix any dependency paths.
5. Build. The target name is ``ZED Stereo Passthrough``.

The project is C++11 and links ZED, CUDA, OpenGL, GLEW, SDL2, and
LibOVR.

Jetson Nano (Ubuntu 18.04)
--------------------------

No C++ build is required. Clone ``scripts/spot_client/`` onto the board
and install:

* Python ≥ 3.7
* `Boston Dynamics Spot SDK <https://dev.bostondynamics.com/>`_
* ZED SDK 3.x and the `ZED Python API <https://www.stereolabs.com/docs/app-development/python/install>`_
* GStreamer
* OpenCV built with GStreamer
* `do-mpc <https://www.do-mpc.com/en/latest/installation.html>`_ (pulls CasADi)
* ``paho-mqtt``

The interface authenticates to Spot at ``10.0.0.3``. Edit
``spot_interface.py`` if your payload network uses a different address
or credentials.

Cloud VM
--------

Create a public-IP VM on Google Cloud or Microsoft Azure and install:

* `MediaMTX <https://github.com/bluenviron/mediamtx>`_
* `Mosquitto <https://mosquitto.org/download/>`_

Open TCP 8554 (RTSP) and 1883 (MQTT) on the firewall. Bind MediaMTX to
``0.0.0.0``.

Building this documentation
---------------------------

.. code-block:: bash

   cd docs
   python -m pip install -r requirements.txt
   make html
   # output: docs/_build/html/index.html
