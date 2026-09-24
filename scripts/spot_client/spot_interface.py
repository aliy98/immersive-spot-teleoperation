#!/usr/bin/env python
"""Boston Dynamics Spot SDK facade used by the Jetson control thread.

The class owns lease, e-stop, power, state and command clients, stands
the robot at start-up, and exposes:

* :meth:`SpotInterface.set_controls` — apply LQR torso increments and
  heading-frame velocities through the black-box whole-body controller.
* :meth:`SpotInterface.get_body_orientation` — integrated pitch/yaw used
  as the LQR measurement.
* :meth:`SpotInterface.get_image` — optional stitched onboard cameras
  when ``image_source == "SPOT"``.

Attitude commands are saturated at ``MAX_PITCH`` / ``MAX_YAW``
(0.5 rad ≈ 0.52 rad in the paper). Velocity commands expire after
``VELOCITY_CMD_DURATION`` seconds so a dropped MQTT packet cannot leave
the robot walking.

Robot address and credentials are hard-coded for the payload LAN
(``10.0.0.3``). Change them before deploying on another platform.

Author: Ali Yousefi <ali.yousefi@edu.unige.it>
"""
import logging
import time
import cv2
import numpy as np
from scipy import ndimage

import bosdyn.api.spot.robot_command_pb2 as spot_command_pb2
import bosdyn.client.util
from bosdyn import geometry
from bosdyn.api import geometry_pb2, trajectory_pb2
from bosdyn.api.geometry_pb2 import SE2Velocity, SE2VelocityLimit, Vec2
from bosdyn.client import create_standard_sdk
from bosdyn.client.estop import EstopClient, EstopEndpoint, EstopKeepAlive
from bosdyn.client.lease import LeaseClient
from bosdyn.client.power import PowerClient
from bosdyn.client.robot_command import RobotCommandBuilder, RobotCommandClient, blocking_stand, blocking_sit
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.api import image_pb2
from bosdyn.client.image import ImageClient, build_image_request
from bosdyn.client.time_sync import TimedOutError

LOGGER = logging.getLogger()
VELOCITY_CMD_DURATION = 0.6  # seconds
MAX_YAW = 0.5
MAX_PITCH = 0.5
#MAX_ROLL = 0.5 


