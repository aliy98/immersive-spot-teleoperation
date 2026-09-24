``scripts/spot_client/spot_client.py``
======================================

Jetson process entry point. Starts a GStreamer publisher thread and an
MQTT control thread.

.. py:class:: SpotClient(broker_address, image_source)

   Robot-side MQTT subscriber and control-thread owner.

   :param str broker_address: Public IPv4 of the Mosquitto / MediaMTX VM.
   :param str image_source: ``"ZED"`` or ``"SPOT"``.

   .. py:attribute:: sub_topic
      :type: str
      :value: "oculus/inputs"

   .. py:attribute:: inputs
      :type: list[float]

      Latest HMD + thumbstick sample, mutated by :meth:`on_message`.

   .. py:attribute:: flag_connected
      :type: int

      ``1`` while the 4G probe succeeds; otherwise :meth:`reconnect` runs
      instead of :meth:`SpotInterface.set_controls`.

   .. py:method:: on_connect(client, userdata, flags, rc)

      Subscribe to ``oculus/inputs`` after CONNACK.

   .. py:method:: on_message(client, userdata, msg)

      ``json.loads`` the payload into :attr:`inputs`.

   .. py:method:: check_internet_connection()

      TCP connect to ``8.8.8.8:53`` with a 15 s timeout.
      Returns ``True`` if the probe succeeds.

   .. py:method:: reconnect()

      ``sudo systemctl restart simcom_wwan@wwan0.service`` then sleep 30 s.

   .. py:method:: control_loop()

      Forever:

      1. ``get_setpoints(inputs[0:3])`` — HMD reference.
      2. ``get_body_orientation()`` — integrated robot pitch/yaw.
      3. ``get_hmd_controls`` + ``get_touch_controls(inputs[3:6])``.
      4. ``set_controls(hmd + touch)`` if the uplink is up.

      ``KeyboardInterrupt`` sits the robot and closes MQTT.

.. py:function:: stream_loop_zed(broker_address, image_source)

   Open :class:`ZEDInterface` and a ``cv2.VideoWriter`` whose pipeline is
   the NVIDIA hardware encoder at 3 Mbit/s, ``GRAY8 1280×240 @ 60``.
   Writes every ``get_image()`` frame to MediaMTX over TCP.

.. py:function:: stream_loop_spot(broker_address, spot)

   Same idea using the onboard cameras via
   :meth:`SpotInterface.get_image`, ``960×640 @ 30``, 0.6 Mbit/s.

.. py:function:: main(broker_address, image_source)
   :no-index:

   Dispatch on ``image_source`` and start both threads.

CLI
---

.. code-block:: text

   python spot_client.py [ip_address] [image_source]

Defaults: ``34.16.188.15``, ``ZED``.
