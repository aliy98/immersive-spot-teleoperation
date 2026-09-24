#!/usr/bin/env python
"""High-level LQR torso tracker and dead-zone locomotion map.

This module implements the discrete controller described in the manuscript
*Technical approach / High-level controller*.

The torso-orientation task is modelled as the 2-state integrator

    x_{k+1} = x_k + u_k,     x = [phi_ROB, psi_ROB]^T

and an infinite-horizon discrete LQR tracks the HMD reference

    x* = [-phi_HMD, psi_HMD]^T

(the HMD pitch axis is opposite to the robot body-fixed pitch).

The locomotion task is independent: Quest thumbstick axes that exceed
``INPUT_TRESHOLD`` are mapped onto saturated heading-frame velocities
``(v_x, v_y, omega_z)``.

Built with ``do_mpc`` / CasADi so the Riccati gain is assembled at
construction time (``t_step = 0.05 s``, ``n_horizon = None``).
"""

import numpy as np
from casadi import *
import do_mpc
from matplotlib import rcParams
import matplotlib.pyplot as plt

# Dead zone on each Quest thumbstick axis (unitless, SDK range ~[-1, 1]).
INPUT_TRESHOLD = 0.5
# Saturated linear speed commanded when a stick leaves the dead zone.
VELOCITY_BASE_SPEED = 0.5  # m/s
# Saturated yaw rate commanded by the left stick.
VELOCITY_BASE_ANGULAR = 0.5  # rad/s


