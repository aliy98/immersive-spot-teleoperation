``scripts/spot_client/zed_interface.py``
========================================

Stereolabs capture used by :func:`stream_loop_zed`.

.. py:class:: ZEDInterface()

   Opens the ZED 2 at ``RESOLUTION.HD720``, 60 fps,
   ``DEPTH_MODE.NONE`` (no depth to save compute and uplink).

   The internal ``sl.Mat`` is allocated at half height so a side-by-side
   retrieve already matches the HMD stereo pair.

   .. py:method:: get_image()

      Grab, retrieve ``VIEW.SIDE_BY_SIDE``, convert RGBA → gray, crop
      ``(x, y, w, h) = (0, 120, 1280, 240)``. That crop is the FoV match
      against the stock tablet controller.

      :returns: ``(240, 1280)`` ``uint8`` array, or ``0`` on grab error.

   .. py:method:: shutdown()

      ``Camera.close()``.
