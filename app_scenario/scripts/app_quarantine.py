#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import traceback
import time
import datetime
import dateutil.parser
import urllib

from rade.modulebase import *
from rade.common import ResponseInfo
from rade.utils import *

from geometry_msgs.msg import Point, Pose
from workerbee_navigation.msg import MoveToActionGoal
from workerbee_msgs.msg import ActionState
from workerbee_platform_msgs.msg import MoveToDriverState
from sero_actions.msg import *

class MyLoop(Loop):
    def on_create(self, event):
        self.logger.info("$$$ create quarantine!!!")

        self.add_listener(self.make_node("{namespace}/quarantine/ui_ready"), self.on_front_ui_ready)
        # self.add_listener(self.make_node("{namespace}/quarantine/ui_finish"), self.)
        # self.add_listener(self.make_node("{namespace}/workerbee_navigation/robot_pose"), self.)
        # self.add_listener(self.make_node("{namespace}/sero_mobile/lpt"), self.)
        # self.add_listener(self.make_node("{namespace}/sero_mobile/battery"), self.)

        return ResponseInfo()
    
    def on_resume(self, event):
        self.logger.info("$$$ resume quarantine!!!")
        self.publish(self.make_node("{namespace}/robot_display/open_url"), {"content": "http://0.0.0.0:8080/app_quarantine.html?" + urllib.urlencode(event)})

        self.robot_pose = Pose()
        self.location_doc = self.load_document("quarantine_location")

        self.logger.info("location_doc = ", self.location_doc)

        self.schedule_end_time = dateutil.parser.parse(event["end_time"])
        self.target_loc = event["location"]

        self.logger.info("schedule_end_time = ", self.schedule_end_time, type(self.schedule_end_time))
        self.logger.info("target_loc = ", self.target_loc, type(self.target_loc))

        self.speed = None
        self.disable_global_path_planning = False
        self.finish_quarantine_flag = False
        self.finish_drive_flag = False
        self.finish_lpt_flag = False
        self.poi_list = self.get_poi_list_with_target_loc()
        self.logger.info("poi list with target location = ", self.poi_list)

        self.poi_idx = 0
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
        self.logger.info("### loop quarantine!!!")

        if self.finish_quarantine_flag == False:
            self.logger.info(datetime.datetime.now())
            # 현재 시간이 schedule_end_time을 넘어갈 경우 quarantine 모듈 종료
            if self.schedule_end_time < datetime.datetime.now():
                self.logger.info("현재 시간이 schedule_end_time을 넘어갈 경우")
                pass

            else:
                self.logger.info("Start QUARANTINE!!!!!!!!!!!")
                if self.finish_lpt_flag == False:
                    self.set_to_lpt()

                if self.finish_drive_flag == False:
                    
                    self.logger.info("poi idx = ", self.poi_idx)

                    # if self.front_ui_ready == False:
                    #     self.pub_ui()

                    if self.try_drive_count < self.TRY_DRIVE_COUNT:
                        self.logger.info("Start Drive poi!!!!")
                        self.move_to_poi()

                    else:
                        self.finish_quarantine_flag = True

        return ResponseInfo()

    def on_pause(self, evnet):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    def on_front_ui_ready(self, msg):
        self.front_ui_ready = True


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

        self.logger.info("\n\n @@@@@ 타겟 LPT 값들 = {}, {}, {}\n".format(target_lift, target_pan, target_tilt))

        # target lpt값으로 액션 명령어 수행
        self.action_sync(
            self.make_node("{namespace}/sero_mobile/lpt_set_position"),
            {
                "lift": target_lift,
                "pan": target_pan,
                "tilt": target_tilt,
            },
        )

        self.finish_lpt_flag = True

    def move_to_poi(self):

        if self.poi_idx >= len(self.poi_list):
            self.logger.info("All poi Finish!!")
            self.finish_quarantine_flag = True
            return

        pose = Pose()

        target_poi = self.poi_list[self.poi_idx]
        pose.position = Point(x=target_poi["pose"]["x"], y=target_poi["pose"]["y"], z=target_poi["pose"]["z"])
        pose.orientation.x = target_poi["orientation"]["x"]
        pose.orientation.y = target_poi["orientation"]["y"]
        pose.orientation.z = target_poi["orientation"]["z"]
        pose.orientation.w = target_poi["orientation"]["w"]

        # MoveToActionGoal Msg
        msg = MoveToActionGoal()
        msg.goal.goal.header.frame_id = "map"
        msg.goal.goal.pose = pose
        msg.goal.speed = 0.2
        msg.goal.disable_global_path_planning = False
        msg.goal.patience_timeout = 30.0
        msg.goal.disable_obstacle_avoidance = False
        msg.goal.endless = False

        # moveto action node
        action_node = self.make_node("{namespace}/workerbee_navigation/moveto")

        gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

        # doing action loop not activate
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
                self.finish_drive_flag = False
                self.try_drive_count += 1
                time.sleep(2)

            elif driver_state_code != MoveToDriverState.NO_ERROR or action_state_code != ActionState.NO_ERROR:
                self.finish_drive_flag = False
                self.try_drive_count += 1
                time.sleep(2)

            else:
                self.logger.info("\n\n @@@@@ Action Generate Result No Error \n")
                self.finish_drive_flag = False
                self.try_drive_count = 0
                self.poi_idx += 1

        # ERROR
        else:
            driver_state_code = gen.result.body["state"]["driver_state"]["code"]
            action_state_code = gen.result.body["state"]["action_state"]["code"]
            if driver_state_code == MoveToDriverState.NO_ERROR and action_state_code == ActionState.ERROR_FAULT:
                self.logger.error("\n\n @@@@@ LOCALIZATION FAULT \n")

            self.logger.error("\n\n @@@@@ ERROR DRIVER \n")
            self.finish_drive_flag = False
            self.try_drive_count += 1


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