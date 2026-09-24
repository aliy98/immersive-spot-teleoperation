``scripts/oculus_client.py``
============================

Windows MQTT bridge. Must run next to ``ZED Stereo Passthrough.exe``
because it reads the named pipe that process creates.

Module constants
----------------

.. py:data:: port
   :value: 1883

.. py:data:: topic
   :value: "oculus/inputs"

.. py:class:: OculusClient(broker_address)

   Starts a paho background loop and connects to ``broker_address:1883``.

   .. py:method:: on_connect(client, userdata, flags, rc)

      Print the CONNACK code.

.. py:function:: main(broker_address)
   :no-index:

   Open ``\\.\pipe\MyPipe`` in binary mode, ``struct.unpack('6f', 24
   bytes)``, ``json.dumps``, publish, sleep 50 ms. Closes the pipe and
   the MQTT client on ``KeyboardInterrupt``.
