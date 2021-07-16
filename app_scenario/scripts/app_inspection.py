#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import traceback
import time
from datetime import datetime
import dateutil.parser
import urllib
from tf.transformations import *
from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from rade.utils import *
from geometry_msgs.msg import Point, Pose
from workerbee_navigation.msg import MoveToActionGoal
from workerbee_msgs.msg import ActionState
from workerbee_platform_msgs.msg import MoveToDriverState
from sero_actions.msg import *
from sero_temperature_monitor.msg import *
from hri_msgs.msg import FaceDetectAndTrackActionGoal

FACE_TRACK_NEAREST_FACE = "look_nearest_face"

class MyLoop(Loop):
    def on_create(self, event):
        self.add_listener(self.make_node("{namespace}/inspection/event/ui_ready"), self.on_front_ui_ready)
        self.add_listener(self.make_node("{namespace}/inspection/event/ui_finish"), self.on_front_ui_finish)
        self.add_listener(self.make_node("{namespace}/agent_analysis_data/analysis_ready"), self.on_agent_analysis_finish)

        return ResponseInfo()

    def on_resume(self, event):
        self.publish(self.make_node("{namespace}/robot_display/open_url"), {"content": "http://0.0.0.0:8080/inspection.html?" + urllib.urlencode(event)})

        '''
            Read the required yaml file
        '''
        self.location_doc = self.load_document("inspection_location")
        self.preference_doc = self.load_document("preferences")

        '''
            Parse info from app_event file
        '''
        self.schedule_end_time = dateutil.parser.parse(event["end_time"])
        self.target_gate = event["gate"]
        self.target_loc = event["location"]

        '''
            Parse info from inspection_location.yaml
        '''
        self.target_poi, self.target_lpt = self.get_poi_and_lpt_with_target_loc()

        '''
            Parse info from preference.yaml
        '''
        self.speed_rest_poi = self.preference_doc["SPEED_REST_POI"]
        self.disable_global_path_planning = self.preference_doc["DISABLE_GLOBAL_PATH_PLANNING"]
        self.disable_obstacle_avoidance_rest_poi = self.preference_doc["DISABLE_OBSTACLE_AVOIDANCE_REST_POI"]
        self.TRY_DRIVE_COUNT = self.preference_doc["TRY_DRIVE_COUNT"]
        self.TRY_LPT_COUNT = self.preference_doc["TRY_LPT_COUNT"]
        
        '''
            Flags for running the service
        '''
        self.finish_inspection_flag = False
        self.finish_drive_flag = False
        self.finish_lpt_flag = False

        '''
            Flags for others
        '''
        self.try_drive_count = 0
        self.try_lpt_count = 0

        self.ready_to_request_analysis = True
        self.front_ui_ready = False

        while self.front_ui_ready == False:
            time.sleep(0.5)
            self.front_ui_ready = True

        # restart rtsp stream node
        os.system("pm2 restart 4")

        return ResponseInfo()

    '''
        [Scenario]
        1. schedule_end_time 범위 안에서
            1-1. docking station에서 undocking하기
            1-2. location.yaml에 있는 poi 위치로 이동하기
            1-3. location.yaml에 있는 lpt 위치로 설정하기
            1-4. inspection.js UI로 호출하기
        2. schedule_end_time 범위 밖에서
            2-1. app_event로 전환하기
    '''
    def on_loop(self):
        if self.finish_inspection_flag == False:
            if self.schedule_end_time < datetime.now():
                self.finish_inspection_flag = True
                self.publish(self.make_node("{namespace}/app_manager/idle"), {})

            else:
                if self.finish_drive_flag == False:
                    if self.try_drive_count < self.TRY_DRIVE_COUNT:
                        self.action_driving()
                    else:
                        self.logger.warning("\n DRIVING 액션 수행 실패")
                        self.finish_inspection_flag = True
                
                if self.finish_drive_flag == True and self.finish_lpt_flag == False:
                    if self.try_lpt_count < self.TRY_LPT_COUNT:
                        self.action_lpt()
                    else:
                        self.logger.warning("\n LPT 액션 수행 실패")
                        self.finish_inspection_flag = True

                if self.finish_drive_flag == True and self.finish_lpt_flag == True:
                    self.action_service()

        return ResponseInfo()

    def on_pause(self, event):
        self.pause_flag = True
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    # inspection.js에서 ui가 준비되었음을 알리는 콜백 함수
    def on_front_ui_ready(self, msg):
        self.front_ui_ready = True

    # inspection.js에서 ui가 끝났음을 알리는 콜백 함수
    def on_front_ui_finish(self, msg):
        self.ready_to_request_analysis = True

    def on_agent_analysis_finish(self, msg):
        self.ready_to_request_analysis = True

    def get_poi_and_lpt_with_target_loc(self):
        for doc in self.location_doc["locations"]:
            if doc["name"] == self.target_loc:
                for gate in doc["gates"]:
                    if gate["name"] == self.target_gate:
                        return gate["pois"], gate["lpt"]

        self.logger.warning("\n Target Gate와 일치하는 pois와 lpt 값이 없음 \n")
        return [], []

    def action_driving(self):
        self.finish_drive_flag = True
        return

        try:
            pose = Pose()
            pose.position = Point(x=self.target_poi["pose"]["x"], y=self.target_poi["pose"]["y"], z=self.target_poi["pose"]["z"])
            pose.orientation.x = self.target_poi["orientation"]["x"]
            pose.orientation.y = self.target_poi["orientation"]["y"]
            pose.orientation.z = self.target_poi["orientation"]["z"]
            pose.orientation.w = self.target_poi["orientation"]["w"]

            # MoveToActionGoal Msg
            msg = MoveToActionGoal()
            msg.goal.goal.header.frame_id = "map"
            msg.goal.goal.pose = pose
            msg.goal.speed = self.speed_rest_poi
            msg.goal.disable_global_path_planning = self.disable_global_path_planning
            msg.goal.patience_timeout = 30.0
            msg.goal.disable_obstacle_avoidance = self.disable_obstacle_avoidance_rest_poi
            msg.goal.endless = False
            
            # moveto action node
            action_node = self.make_node("{namespace}/workerbee_navigation/moveto")
            gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

            for process in gen:
                driver_state_code = process.body["state"]["driver_state"]["code"]
                action_state_code = process.body["state"]["action_state"]["code"]
                if driver_state_code > 1 or action_state_code != ActionState.NO_ERROR:
                    pass

            self.logger.info("Action Generate Result = {}\n".format(gen.result))

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
                    self.logger.info("\n Move to POI Success \n")
                    
                    self.finish_drive_flag = True
                    self.try_drive_count = 0

            else:
                driver_state_code = gen.result.body["state"]["driver_state"]["code"]
                action_state_code = gen.result.body["state"]["action_state"]["code"]
                if driver_state_code == MoveToDriverState.NO_ERROR and action_state_code == ActionState.ERROR_FAULT:
                    self.logger.warning("LOCALIZATION FAULT\n")

                self.logger.warning("ERROR DRIVER\n")
                self.try_drive_count += 1

        except Exception as e:
            self.logger.warning("\n DRIVING 액션 수행에서 문제 발생 = {}".format(e))
            self.try_drive_count += 1

    def action_lpt(self):
        try:
            tl, tp, tt = float(self.target_lpt["lift"]), float(self.target_lpt["pan"]), float(self.target_lpt["tilt"])

            # target lpt값으로 액션 명령어 수행
            self.action_sync(
                self.make_node("{namespace}/sero_mobile/lpt_set_position"),
                {
                    "lift": tl,
                    "pan": tp,
                    "tilt": tt,
                },
            )

            # publish ui
            self.publish(
                self.make_node("{namespace}/robot_scenario/event"),
                {
                    "scenario": "inspection",
                    "state": "inspecting",
                    "end_time": self.schedule_end_time.isoformat()
                }
            )

            # Face Tracker Action
            msg = FaceDetectAndTrackActionGoal()
            msg.goal.origin_lift = tl
            msg.goal.origin_pan = tp
            msg.goal.origin_tilt = tt
            msg.goal.strategy = FACE_TRACK_NEAREST_FACE

            action_node = self.make_node("{namespace}/face_tracker")
            gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

            self.finish_lpt_flag = True

        except Exception as e:
            self.logger.warning("\n LPT 액션 수행에서 문제 발생 = {}".format(e))
            self.try_lpt_count += 1

    def action_service(self):
        if self.ready_to_request_analysis == True:
            self.logger.info("\n\nAction Start!!!")
            self.publish(self.make_node("{namespace}/agent_analysis_data/transfer_image"), {})
            self.ready_to_request_analysis = False

__class = MyLoop
DOCUMENT_DIR = os.path.expanduser("~") + "/document/"

if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class,
            manifest_path=os.path.join(os.path.dirname(__file__), "app_inspection.yaml"),
        )
    except:
        traceback.self.logger.info_exc()