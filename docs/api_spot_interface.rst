``scripts/spot_client/spot_interface.py``
=========================================

Boston Dynamics Python-SDK facade. Owns lease, e-stop, power, state and
command clients.

Module constants
----------------

.. py:data:: VELOCITY_CMD_DURATION
   :value: 0.6

   End time, in seconds, attached to every SDK command so a dropped
   packet cannot leave the robot walking.

.. py:data:: MAX_YAW
   :value: 0.5

.. py:data:: MAX_PITCH
   :value: 0.5

   Joint-safe saturation in radians (paper: :math:`0.52\,\mathrm{rad}`).

.. py:class:: SpotInterface(image_source)

   :param str image_source: ``"ZED"`` or ``"SPOT"``.

   Connects to ``10.0.0.3`` on the payload LAN. Edit the constructor
   before using another address or account.

   .. py:method:: _toggle_estop()

      Start or stop the ``EstopKeepAlive`` thread. Initial state is ON.

   .. py:method:: _orientation_cmd_helper(yaw=0.0, roll=0.0, pitch=0.0, height=0.0)

      ``synchro_stand_command`` with ``EulerZXY`` body offset.

   .. py:method:: _velocity_cmd_helper(v_x=0.0, v_y=0.0, v_rot=0.0)

      ``synchro_velocity_command`` with the mobility params from
      :meth:`_set_mobility_params`.

   .. py:method:: _set_mobility_params()

      Return ``bosdyn.api.spot.robot_command_pb2.MobilityParams``.
      Vision obstacle avoidance on (10 cm padding), speed cap
      :math:`(1, 1)` m/s and 0.7 rad/s, ``HINT_AUTO``. When any planar
      velocity is non-zero the commanded yaw offset is zeroed so walking
      direction stays in the heading frame.

   .. py:method:: get_body_vel()

      Return ``[z, y, x]`` angular velocity of the body in the vision
      frame. Kept for diagnostics; the closed loop uses orientation,
      not rate.

   .. py:method:: get_body_orientation()

      Return integrated ``[yaw, pitch, roll]`` rounded to 3 decimals.
      This is the LQR measurement ``x_k``.

   .. py:method:: set_controls(controls)

      :param controls: ``[dyaw, dpitch, _, v_x, v_y, v_rot]``.

      Accumulates pitch/yaw, clips to ``±MAX_*``, stores the three
      velocities and sends a velocity command that also carries the body
      offset through mobility params.

   .. py:method:: _start()

      Take the lease, configure e-stop, power on, ``blocking_stand``.
      If ``image_source == "SPOT"``, construct the optional ``Stitch``
      helper.

   .. py:method:: shutdown()

      Zero the body offset, sit, safe-power-off, stop keep-alives.

   .. py:method:: get_image()

      One stitched onboard frame (SPOT source only).