class SpotInterface:
    """SDK wrapper around Spot's whole-body controller.

    Parameters
    ----------
    image_source : str
        ``"ZED"`` uses the external stereo camera (no Spot image client).
        ``"SPOT"`` instantiates ``ImageClient`` plus a ``Stitch`` helper
        so :meth:`get_image` can publish the onboard pair.
    """
    def __init__(self, image_source):
        self._image_source = image_source
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._z = 0.0
        self._v_x = 0.0
        self._v_y = 0.0
        self._v_rot = 0.0
        self._powered_on = False
        self._estop_keepalive = None
        sdk = create_standard_sdk("spot_interface")
        self._robot = sdk.create_robot('10.0.0.3')
        self._robot.authenticate('user', 'wruzvkg4rce4')
        self._robot.sync_with_directory()
        self._robot.time_sync.wait_for_sync()
        self._lease_client = self._robot.ensure_client(LeaseClient.default_service_name)
        try:
            self._estop_client = self._robot.ensure_client(EstopClient.default_service_name)
            self._estop_endpoint = EstopEndpoint(self._estop_client, 'GNClient', 9.0)
        except:
            self._estop_client = None
            self._estop_endpoint = None
        self._power_client = self._robot.ensure_client(PowerClient.default_service_name)
        self._robot_state_client = self._robot.ensure_client(RobotStateClient.default_service_name)
        self._robot_command_client = self._robot.ensure_client(RobotCommandClient.default_service_name)
        if self._image_source == "SPOT":
            self._image_client = self._robot.ensure_client(ImageClient.default_service_name)
        self._start()
        
    
    def _toggle_estop(self):
        """
            Toggle estop on/off. Initial state is ON.
        """
        if self._estop_client is not None and self._estop_endpoint is not None:
            if not self._estop_keepalive:
                self._estop_keepalive = EstopKeepAlive(self._estop_endpoint)
            else:
                LOGGER.info('stopping estop')
                self._estop_keepalive.stop()
                self._estop_keepalive.shutdown()
                self._estop_keepalive = None
        
    def _orientation_cmd_helper(self, yaw=0.0, roll=0.0, pitch=0.0, height=0.0):
        """
            A helper function to set the robot attitude and height values.
            
            Args:
                yaw(float)
                roll(float)
                pitch(float)
                height(float)
        """
        orientation = geometry.EulerZXY(yaw, roll, pitch)
        cmd = RobotCommandBuilder.synchro_stand_command(body_height=height, footprint_R_body=orientation)
        self._robot_command_client.robot_command(lease=None, command=cmd, end_time_secs=time.time() + VELOCITY_CMD_DURATION)

    def _velocity_cmd_helper(self, v_x=0.0, v_y=0.0, v_rot=0.0):
        """
            A helper function to set the velocity values generated from the locomotion.
            
            Args:
                v_x(float)
                v_y(float)
                v_rot(float)
        """
        mobility_params = self._set_mobility_params()
        cmd = RobotCommandBuilder.synchro_velocity_command(v_x=v_x, v_y=v_y, v_rot=v_rot, params=mobility_params)
        self._robot_command_client.robot_command(lease=None, command=cmd, end_time_secs=time.time() + VELOCITY_CMD_DURATION)
        
    def _set_mobility_params(self):
        """
            Sets the required mobility parameters, including the obstacle avoidance, velocity limits, orientation offset between the robot 
            and footprint frames.

            Returns:
                mobility_params(spot_command_pb2.MobilityParams)
        """
        obstacles = spot_command_pb2.ObstacleParams(disable_vision_body_obstacle_avoidance=False,
                                                    disable_vision_foot_obstacle_avoidance=False,
                                                    disable_vision_foot_constraint_avoidance=False,
                                                    disable_vision_foot_obstacle_body_assist= False,
                                                    disable_vision_negative_obstacles=False,
                                                    obstacle_avoidance_padding=0.1)
        if self._v_x != 0 or self._v_y != 0 or self._v_rot != 0:
            self._yaw = 0
        footprint_R_body = geometry.EulerZXY(roll=0.0, pitch=self._pitch, yaw=self._yaw)
        position = geometry_pb2.Vec3(x=0.0, y=0.0, z=0.0)
        rotation = footprint_R_body.to_quaternion()
        pose = geometry_pb2.SE3Pose(position=position, rotation=rotation)
        point = trajectory_pb2.SE3TrajectoryPoint(pose=pose)
        traj = trajectory_pb2.SE3Trajectory(points=[point])
        body_control=spot_command_pb2.BodyControlParams(base_offset_rt_footprint=traj)
        speed_limit = SE2VelocityLimit(max_vel=SE2Velocity(linear=Vec2(x=1.0, y=1.0), angular=0.7))
        mobility_params = spot_command_pb2.MobilityParams(obstacle_params=obstacles, vel_limit=speed_limit, body_control=body_control, locomotion_hint=spot_command_pb2.HINT_AUTO)
        return mobility_params
    
    def get_body_vel(self):
        """
            Provides the angular velocity values of the robot base frame.

            Returns:
                measures([float])
        """
        robot_state = self._robot_state_client.get_robot_state()
        vis_vel_ang = robot_state.kinematic_state.velocity_of_body_in_vision.angular
        measures = [vis_vel_ang.z, vis_vel_ang.y, vis_vel_ang.x]
        return measures
    
    def get_body_orientation(self):
        """
            Provides the orientation values of the robot base frame.

            Returns:
                measures([float])
        """
        measures = [round(self._yaw, 3), round(self._pitch, 3), round(self._roll, 3)]
        return measures

    def set_controls(self, controls):
        """
            Sets the computed control signals on the robot base frame, using ``_velocity_cmd_helper()`` function.

            Args:
                controls([float])
        """
        dyaw = controls[0] 
        dpitch = controls[1] 
        #droll = controls[2] 

        self._yaw = self._yaw + dyaw
        self._pitch = self._pitch + dpitch
        #self._roll = self._roll + droll

        if self._yaw > MAX_YAW:
            self._yaw = MAX_YAW
        elif self._yaw < -MAX_YAW:
            self._yaw = -MAX_YAW
        if self._pitch > MAX_PITCH:
            self._pitch = MAX_PITCH
        elif self._pitch < -MAX_PITCH:
            self._pitch = -MAX_PITCH

        self._v_x = controls[3]
        self._v_y = controls[4]
        self._v_rot = controls[5]
        
        self._velocity_cmd_helper(v_x=self._v_x, v_y=self._v_y, v_rot=self._v_rot)
        
    def _start(self):
        """
            Takes the lease of the robot, powers on the motors, and makes the robot stand up.
        """
        if self._image_source == "SPOT":
            from stitch_images import Stitch
            self._stitch = Stitch(self._image_client)
        self._lease = self._lease_client.take()
        self._lease_keepalive = bosdyn.client.lease.LeaseKeepAlive(self._lease_client)
        if self._estop_endpoint is not None:
            self._estop_endpoint.force_simple_setup(
            )  # Set this endpoint as the robot's sole estop.
        self._toggle_estop()
        self._robot.power_on()
        self._powered_on=True
        time.sleep(5)
        blocking_stand(self._robot_command_client)
        time.sleep(5)
        LOGGER.info("ready to take commands")

    def shutdown(self):
        """
            Makes the robot to be configured with no orientation offsets, sit down, and powers off the motors.
        """
        self._orientation_cmd_helper(roll=0.0, pitch=0.0, yaw=0.0)
        time.sleep(5)
        blocking_sit(self._robot_command_client)
        time.sleep(5)
        safe_power_off_cmd=RobotCommandBuilder.safe_power_off_command()
        self._robot_command_client.robot_command(command= safe_power_off_cmd)
        time.sleep(2.5)
        self._powered_on=False
        LOGGER.info('Shutting down SpotInterface.')
        if self._estop_keepalive:
            # This stops the check-in thread but does not stop the robot.
            self._estop_keepalive.shutdown()
        if self._lease_keepalive:
            self._lease_keepalive.shutdown()

    def get_image(self):
        """Return one stitched onboard frame (only if ``image_source=="SPOT"``).

        Returns
        -------
        numpy.ndarray
            Grayscale image produced by the optional ``Stitch`` helper.
        """
        image = self._stitch.get_image()
        return image
        



