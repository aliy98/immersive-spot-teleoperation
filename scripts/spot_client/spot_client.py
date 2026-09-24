#!/usr/bin/env python
"""Jetson entry point: MQTT control loop + GStreamer/RTSP publisher.

Usage::

    python spot_client.py <cloud-public-ip> ZED
"""

import argparse
import cv2
import json
import paho.mqtt.client as mqtt
import threading
import numpy as np
import socket
import os
import time
from spot_interface import SpotInterface
from zed_interface import ZEDInterface
from spot_controller import Controller


class SpotClient:
    """Robot-side MQTT subscriber and control-thread owner.

    Parameters
    ----------
    broker_address : str
        Public IPv4 of the Mosquitto / MediaMTX virtual machine.
    image_source : str
        ``"ZED"`` or ``"SPOT"``; forwarded to SpotInterface.

    Notes
    -----
    self.inputs is a six-float list updated by the MQTT callback:
    [pitch, yaw, roll, stick_x, stick_y, stick_yaw].
    """

    def __init__(self, broker_address, image_source):
        self.broker_address = broker_address
        self.image_source = image_source
        self.sub_topic = "oculus/inputs"
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_address, 1883)
        self.client.loop_start()
        self.interface = SpotInterface(self.image_source)
        self.controller = Controller()
        self.inputs = [0, 0, 0, 0, 0, 0]
        self.flag_connected = 1

    def on_connect(self, client, userdata, flags, rc):
        """Subscribe to oculus/inputs once the broker accepts the session."""
        print("Connected with result code " + str(rc))
        client.subscribe(self.sub_topic)

    def on_message(self, client, userdata, msg):
        """Decode the JSON payload into inputs."""
        payload = msg.payload.decode()
        self.inputs = json.loads(payload)

    def check_internet_connection(self):
        """Return True if a TCP socket to 8.8.8.8:53 succeeds within 15 s."""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=15)
            return True
        except OSError:
            return False

    def reconnect(self):
        """Restart the SIM7600 wwan0 systemd unit and wait 30 s."""
        os.system("sudo systemctl restart simcom_wwan@wwan0.service")
        time.sleep(30)

    def control_loop(self):
        """Blocking loop: LQR torso + dead-zone locomotion + SDK apply."""
        try:
            while True:
                hmd_inputs = self.inputs[0:3]
                self.controller.get_setpoints(hmd_inputs)
                touch_inputs = self.inputs[3:6]
                spot_measures = self.interface.get_body_orientation()
                print(spot_measures)
                hmd_controls = self.controller.get_hmd_controls(spot_measures)
                touch_controls = self.controller.get_touch_controls(touch_inputs)
                controls = hmd_controls + touch_controls
                if self.flag_connected:
                    self.interface.set_controls(controls)
                else:
                    self.reconnect()
                self.flag_connected = self.check_internet_connection()
        except KeyboardInterrupt:
            pass
        finally:
            self.interface.shutdown()
            self.client.loop_stop()
            self.client.disconnect()
            print("Spot Client disconnected.")


def stream_loop_zed(broker_address, image_source):
    """Publish ZED frames through the NVIDIA H.264 GStreamer pipeline."""
    zed = ZEDInterface()
    pipeline = 'appsrc ! videoconvert ! videoscale ! video/x-raw,format=GRAY8,width=1280,height=240,framerate=60/1 ! nvvidconv ! \
                            nvv4l2h264enc bitrate=3000000 ! video/x-h264, \
                            stream-format=byte-stream ! \
                            rtspclientsink protocols=tcp location=rtsp://%s:8554/spot-stream' % broker_address
    image_size = (1280, 240)

    out_send = cv2.VideoWriter(pipeline, cv2.CAP_GSTREAMER, 0, 60, image_size, False)
    if not out_send.isOpened():
        print('VideoWriter not opened')
        exit(0)
    print("\n *** Launched RTSP Streaming at rtsp://%s:8554/spot-stream ***\n\n" % broker_address)

    try:
        key = ' '
        while True:
            image = zed.get_image()
            out_send.write(image)
            key = cv2.waitKey(10)
    except KeyboardInterrupt:
        pass
    finally:
        zed.shutdown()


def stream_loop_spot(broker_address, spot):
    """Publish stitched onboard cameras (960x640 @ 30 fps, 0.6 Mbit/s)."""
    pipeline = 'appsrc ! videoconvert ! videoscale ! video/x-raw,format=GRAY8,width=960,height=640,framerate=30/1 ! nvvidconv ! \
                            nvv4l2h264enc bitrate=600000 ! video/x-h264, \
                            stream-format=byte-stream ! \
                            rtspclientsink protocols=tcp location=rtsp://%s:8554/spot-stream' % broker_address
    image_size = (960, 640)

    out_send = cv2.VideoWriter(pipeline, cv2.CAP_GSTREAMER, 0, 30, image_size, False)
    if not out_send.isOpened():
        print('VideoWriter not opened')
        exit(0)
    print("\n *** Launched RTSP Streaming at rtsp://%s:8554/spot-stream ***\n\n" % broker_address)

    try:
        key = ' '
        while True:
            image = spot.interface.get_image()
            out_send.write(image)
            key = cv2.waitKey(10)
    except KeyboardInterrupt:
        pass


def main(broker_address, image_source):
    """Start the streaming thread then the control thread."""
    if image_source == 'ZED':
        stream_thread = threading.Thread(target=stream_loop_zed, args=(broker_address, image_source))
        stream_thread.start()
        spot = SpotClient(broker_address, image_source)
        control_thread = threading.Thread(target=spot.control_loop)
        control_thread.start()
    elif image_source == 'SPOT':
        spot = SpotClient(broker_address, image_source)
        stream_thread = threading.Thread(target=stream_loop_spot, args=(broker_address, spot))
        stream_thread.start()
        control_thread = threading.Thread(target=spot.control_loop)
        control_thread.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Send video stream to RTSP server")
    parser.add_argument(
        'ip_address',
        type=str,
        nargs='?',
        default='34.16.188.15',
        help='The IP address of the RTSP server'
    )
    parser.add_argument(
        'image_source',
        type=str,
        nargs='?',
        default='ZED',
        help='The image source for visual feedback from robot'
    )

    args = parser.parse_args()
    main(args.ip_address, args.image_source)
