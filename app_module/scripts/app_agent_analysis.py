#!/usr/bin/python
# -*- encoding: utf-8 coding: utf8 -*-#

import os
import signal
import cv2
import traceback
import base64
import json
import datetime
import requests
import numpy as np
import rospy
import requests
import ros_numpy
import uuid
import math
from rade.utils import *
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage, PointCloud2
from sensor_msgs.msg import PointCloud2
from pedestrian_detection.msg import Pedestrians
from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from sensor_msgs.msg import CompressedImage, Image, PointCloud2
from std_msgs.msg import String

class MyLoop(Loop):
    def on_create(self, event):
        return ResponseInfo()

    def on_resume(self, event):
        return ResponseInfo()

    def on_loop(self):
        return ResponseInfo()

    def on_pause(self, event):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

__class = MyLoop
if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class,
            manifest_path=os.path.join(
                os.path.dirname(__file__), "app_agent_analysis.yaml"
            ),
        )
    except:
        traceback.print_exc()