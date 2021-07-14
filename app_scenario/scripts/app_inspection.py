#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import traceback
import time
import datetime
import dateutil.parser
import urllib
from tf.transformations import *
from rade.modulebase import *
from rade.common import ResponseInfo
from rade.utils import *
from geometry_msgs.msg import Point, Pose
from workerbee_navigation.msg import MoveToActionGoal
from workerbee_msgs.msg import ActionState
from workerbee_platform_msgs.msg import MoveToDriverState
from sero_actions.msg import *
from sero_temperature_monitor.msg import *
from hri_msgs.msg import FaceDetectAndTrackActionGoal
class MyLoop(Loop):
    def on_create(self, event):
        self.robot_pose = Pose()
        self.master_poi_doc = self.load_document("master_poi")

        self.schedule_end_time = dateutil.parser.parse("20:00:00")
        self.schedule_gate = "253"

        self.is_agent_analysis_send = False
        self.scenario_finish = False
        self.drive_finish = False
        self.lpt_finish = False
        self.mode_finish = False
        self.lpt_restore_finish = False
        self.pause_flag = False

        self.loc_name = "W_102"
        self.speed = 0.2
        self.disable_global_path_planning = False
        self.gates = []
        
        self.cur_battery = 100

        self.cur_lift = 0
        self.cur_pan = 0
        self.cur_tilt = 0

        self.target_lift = 0
        self.target_pan = 0
        self.target_tilt = 0

        self.cur_lift_complete = False
        self.cur_pan_complete = False
        self.cur_tilt_complete = False

        self.lift_min_margin = 0
        self.pan_min_margin = 0
        self.tilt_min_margin = 0

        self.lift_max_margin = 0
        self.pan_max_margin = 0
        self.tilt_max_margin = 0

        self.drive_error_count = 0
        self.lpt_error_count = 0
        self.mode_error_count = 0

        self.add_listener(self.make_node("{namespace}/inspection/event/ui_ready"), self.on_ui_ready)
        self.add_listener(self.make_node("{namespace}/inspection/ui_finished"), self.on_ui_finish)
        self.add_listener(self.make_node("{namespace}/workerbee_navigation/robot_pose"), self.on_robot_pose)
        self.add_listener(self.make_node("{namespace}/sero_mobile/lpt"), self.on_lpt_pose)
        self.add_listener(self.make_node("{namespace}/sero_mobile/battery"), self.on_battery_status)
        self.add_listener(self.make_node("{namespace}/agent_analysis_data/event_result_data"), self.on_agent_analysis_event_result)

        return ResponseInfo()

    def on_resume(self, event):
        self.logger.info("\n\n Resumed Inspection Module \n\n")
        self.publish(self.make_node("{namespace}/robot_display/open_url"), {"content": "http://0.0.0.0:8080/inspection.html?" + urllib.urlencode(event)})

        self.robot_pose = Pose()
        self.master_poi_doc = self.load_document("master_poi")

        # idle이 던져주는 schedule 정보들
        self.event = event
        self.schedule_end_time = dateutil.parser.parse(self.event["end_time"])
        self.schedule_gate = self.event["gate"]
        self.loc_name = self.event["location"]
        self.logger.info("\n\n schedule_end_time = {}, schedule_gate = {} \n\n".format(self.schedule_end_time.isoformat(), self.schedule_gate))

        self.is_agent_analysis_send = False
        self.scenario_finish = False
        self.drive_finish = False
        self.lpt_finish = False
        self.mode_finish = False
        self.lpt_restore_finish = False
        self.pause_flag = False

        self.speed, self.disable_global_path_planning, self.gates = self.get_info_from_master_poi()
        self.logger.info("\n\n Gate pois from master poi = {} \n\n".format(self.gates))

        self.cur_battery = 100

        self.cur_lift = 0
        self.cur_pan = 0
        self.cur_tilt = 0

        self.target_lift = 0
        self.target_pan = 0
        self.target_tilt = 0

        self.cur_lift_complete = False
        self.cur_pan_complete = False
        self.cur_tilt_complete = False

        self.lift_min_margin = 0
        self.pan_min_margin = 0
        self.tilt_min_margin = 0

        self.lift_max_margin = 0
        self.pan_max_margin = 0
        self.tilt_max_margin = 0

        self.drive_error_count = 0
        self.lpt_error_count = 0
        self.mode_error_count = 0

        self._is_ui_ready = False
        while self._is_ui_ready == False:
            time.sleep(0.5)

        os.system("pm2 restart 4")    

        return ResponseInfo()

    def on_loop(self):
        self.logger.info("\n\n Loop Inspection Module \n\n")

        if self.scenario_finish == False:
            '''
                시나리오 종료 case
                1. 스케줄 종료 시간을 넘긴 경우
                2. 모든 동작을 완료한 경우
            '''
            if self.schedule_end_time < datetime.datetime.now() or (self.drive_finish == True and self.lpt_finish == True and self.mode_finish == True and self.lpt_restore_finish == False):
                self.logger.info("\n\n Start to restore LPT \n\n")
                if self.lpt_error_count < LPT_SET_TRY_COUNT:
                    self.logger.info("\n\n Current LPT error count = {} \n".format(self.lpt_error_count))
                    self.set_to_lpt("restore")
                else:
                    self.logger.warning("\n\n Fail to restore LPT \n")
                    self.scenario_finish = True
                    self.pub_error_lpt()

                if self.lpt_restore_finish == True:
                    self.logger.info("\n\n Success to restore LPT && Pub Idle \n")
                    self.scenario_finish = True
                    self.pub_idle() # 정기 스케줄의 경우 idle을 직접 호출해야 함.
            else:
                ### Logic 1 - Move to POI
                if self.drive_finish == False:
                    self.logger.info("\n\n Start to navigate POI \n")
                    if self.drive_error_count < DRIVING_TRY_COUNT:
                        self.logger.info("\n\n Current MoveTo error count = {} \n".format(self.drive_error_count))
                        self.move_to_poi()
                    else:
                        self.logger.error("\n\n Fail to navigate POI \n")
                        self.scenario_finish = True
                        self.pub_error_drive()
                
                ### Logic 2 - Start to set LPT in POI
                if self.drive_finish == True and self.lpt_finish == False:
                    self.logger.info("\n\n Start to setting LPT \n")
                    if self.lpt_error_count < LPT_SET_TRY_COUNT:
                        self.logger.info("\n\n Current Setting error count = {} \n".format(self.lpt_error_count))
                        self.set_to_lpt("setting")
                    else:
                        self.logger.error("\n\n Fail to setting LPT \n")
                        self.scenario_finish = True
                        self.pub_error_lpt()

                ### Logic 3 - Start to excute mode
                if self.drive_finish == True and self.lpt_finish == True and self.mode_finish == False:
                    self.logger.info("\n\n Start to excute mode \n")
                    if self.mode_error_count < MODE_SET_TRY_COUNT:
                        self.logger.info("\n\n Current Excute Mode error count = {} \n".format(self.mode_error_count))
                        self.execute_to_mode()
                    else:
                        self.logger.error("\n\n Fail to excute mode \n")
                        self.scenario_finish = True
                        self.pub_error_mode()
        else:
            self.logger.info("\n\n Inspcection Scenario End \n\n")

        return ResponseInfo()

    ### Subscriber Function 1
    def on_ui_ready(self, msg):
        self._is_ui_ready = True

    ### Subscriber Function 2
    def on_robot_pose(self, res):
        try:
            self.robot_pose = convert_dictionary_to_ros_message("geometry_msgs/Pose", res.body["pose"])
        except:
            self.logger.error(traceback.format_exc())

    ### Subscriber Function 3
    def on_lpt_pose(self, res):
        self.cur_lift = float(res.body["lift_pos"])
        self.cur_pan = float(res.body["pan_pos"])
        self.cur_tilt = float(res.body["tilt_pos"])

    ### Subscriber Function 4
    def on_battery_status(self, res):
        self.cur_battery = res.body["batteries"][0]["voltage_level"]

    ### Subscriber Function 5
    def on_agent_analysis_event_result(self, res):
        event_result_status = res.body["status"]
        event_result_data = res.body["event_result"]

        #self.logger.info("\n\n @@@@@ 영상 분석 서버에서 받은 응답 상태 = {}, 데이터 = {} \n\n".format(event_result_status, event_result_data))
        #self.logger.info("status type = {}, data type = {}".format(type(event_result_status), type(event_result_data)))
        data = {}
        # 감지가 된 경우, UI에 pub
        if event_result_status == unicode("ok", "utf-8"):

            if event_result_data["high_temp"] == True:
                self.logger.info("\n\n @@@@@ 영상 분석 서버 데이터에서 고온 감지됨 \n")
                
                data["state"] = "mode_temperature"  
                data["event_result"] = event_result_data
                self.publish(self.make_node("{namespace}/robot_scenario/event"), data)

            # if "mask" in event_result_data.keys():
            #     if event_result_data["mask"] != []:
            #         self.logger.info("\n\n @@@@@ 영상 분석 서버 데이터에서 마스크 감지됨 \n")
            #         self.logger.info("@@@@@ 마스크 감지 데이터 : ", event_result_data)
                    
            #         data["state"] = "mode_mask"
            #         data["event_result"] = event_result_data
            #         self.logger.info("Mask Data Event Result = {}".format(data["event_result"]))
            #         self.publish(self.make_node("{namespace}/robot_scenario/event"), data)

            # if "distance" in event_result_data.keys():
            #     if event_result_data["distance"] == True:
            #         self.logger.info("\n\n @@@@@ 영상 분석 서버 데이터에서 distance 감지됨 \n")
            #         self.logger.info("@@@@@ distance 감지 데이터 : ", event_result_data)
                    
            #         data["state"] = "mode_distance"
            #         data["event_result"] = event_result_data
            #         self.logger.info("Distance Data Event Result = {}".format(data["event_result"]))
            #         self.publish(self.make_node("{namespace}/robot_scenario/event"), data)


            ###############
            elif event_result_data["mask"] != []:
                self.logger.info("\n\n @@@@@ 영상 분석 서버 데이터에서 마스크 감지됨 \n")
                self.logger.info("@@@@@ 마스크 감지 데이터 : ", event_result_data)
                
                data["state"] = "mode_mask"
                data["event_result"] = event_result_data
                self.logger.info("Mask Data Event Result = {}".format(data["event_result"]))
                self.publish(self.make_node("{namespace}/robot_scenario/event"), data)

            # elif event_result_data["distance"] == True:
            #     self.logger.info("\n\n @@@@@ 영상 분석 서버 데이터에서 distance 감지됨 \n")
            #     self.logger.info("@@@@@ distance 감지 데이터 : ", event_result_data)
                
            #     data["state"] = "mode_distance"
            #     data["event_result"] = event_result_data
            #     self.logger.info("Distance Data Event Result = {}".format(data["event_result"]))
            #     self.publish(self.make_node("{namespace}/robot_scenario/event"), data)



            self.logger.info("Passed")

            # TODO distance 경우 작성하기

        # 감지가 되지 않은 경우, 다시 쏘기
        else:
            ######## TODO 질문 2 - 왜 sleep 0.7초
            #time.sleep(0.7)
            self.is_agent_analysis_send = False

    ### Subscriber Function 6
    def on_ui_finish(self, res):
        self.is_agent_analysis_send = False
        self.logger.info("\n@@@@@@@@@ Get UI Finished Message!!")

    ### Publisher Function 1
    def pub_idle(self):
        self.publish(
            self.make_node("{namespace}/app_manager/idle"), {}
        )

    ### Publisher Function 2
    def pub_moving(self):
        self.publish(
            self.make_node("{namespace}/robot_scenario/event"),
            {
                "scenario": "inspection", 
                "state": "moving"
            }
        )

    ### Publisher Function 3
    def pub_setting_lpt(self):
        self.publish(
            self.make_node("{namespace}/robot_scenario/event"),
            {
                "scenario": "inspection",
                "state": "inspecting",
                "end_time": self.schedule_end_time.isoformat()
            }
        )

    ### Publisher Function 4
    def pub_error_drive(self):
        self.publish(
            self.make_node("{namespace}/app_manager/error_service"), 
            {
                "service": "inspection",
                "message": "drive_fail"
            }
        )

    ### Publisher Function 5
    def pub_error_lpt(self):
        self.publish(
            self.make_node("{namespace}/app_manager/error_service"), 
            {
                "service": "inspection",
                "message": "lpt_fail",
                "lift_status": self.cur_lpt_status[0],
                "pan_status": self.cur_lpt_status[1],
                "tilt_status": self.cur_lpt_status[2],
            }
        )

    ### Publisher Function 6
    def pub_error_mode(self):
        self.publish(
            self.make_node("{namespace}/app_manager/error_service"),
            {
                "service": "inspection",
                "message": "mode_fail"
            }
        )

    ### Get POI Function
    def get_info_from_master_poi(self):
        for i in range(len(self.master_poi_doc)):
            locations = self.master_poi_doc[i]["locations"]
            for loc_data in locations:
                if loc_data["name"] == self.loc_name:
                    speed = loc_data["speed"]
                    disable_global_path_planning = loc_data["disable_global_path_planning"]
                    gates = loc_data["gates"]

                    return speed, disable_global_path_planning, gates

    ### Move POI Function
    def move_to_poi(self):
        pose = Pose()
        for target_gate in self.gates:
            if target_gate["name"] == self.schedule_gate:
                pose.position = Point(x=target_gate["pose"]["x"], y=target_gate["pose"]["y"], z=target_gate["pose"]["z"])
                pose.orientation.x = target_gate["orientation"]["x"]
                pose.orientation.y = target_gate["orientation"]["y"]
                pose.orientation.z = target_gate["orientation"]["z"]
                pose.orientation.w = target_gate["orientation"]["w"]


        # self.drive_finish = True
        # return

        # MoveToActionGoal 메시지 작성
        msg = MoveToActionGoal()
        msg.goal.goal.header.frame_id = "map"
        msg.goal.goal.pose = pose

        if self.speed is None:
            msg.goal.speed = DEFAULT_SPEED
        else:
            msg.goal.speed = self.speed

        if self.disable_global_path_planning is None:
            msg.goal.disable_global_path_planning = DEFAULT_GLOBAL_PATH
        else:
            msg.goal.disable_global_path_planning = self.disable_global_path_planning

        msg.goal.patience_timeout = 30.0
        msg.goal.disable_obstacle_avoidance = False
        msg.goal.endless = False

        self.logger.info("\n\n @@@@@ Moveto POI Action Msg = {} \n".format(msg))

        action_node = self.make_node("{namespace}/workerbee_navigation/moveto")
        gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

        for process in gen:
            driver_state_code = process.body["state"]["driver_state"]["code"]
            action_state_code = process.body["state"]["action_state"]["code"]
            if driver_state_code > 1 or action_state_code != ActionState.NO_ERROR:
                pass

        self.logger.info("\n\n @@@@@ Action Generate Result = {}\n".format(gen.result))

        # NO ERROR
        if gen.result.error == False:
            driver_state_code = gen.result.body["state"]["driver_state"]["code"]
            action_state_code = gen.result.body["state"]["action_state"]["code"]

            # 아래 조건들은 특수한 경우
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

    ### Set POI Function
    def set_to_lpt(self, mod):
        for target_gate in self.gates:
            if target_gate["name"] == self.schedule_gate:
                if mod == "setting":
                    target_gate_lpt = target_gate["lpt"][0]
                    self.target_lift = float(target_gate_lpt["lift"])
                    self.targe_pan = float(target_gate_lpt["pan"])
                    self.targe_tilt = float(target_gate_lpt["tilt"])
                else:
                    self.target_lift = 0
                    self.targe_pan = 0
                    self.targe_tilt = 0

                self.logger.info("\n\n @@@@@ 타겟 LPT 값들 = {}, {}, {}\n".format(self.target_lift, self.target_pan, self.targe_tilt))

                # target lpt값으로 액션 명령어 수행
                self.action_sync(
                    self.make_node("{namespace}/sero_mobile/lpt_set_position"),
                    {
                        "lift": self.target_lift,
                        "pan": self.targe_pan,
                        "tilt": self.targe_tilt,
                    },
                )

                self.pub_setting_lpt()

                # lpt 조정 중 발화 시간을 맞추기 위한 sleep
                # time.sleep(10)

                self.cur_lift_complete = False
                self.cur_pan_complete = False
                self.cur_tilt_complete = False

                self.lift_min_margin = self.target_lift - LIFT_MARGIN
                self.pan_min_margin = self.target_pan - PAN_MARGIN
                self.tilt_min_margin = self.target_tilt - TILT_MARGIN

                self.lift_max_margin = self.target_lift + LIFT_MARGIN
                self.pan_max_margin = self.target_pan + PAN_MARGIN
                self.tilt_max_margin = self.target_tilt + TILT_MARGIN

                # 작동 시간 & LPT 마진 범위 내에 들어올 때까지
                init_time = datetime.datetime.now()
                limit_time = init_time + datetime.timedelta(seconds=LIMIT_TASK_TIME)

                # 2021.05.27 - 이슈 | set LPT 서비스와 face tracker 액션이 서로 겹치면서 제한 시간을 벗어나는 문제
                #              해결 | lift 만 체크해서 루프문을 탈출하도록
                # while True:
                #     # 탈출 조건
                #     # 1. 어플리케이션이 중지된 경우
                #     if self.pause_flag:
                #         break

                #     # 2. lpt 동작이 완료되거나 수행 시간이 제한된 시간을 초과한 경우
                #     if self.cur_lift_complete == True: # and self.cur_pan_complete == True and self.cur_tilt_complete == True) or (datetime.datetime.now() >= limit_time):
                #         break
                #     else:
                #         if (self.lift_min_margin <= self.cur_lift and self.cur_lift <= self.lift_max_margin):
                #             self.cur_lift_complete = True
                #         # if (self.pan_min_margin <= self.cur_pan and self.cur_pan <= self.pan_max_margin):
                #         #     self.cur_pan_complete = True
                #         # if (self.tilt_min_margin <= self.cur_tilt and self.cur_tilt <= self.tilt_max_margin):
                #         #     self.cur_tilt_complete = True

                #     self.action_sync(
                #         self.make_node("{namespace}/sero_mobile/lpt_set_position"),
                #         {
                #             "lift": self.target_lift,
                #             "pan": self.targe_pan,
                #             "tilt": self.targe_tilt,
                #         },
                #     )
                    
                #     time.sleep(2)

                self.cur_lift_complete = True

                # 현재 lpt가 완성되지 않았지만, 제한 시간을 초과하여 루프를 탈출한 경우
                if self.cur_lift_complete == False: # or self.cur_pan_complete == False or self.cur_tilt_complete == False):
                    self.logger.warning("\n\n @@@@@ 현재 LPT가 완성되지 않았지만, 제한 시간을 초과한 경우 \n")
                    if mod == "setting":
                        self.lpt_finish = False
                    else:
                        self.lpt_restore_finish = False

                    self.lpt_error_count += 1

                else:
                    self.logger.warning("\n\n @@@@@ 제한 시간내에 LPT가 완성된 경우 \n")
                    if mod == "setting":
                        self.lpt_finish = True
                    else:
                        self.lpt_restore_finish = True

                    self.lpt_error_count = 0

    def execute_to_mode(self):
        while datetime.datetime.now() < self.schedule_end_time:
            if self.pause_flag:
                break
            if self.is_agent_analysis_send is False:
                self.logger.info("\n\n @@@@@ agent analysis 모듈에 data를 publish \n")

                # LPT TRACKING ACTION
                msg = FaceDetectAndTrackActionGoal()
                msg.goal.origin_lift = self.target_lift
                msg.goal.origin_pan = self.target_pan
                msg.goal.origin_tilt = self.target_tilt
                msg.goal.strategy = FACE_TRACK_NEAREST_FACE

                action_node = self.make_node("{namespace}/face_tracker")

                ######## TODO 질문 1 - 계속 메시지를 만들 필요가 있나
                gen = self.action_generate(action_node, msg, timeout=30.0, auto_cancel=True)

                for process in gen:
                    if self.is_agent_analysis_send is False:
                        self.is_agent_analysis_send = True
                        self.publish(self.make_node("{namespace}/agent_analysis_data/transfer_image"), {})

                    if datetime.datetime.now() > self.schedule_end_time:
                        break

                self.logger.info("\n\n @@@@@ Action Generate Result = {} \n".format(gen.result))

                # NO ERROR
                if gen.result.error == False:
                    self.logger.warning("\n\n @@@@@ Action Generate No Error\n")
                # ERROR
                else:
                    self.logger.warning("\n\n @@@@@ Action Generate Error = {}".format(gen.result))

            time.sleep(0.2)

        self.mode_finish = True

    def on_pause(self, event):
        self.logger.info("\n\n @@@@@ paused \n")

        self.pause_flag = True
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
            manifest_path=os.path.join(os.path.dirname(__file__), "app_inspection.yaml"),
        )
    except:
        traceback.self.logger.info_exc()