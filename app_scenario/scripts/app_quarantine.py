#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import cv2
import threading
import traceback
import time
import yaml
import base64
import logging
import json
import rospy
import datetime
import dateutil.parser
import numpy
import urllib
import base64
import tf
import tf.transformations as transform
from tf.transformations import *
import transform as compass

from rade.modulebase import *
from rade.common import Node, ResponseInfo
from rade.utils import *

from geometry_msgs.msg import Point, Quaternion, Pose, PoseStamped
from workerbee_navigation.msg import MoveToActionGoal
from workerbee_msgs.msg import ActionState
from workerbee_platform_msgs.msg import MoveToDriverState
from sero_actions.msg import *
from sero_temperature_monitor.msg import *

class MyLoop(Loop):
    def on_create(self, event):
        self.robot_pose = Pose()
        self.location_doc = self.load_document("location")
        self.schedule_end_time = dateutil.parser.parse("23:00:00")
        self.location_name = "W_102"
        self.poi_list = None


        self.add_listener(self.make_node("{namespace}/quarantine/ui_ready"), self.)
        self.add_listener(self.make_node("{namespace}/quarantine/ui_finish"), self.)
        self.add_listener(self.make_node("{namespace}/workerbee_navigation/robot_pose"), self.)
        self.add_listener(self.make_node("{namespace}/sero_mobile/lpt"), self.)
        self.add_listener(self.make_node("{namespace}/sero_mobile/battery"), self.)

        return ResponseInfo()
    
    def on_resume(self, event):


        self.front_ui_ready = False
        # javascript로 구성된 front-end단이 python으로 구성된 back-end단의 실행 시간보다 빠르기 때문에 sleep을 걸어준다.
        while self.front_ui_ready == False:
            time.sleep(0.5)

        return ResponseInfo()

    def on_loop(self):
        '''
            [Scenario]
            1. app_event.py에서 schedule_end_time을 받아온다.
            2. docking station에서 undocking된 후, quarantine.js로 UI 시작을 호출한다.
            3. schedule_end_time이 끝날 때까지, location.yaml에 있는 poi 위치들을 반복해서 이동한다.
            4. schedule_end_time이 끝나면 charging 시나리오로 전환한다.
        '''

        if self.quarantine_finish == False:
            # 현재 시간이 schedule_end_time을 넘어갈 경우 quarantine 모듈 종료
            if self.schedule_end_time < datetime.datetime.now():
                pass

            else:
                if self.lpt_finish == False:
                    self.action_lpt()

                if self.front_ui_ready == False:
                    self.pub_ui()

                if self.check_next_poi == False:
                    pass

        return ResponseInfo()

    def on_puase(self, evnet):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()


__class = MyLoop
DOCUMENT_DIR = os.path.expanduser("~") + "/document/"

if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class,
            manifest_path=os.path.join(os.path.dirname(__file__), "app_quarantine.yaml"),
        )
    except:
        traceback.self.logger.info_exc()