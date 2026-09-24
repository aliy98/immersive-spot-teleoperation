"""ZED 2 capture used by the Jetson streaming thread.

Frames are grabbed side-by-side at HD720 / 60 fps with depth disabled
(bandwidth), converted to grayscale and cropped to ``1280 x 240`` so the
HMD field of view matches the stock Spot tablet used in the user study.
"""

import sys
import pyzed.sl as sl
import cv2


class ZEDInterface:
    """Thin Stereolabs wrapper that yields FoV-matched grayscale frames.

    The output shape is exactly what ``stream_loop_zed`` encodes:
    ``GRAY8, 1280x240, 60 fps``.
    """

    def __init__(self):
        """Open the ZED 2 at HD720 / 60 fps, depth off."""
        self.zed = sl.Camera()
        input_type = sl.InputType()
        init = sl.InitParameters(input_t=input_type)
        init.camera_resolution = sl.RESOLUTION.HD720
        init.camera_fps = 60
        init.depth_mode = sl.DEPTH_MODE.NONE

        err = self.zed.open(init)
        if err != sl.ERROR_CODE.SUCCESS :
            print(repr(err))
            self.zed.close()
            exit(1)

        self.runtime = sl.RuntimeParameters()
        self.image_size_out = self.zed.get_camera_information().camera_configuration.resolution
        self.image_size_out.height = self.image_size_out.height/2
        self.image_zed_out = sl.Mat(self.image_size_out.width, self.image_size_out.height, sl.MAT_TYPE.U8_C4)

    def get_image(self):
        """Grab, convert RGBA side-by-side to gray, crop the tablet FoV.

        Returns
        -------
        numpy.ndarray or int
            ``(240, 1280)`` uint8 image on success, ``0`` on grab failure.
        """
        err = self.zed.grab(self.runtime)
        if err == sl.ERROR_CODE.SUCCESS:
            self.zed.retrieve_image(self.image_zed_out, sl.VIEW.SIDE_BY_SIDE, sl.MEM.CPU, self.image_size_out)
            image_ocv_out = self.image_zed_out.get_data()
            image = cv2.cvtColor(image_ocv_out, cv2.COLOR_RGBA2GRAY)
            x, y, w, h = 0, 120, 1280, 240  # Modify these values as needed
            cropped_roi = image[y:y+h, x:x+w]
            return cropped_roi

        else:
            print("error grabing image from zed")
            return 0


    def shutdown(self):
        """Close the Stereolabs session."""
        self.zed.close()
        print("\nShutting down ZEDInterface.")

