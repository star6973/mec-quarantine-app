#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import traceback
import time
from datetime import datetime
import dateutil.parser
import urllib
from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from rade.utils import *
from geometry_msgs.msg import Point, Pose
from workerbee_navigation.msg import MoveToActionGoal
from workerbee_msgs.msg import ActionState
from workerbee_platform_msgs.msg import MoveToDriverState
from sero_actions.msg import *
from hri_msgs.msg import FaceDetectAndTrackActionGoal

FACE_TRACK_NEAREST_FACE = "look_nearest_face"

class MyLoop(Loop):
    def on_create(self, event):
        self.add_listener(self.make_node("{namespace}/quarantine/ui_ready"), self.on_front_ui_ready)

        return ResponseInfo()
    
    def on_resume(self, event):
        self.publish(self.make_node("{namespace}/robot_display/open_url"), {"content": "http://0.0.0.0:8080/quarantine.html?" + urllib.urlencode(event)})

        '''
            Read the required yaml file
        '''
        self.location_doc = self.load_document("quarantine_location")
        self.preference_doc = self.load_document("preferences")

        '''
            Parse info from app_event file
        '''
        self.schedule_end_time = dateutil.parser.parse(event["end_time"])
        self.target_loc = event["location"]

        '''
            Parse info from quarantine_location.yaml
        '''
        self.poi_list = self.get_poi_list_with_target_loc()

        '''
            Parse info from preference.yaml
        '''
        self.speed_first_poi = self.preference_doc["SPEED_FIRST_POI"]
        self.speed_rest_poi = self.preference_doc["SPEED_REST_POI"]
        self.disable_global_path_planning = self.preference_doc["DISABLE_GLOBAL_PATH_PLANNING"]
        self.disable_obstacle_avoidance_first_poi = self.preference_doc["DISABLE_OBSTACLE_AVOIDANCE_FIRST_POI"]
        self.disable_obstacle_avoidance_rest_poi = self.preference_doc["DISABLE_OBSTACLE_AVOIDANCE_REST_POI"]
        self.TRY_LPT_COUNT = self.preference_doc["TRY_LPT_COUNT"]
        self.TRY_DRIVE_COUNT = self.preference_doc["TRY_DRIVE_COUNT"]

        '''
            Flags for running the service
        '''
        self.finish_quarantine_flag = False
        self.finish_drive_flag = False
        self.finish_lpt_flag = False
        self.finish_pub_ui = False
        self.finish_first_moving = False

        '''
            Flags for others
        '''
        self.poi_idx = 0
        self.try_lpt_count = 0
        self.try_drive_count = 0
        self.front_ui_ready = False

        # javascript로 구성된 front-end단이 python으로 구성된 back-end단의 실행 시간보다 빠르기 때문에 sleep을 걸어준다.
        while self.front_ui_ready == False:
            time.sleep(0.5)
            self.front_ui_ready = True

        return ResponseInfo()

    '''
        [Scenario]
        1. schedule_end_time 범위 안에서
            1-1. docking station에서 undocking하기
            1-2. location.yaml에 있는 lpt 위치로 설정하기
            1-3. location.yaml에 있는 poi 위치로 이동하기
            1-4. quarantine.js UI로 호출하기
        2. schedule_end_time 범위 밖에서
            2-1. app_event로 전환하기
    '''
    def on_loop(self):
        if self.finish_quarantine_flag == False:
            if self.schedule_end_time < datetime.now():
                self.publish(self.make_node("{namespace}/robot_scenario/quarantine_finish"), {})
                self.finish_quarantine_flag = True
                self.publish(self.make_node("{namespace}/app_manager/idle"), {})

            else:
                if self.finish_drive_flag == False:
                    if self.try_drive_count < self.TRY_DRIVE_COUNT:
                        self.action_driving()
                    else:
                        self.logger.warning("DRIVING 액션 수행 실패")
                        self.finish_quarantine_flag = True

                if self.finish_first_moving == True:
                    if self.finish_lpt_flag == False:
                        if self.try_lpt_count < self.TRY_LPT_COUNT:
                            self.action_lpt()
                        else:
                            self.logger.warning("LPT 액션 수행 실패")
                            self.finish_quarantine_flag = True

                    if self.finish_pub_ui == False:
                        self.publish(
                            self.make_node("{namespace}/robot_scenario/quarantine_start"),
                            {
                                "service": "quarantine",
                                "state": "quarantine"
                            }
                        )
                        self.finish_pub_ui = True

                    if self.finish_drive_flag == False:
                        if self.try_drive_count < self.TRY_DRIVE_COUNT:
                            self.action_driving()
                        else:
                            self.logger.warning("DRIVING 액션 수행 실패")
                            self.finish_quarantine_flag = True
        
        return ResponseInfo()

    def on_pause(self, evnet):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    # quarantine.js에서 ui가 준비되었음을 알리는 콜백 함수
    def on_front_ui_ready(self, msg):
        self.front_ui_ready = True

    def get_poi_list_with_target_loc(self):
        for doc in self.location_doc:
            name = doc["name"]
            poi = doc["poi"]

            if name == self.target_loc:
                return poi

        self.logger.warning("Target Location과 일치하는 poi 값이 없음")
        return []

    def action_lpt(self):
        try:
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

            # Face Tracker Action
            msg = FaceDetectAndTrackActionGoal()
            msg.goal.origin_lift = target_lift
            msg.goal.origin_pan = target_pan
            msg.goal.origin_tilt = target_tilt
            msg.goal.strategy = FACE_TRACK_NEAREST_FACE

            action_node = self.make_node("{namespace}/face_tracker")
            gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

            self.finish_lpt_flag = True
        
        except Exception as e:
            self.logger.warning("LPT 액션 수행에서 문제 발생 = {}".format(e))
            self.try_lpt_count += 1

    def action_driving(self):
        try:
            if self.finish_first_moving == False:
                self.publish(
                    self.make_node("{namespace}/robot_scenario/quarantine_start"),
                    {
                        "service": "quarantine",
                        "state": "moving"
                    }
                )

            # poi 리스트가 한 개만 있는 경우
            if len(self.poi_list) == 1:
                self.poi_idx = 0
                self.finish_drive_flag = True

            # poi 리스트가 여러 개가 있는 경우
            if self.poi_idx >= len(self.poi_list):
                self.poi_idx = 0

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

            if self.finish_first_moving == False:
                msg.goal.speed = self.speed_first_poi
            else:
                msg.goal.speed = self.speed_rest_poi
            
            msg.goal.disable_global_path_planning = self.disable_global_path_planning
            msg.goal.patience_timeout = 30.0

            if self.finish_first_moving == False:
                msg.goal.disable_obstacle_avoidance = self.disable_obstacle_avoidance_first_poi
            else:
                msg.goal.disable_obstacle_avoidance = self.disable_obstacle_avoidance_rest_poi
            
            msg.goal.endless = False

            # moveto action node
            action_node = self.make_node("{namespace}/workerbee_navigation/moveto")
            gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

            # if action start, on_loop does not activate
            for process in gen:
                driver_state_code = process.body["state"]["driver_state"]["code"]
                action_state_code = process.body["state"]["action_state"]["code"]
                if driver_state_code > 1 or action_state_code != ActionState.NO_ERROR:
                    pass

            self.logger.info("Action Generate Result = {}\n".format(gen.result))

            # /workerbee_navigation/moveto/result 토픽 결과를 바탕으로 action 성공 유무 확인
            if gen.result.error == False:
                driver_state_code = gen.result.body["state"]["driver_state"]["code"]
                action_state_code = gen.result.body["state"]["action_state"]["code"]

                # 아래 조건들은 특수한 경우의 예외 조건
                if driver_state_code == MoveToDriverState.ERROR_PLANNER and action_state_code == ActionState.ERROR_DRIVER:
                    self.logger.warning("ERROR PLANNING\n")
                    self.try_drive_count += 1
                    time.sleep(2)

                elif driver_state_code != MoveToDriverState.NO_ERROR or action_state_code != ActionState.NO_ERROR:
                    self.try_drive_count += 1
                    time.sleep(2)

                else:
                    self.logger.info("Move to POI Success\n")

                    if self.poi_idx == 0:
                        self.finish_first_moving = True
                    
                    self.poi_idx += 1
                    self.try_drive_count = 0

            else:
                driver_state_code = gen.result.body["state"]["driver_state"]["code"]
                action_state_code = gen.result.body["state"]["action_state"]["code"]
                if driver_state_code == MoveToDriverState.NO_ERROR and action_state_code == ActionState.ERROR_FAULT:
                    self.logger.warning("LOCALIZATION FAULT\n")

                self.logger.warning("ERROR DRIVER\n")
                self.try_drive_count += 1

        except Exception as e:
            self.logger.warning("DRIVING 액션 수행에서 문제 발생 = {}".format(e))
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