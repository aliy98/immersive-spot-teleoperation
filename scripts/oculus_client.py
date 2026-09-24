#!/usr/bin/env python
"""Windows MQTT bridge between the Oculus C++ client and the cloud broker.

The OpenGL / Oculus process (``ZED Stereo Passthrough.exe``) writes a
packed record of six little-endian floats to the named pipe
``\\\\.\\pipe\\MyPipe`` at display rate:

    pitch, yaw, roll, stick_x, stick_y, stick_yaw

This script opens that pipe, unpacks each 24-byte record (``struct``
format ``6f``), serialises it as JSON and publishes it to MQTT topic
``oculus/inputs`` every 50 ms (20 Hz), which is the rate used in the
manuscript for the input thread.

Usage::

    python oculus_client.py <cloud-public-ip>
"""

import argparse
import struct
import paho.mqtt.client as mqtt
import json
import time

port = 1883
topic = "oculus/inputs"


class OculusClient:
    """Thin paho-mqtt publisher used on the operator PC.

    Parameters
    ----------
    broker_address : str
        Public IPv4 of the Mosquitto broker (same VM as MediaMTX).
    """

    def __init__(self, broker_address):
        self.broker_address = broker_address
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.connect(self.broker_address, port)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        """Log the CONNACK result code (0 = accepted)."""
        print("Connected with result code " + str(rc))


def main(broker_address):
    """Read the named pipe forever and publish JSON payloads.

    Parameters
    ----------
    broker_address : str
        Passed through to :class:`OculusClient`.
    """
    pipe_path = r'\\.\pipe\MyPipe'
    pipe = open(pipe_path, 'rb')
    oculus = OculusClient(broker_address)
    try:
        while True:
            data = pipe.read(24)
            received_tuple = struct.unpack('6f', data)
            inputs = list(received_tuple)
            payload = json.dumps(inputs)
            oculus.client.publish(topic, payload)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        pipe.close()
        oculus.client.loop_stop()
        oculus.client.disconnect()
        print("Oculus client disconnected.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Publish HMD/thumbstick samples to MQTT")
    parser.add_argument(
        'ip_address',
        type=str,
        nargs='?',
        default='34.16.188.15',
        help='The IP address of the MQTT broker'
    )
    args = parser.parse_args()
    main(args.ip_address)
