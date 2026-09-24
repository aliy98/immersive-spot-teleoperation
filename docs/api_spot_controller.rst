``scripts/spot_client/spot_controller.py``
==========================================

Discrete LQR torso tracker and dead-zone locomotion map
(``do_mpc`` / CasADi).

Module constants
----------------

.. py:data:: INPUT_TRESHOLD
   :value: 0.5

   Thumbstick dead zone (unitless).

.. py:data:: VELOCITY_BASE_SPEED
   :value: 0.5

   Saturated heading-frame linear speed in m/s.

.. py:data:: VELOCITY_BASE_ANGULAR
   :value: 0.5

   Saturated heading-frame yaw rate in rad/s.

.. py:class:: Controller()

   Builds the integrator model and solves the discrete Riccati equation
   once at construction.

   .. py:attribute:: setpoints
      :type: numpy.ndarray

      Shape ``(2, 1)``. HMD pitch/yaw reference ``xss``.

   .. py:method:: get_model()

      Return a ``do_mpc.model.LinearModel``.
      State and input in :math:`\mathbb{R}^{2}`, RHS :math:`x + u`
      (i.e. :math:`A = B = I`).

   .. py:method:: get_lqr(model, silence_solver=False)

      Return a ``do_mpc.controller.LQR``.
      ``t_step = 0.05``, ``n_horizon = None``,
      :math:`Q = 10 I`, :math:`R = I`, increment penalty ``delR = I``.

   .. py:method:: get_setpoints(setpoints)

      Keep ``setpoints[0:2]`` (HMD pitch, yaw). Roll is ignored.

   .. py:method:: get_simulator(model)

      Return a ``do_mpc.simulator.Simulator``.
      Only used by the ``__main__`` sine-tracking demo.

   .. py:method:: get_touch_controls(setpoints)

      Return ``[v_x, v_y, omega_z]``.
      Map ``[stick_x, stick_y, stick_yaw]`` through the dead zone onto
      heading-frame velocities. Y and yaw axes are sign-flipped to match
      the Quest / heading-frame convention.

   .. py:method:: get_hmd_controls(measures)

      One LQR step. ``measures`` is ``[yaw, pitch, roll]`` from
      :meth:`SpotInterface.get_body_orientation`. Returns
      ``[u_yaw, u_pitch, 0.0]``.
