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

        # self.add_listener(self.make_node("{namespace}/quarantine/ui_ready"), self.)
        # self.add_listener(self.make_node("{namespace}/quarantine/ui_finish"), self.)
        # self.add_listener(self.make_node("{namespace}/workerbee_navigation/robot_pose"), self.)
        # self.add_listener(self.make_node("{namespace}/sero_mobile/lpt"), self.)
        # self.add_listener(self.make_node("{namespace}/sero_mobile/battery"), self.)

        return ResponseInfo()
    
    def on_resume(self, event):
        self.publish(self.make_node("{namespace}/robot_display/open_url"), {"content": "http://0.0.0.0:8080/quarantine.html?" + urllib.urlencode(event)})

        self.robot_pose = Pose()
        self.location_doc = self.load_document("location")
        self.schedule_end_time = dateutil.parser.parse("23:00:00")

        self.target_loc = "W_102"
        self.speed = None
        self.disable_global_path_planning = False
        self.finish_quarantine_flag = False
        self.finish_drive_flag = False
        self.poi_list = self.get_poi_list_with_target_loc()

        self.poi_idx = -1
        self.try_drive_count = 0
        self.TRY_DRIVE_COUNT = 5

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
            3. schedule_end_time이 끝나기 전까지, location.yaml에 있는 poi 위치들을 반복해서 이동한다.
            4. schedule_end_time이 끝나면 charging 시나리오로 전환한다.
        '''

        if self.finish_quarantine_flag == False:
            # 현재 시간이 schedule_end_time을 넘어갈 경우 quarantine 모듈 종료
            if self.schedule_end_time < datetime.datetime.now():
                pass

            else:
                # if self.finish_lpt_flag == False:
                #     self.action_lpt()

                if self.finish_drive_flag == False:
                    self.poi_idx += 1

                    # if self.front_ui_ready == False:
                    #     self.pub_ui()

                    if self.try_drive_count < self.TRY_DRIVE_COUNT:
                        self.move_to_poi()
                    else:
                        self.finish_quarantine_flag = True

        return ResponseInfo()

    def on_puase(self, evnet):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()


    def get_poi_list_with_target_loc(self):
        for doc in self.location_doc:
            name = doc["name"]
            poi = doc["poi"]

            if name == self.target_loc:
                return poi

        self.logger.info("Target Location과 일치하는 poi 값이 없음")
        # error

    def set_to_lpt(self):
        target_poi = self.poi_list[self.poi_idx]
        target_lift = target_poi["lpt"]["lift"]
        target_pan = target_poi["lpt"]["pan"]
        target_tilt = target_poi["lpt"]["tilt"]

        # target lpt값으로 액션 명령어 수행
        self.action_sync(
            self.make_node("{namespace}/sero_mobile/lpt_set_position"),
            {
                "lift": target_lift,
                "pan": target_pan,
                "tilt": target_tilt,
            },
        )

    def move_to_poi(self):
        pose = Pose()
        target_poi = self.poi_list[self.poi_idx]
        pose.position = Point(x=target_poi["pose"]["x"], y=target_poi["pose"]["y"], z=target_poi["pose"]["z"])
        pose.orientation.x = target_poi["orientation"]["x"]
        pose.orientation.y = target_poi["orientation"]["y"]
        pose.orientation.z = target_poi["orientation"]["z"]
        pose.orientation.w = target_poi["orientation"]["w"]

        self.logger.info("target poi pose = {}".format(pose))
        self.finish_drive_flag = True
        return

        # MoveToActionGoal Msg
        msg = MoveToActionGoal()
        msg.goal.goal.header.frame_id = "map"
        msg.goal.goal.pose = pose
        msg.goal.speed = self.speed
        msg.goal.disable_global_path_planning = self.disable_global_path_planning
        msg.goal.patience_timeout = 30.0
        msg.goal.disable_obstacle_avoidance = False
        msg.goal.endless = False

        # moveto action node
        action_node = self.make_node("{namespace}/workerbee_navigation/moveto")

        gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

        for process in gen:
            driver_state_code = process.body["state"]["driver_state"]["code"]
            action_state_code = process.body["state"]["action_state"]["code"]
            if driver_state_code > 1 or action_state_code != ActionState.NO_ERROR:
                pass

        self.logger.info("\n\n @@@@@ Action Generate Result = {}\n".format(gen.result))

        # /workerbee_navigation/moveto/result 토픽 결과를 바탕으로 action 성공 유무 확인
        if gen.result.error == False:
            driver_state_code = gen.result.body["state"]["driver_state"]["code"]
            action_state_code = gen.result.body["state"]["action_state"]["code"]

            # 아래 조건들은 특수한 경우의 예외 조건
            if driver_state_code == MoveToDriverState.ERROR_PLANNER and action_state_code == ActionState.ERROR_DRIVER:
                self.logger.error("\n\n @@@@@ ERROR PLANNING \n")
                self.drive_finish = False
                self.drive_error_count += 1
                time.sleep(2)

            elif driver_state_code != MoveToDriverState.NO_ERROR or action_state_code != ActionState.NO_ERROR:
                self.drive_finish = False
                self.drive_error_count += 1
                time.sleep(2)

            else:
                self.logger.info("\n\n @@@@@ Action Generate Result No Error \n")
                self.drive_finish = True
                self.drive_error_count = 0
                self.pub_moving()

        # ERROR
        else:
            driver_state_code = gen.result.body["state"]["driver_state"]["code"]
            action_state_code = gen.result.body["state"]["action_state"]["code"]
            if driver_state_code == MoveToDriverState.NO_ERROR and action_state_code == ActionState.ERROR_FAULT:
                self.logger.error("\n\n @@@@@ LOCALIZATION FAULT \n")

            self.logger.error("\n\n @@@@@ ERROR DRIVER \n")
            self.drive_finish = False
            self.drive_error_count += 1




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