class Controller:
    """Parallel torso-orientation LQR and thumbstick locomotion mapper.

    Attributes
    ----------
    setpoints : numpy.ndarray, shape (2, 1)
        Latest HMD pitch/yaw reference used as the LQR ``xss``.
    model : do_mpc.model.LinearModel
        Discrete integrator :math:`x^+ = x + u`.
    lqr : do_mpc.controller.LQR
        Infinite-horizon regulator on ``model``.
    """

    def __init__(self):
        """Allocate the linear model and solve the discrete Riccati equation."""
        self.setpoints = np.array([[0], [0]])
        self.model = self.get_model()
        self.lqr = self.get_lqr(self.model)

    def get_model(self):
        """Build the 2-DoF discrete integrator used for torso tracking.

        Returns
        -------
        do_mpc.model.LinearModel
            State ``x`` and input ``u`` both in ``R^2``; RHS is ``x + u``,
            which matches ``A = B = I`` in the paper.
        """
        model_type = "discrete"
        model = do_mpc.model.LinearModel(model_type)
        _x = model.set_variable(var_type="_x", var_name="x", shape=(2, 1))
        _u = model.set_variable(var_type="_u", var_name="u", shape=(2, 1))
        x_next = _x + _u
        model.set_rhs("x", x_next)
        model.setup()
        return model

    def get_lqr(self, model, silence_solver=False):
        """Configure the infinite-horizon LQR.

        Cost matrices follow the manuscript implementation:

        * ``Q = 10 I_2`` (state / tracking error)
        * ``R = I_2`` (control effort)
        * ``delR = I_2`` (penalty on input increments)

        Parameters
        ----------
        model : do_mpc.model.LinearModel
            Output of :meth:`get_model`.
        silence_solver : bool, optional
            Unused; kept for API compatibility.

        Returns
        -------
        do_mpc.controller.LQR
        """
        lqr = do_mpc.controller.LQR(model)
        lqr.settings.t_step = 0.05
        lqr.settings.n_horizon = None  # infinite horizon
        Q = 10 * np.identity(2)
        R = np.identity(2)
        Rdelu = np.identity(2)
        lqr.set_objective(Q=Q, R=R)
        lqr.set_rterm(delR=Rdelu)
        lqr.setup()
        return lqr

    def get_setpoints(self, setpoints):
        """Store the HMD orientation reference.

        Parameters
        ----------
        setpoints : sequence of float
            ``[pitch_hmd, yaw_hmd, roll_hmd]``. Only the first two entries
            are used; roll is not controlled.
        """
        self.setpoints = np.array([[setpoints[0]], [setpoints[1]]])

    def get_simulator(self, model):
        """Optional do-mpc simulator, used only by the ``__main__`` demo.

        Parameters
        ----------
        model : do_mpc.model.LinearModel

        Returns
        -------
        do_mpc.simulator.Simulator
        """
        simulator = do_mpc.simulator.Simulator(model)
        params_simulator = {"t_step": 0.05}
        simulator.set_param(**params_simulator)
        simulator.setup()
        return simulator

    def get_touch_controls(self, setpoints):
        """Map Quest thumbsticks onto heading-frame velocities.

        The right stick drives ``v_x`` then ``v_y``; the left stick drives
        ``omega_z``. Each axis is zero inside the dead zone and otherwise
        clipped to ``±VELOCITY_BASE_SPEED`` or ``±VELOCITY_BASE_ANGULAR``.
        Sign flips on the Y and yaw axes match the HMD / heading-frame
        convention used on the Quest 2.

        Parameters
        ----------
        setpoints : sequence of float
            ``[stick_x, stick_y, stick_yaw]`` in ``[-1, 1]``.

        Returns
        -------
        list of float
            ``[v_x, v_y, omega_z]`` in m/s and rad/s.
        """
        touch_controls = []
        if abs(setpoints[0]) > INPUT_TRESHOLD:
            if setpoints[0] > 0:
                touch_controls.append(VELOCITY_BASE_SPEED)
            else:
                touch_controls.append(-VELOCITY_BASE_SPEED)
        else:
            touch_controls.append(0)

        if abs(setpoints[1]) > INPUT_TRESHOLD:
            if setpoints[1] > 0:
                touch_controls.append(-VELOCITY_BASE_SPEED)
            else:
                touch_controls.append(VELOCITY_BASE_SPEED)
        else:
            touch_controls.append(0)

        if abs(setpoints[2]) > INPUT_TRESHOLD:
            if setpoints[2] > 0:
                touch_controls.append(-VELOCITY_BASE_ANGULAR)
            else:
                touch_controls.append(VELOCITY_BASE_ANGULAR)
        else:
            touch_controls.append(0)

        return touch_controls

    def get_hmd_controls(self, measures):
        """Evaluate one LQR step for torso pitch/yaw.

        Parameters
        ----------
        measures : sequence of float
            Current robot orientation ``[yaw, pitch, roll]`` as returned
            by :meth:`spot_interface.SpotInterface.get_body_orientation`.
            The first two entries become the measured state ``x_k``.

        Returns
        -------
        list of float
            ``[u_yaw, u_pitch, 0.0]``. The trailing zero is a placeholder
            for unused roll so the vector concatenates cleanly with the
            three locomotion commands.
        """
        hmd_controls = []
        self.lqr.set_setpoint(xss=self.setpoints)
        x = np.array([[measures[0]], [measures[1]]])
        u = self.lqr.make_step(x)
        hmd_controls.append(round(u[0][0], 3))
        hmd_controls.append(round(u[1][0], 3))
        hmd_controls.append(0)
        return hmd_controls


if __name__ == "__main__":
    # Offline sanity plot: track a sinusoidal pitch/yaw reference.
    print(" LQR sample")
    controller = Controller()
    controller.simulator = controller.get_simulator(controller.model)
    x0 = np.array([[0], [0]])
    controller.simulator.x0 = x0
    for k in range(50):
        controller.lqr.set_setpoint(xss=np.array([[sin(k)], [cos(k)]]))
        u0 = controller.lqr.make_step(x0)
        y_next = controller.simulator.make_step(u0)
        x0 = y_next
    rcParams["axes.grid"] = True
    rcParams["font.size"] = 18
    fig, ax, graphics = do_mpc.graphics.default_plot(controller.lqr.data, figsize=(16, 9))
    graphics.plot_results()
    graphics.reset_axes()
    plt.show()
