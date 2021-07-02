#!/usr/bin/python
# -*- encoding: utf-8 coding: utf8 -*-#

import os
import io
import signal
import cv2
import threading
import traceback
import time
import yaml
import base64
import logging
import json
import urllib
import datetime
import dateutil.parser
import requests
import numpy as np
import rospy
import ast
import requests
import copy
from urlparse import urlsplit, parse_qs

from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from rade.utils import *

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
            manifest_path=os.path.join(os.path.dirname(__file__), "app_scheduler.yaml"),
        )
    except:
        traceback.print_exc()