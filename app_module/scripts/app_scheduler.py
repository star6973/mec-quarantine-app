#!/usr/bin/python
# -*- encoding: utf-8 coding: utf8 -*-#

import os
import signal
from time import strftime
import traceback
from datetime import datetime
import dateutil.parser
import requests
import copy
from urlparse import urlsplit, parse_qs

from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from rade.utils import *

REMARK = unicode("착륙", "utf-8")

class MyLoop(Loop):
    def on_create(self, event):
        '''
            Parse info from preference.yaml
        '''
        self.preference_doc = self.load_document("preferences")
        self.low_battery = self.preferences_doc["LOW_BATTERY"]
        self.service_mode = self.preference_doc["MODE"]

        '''
            Erase exist schedule
        '''
        self.save_document("schedule", [])

        '''
            Flags for running the service
        '''
        self.is_charging = False
        self.is_low_battery = False
        self.is_immediate_charging = False
        self.is_immediate_mission = False
        
        '''
            Flags for others
        '''
        self.cur_display = "app_console"
        self.cur_battery = 100
        self.enough_battery = 100
        self.service_run_time = 0
        self.time_offset_prev = 0
        self.time_offset_next = 0
        
        self.master_poi_doc = None
        self.schedule_doc = None
        self.immediate_response_data = None
        self.immediate_mission_schedule = dict()
        self.immediate_charging_schedule = dict()
        self.receive_schedules_data = []
        self.receive_arrivals_data = []
        
        self.add_listener(self.make_node("{namespace}/robot_display/event"), self.on_robot_display)
        self.add_listener(self.make_node("{namespace}/sero_mobile/battery"), self.on_battery_status)
        self.add_listener(self.make_node("{namespace}/charging/low_battery"), self.on_low_battery_status)
        self.add_listener(self.make_node("{namespace}/schedule/run_immediately"), self.on_immediate_schedule)
        self.add_listener(self.make_node("{namespace}/control_server_data/arrived"), self.on_server_data_arrived)

        return ResponseInfo()

    def on_resume(self, event):
        return ResponseInfo()

    def on_loop(self):
        return ResponseInfo()

    def on_pause(self, event):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    # 현재 전환된 화면 상태(content_pkg로 관리되고 있는 노드 패키지)
    def on_robot_display(self, res):
        content_data = urlsplit(res.body["content"])

        self.cur_display = content_data.path.split(".")[0].split("/")[1]
        self.logger.info("\nConvert to {} Display\n".format(self.cur_display))

    def on_battery_status(self, res):
        self.cur_battery = res.body["batteries"][0]["voltage_level"]
        self.is_charging = res.body["batteries"][0]["charging"]

        # 배터리 상태 계속 확인
        if self.cur_battery < self.low_battery:
            self.is_low_battery = True
        else:
            self.is_low_battery = False

    # app_charging.py에서 publish해주는 nats 메시지로, 도킹 후 현재 배터리 값이 최저 배터리 임계값보다 커질 경우 보내준다.
    def on_low_battery_status(self, res):
        self.is_low_battery = False

    # console 화면과 nats로 통신, 로컬에서 긴급 임무를 주어질 경우 바로 동작할 수 있도록 publish function을 사용한다.
    def on_immediate_schedule(self, res):
        if "canceld" in res.body:
            self.save_document("schedule", [])
            self.is_immediate_mission = False
        else:
            self.immediate_mission_schedule["end_time"] = res.body["end_time"]
            self.immediate_mission_schedule["gate"] = res.body["gate"]

            now_time = datetime.now() # datetime 형식
            now_time = now_time.strftime("%H:%M:%S") # datetime -> str 형식
            now_time = datetime.strptime(now_time, "%H:%M:%S") # str -> datetime 형식

            end_time = datetime.strptime(self.immediate_mission_schedule["end_time"], "%H:%M:%S")

            if now_time < end_time:
                location_name = self.find_location_with_gate(self.immediate_mission_schedule["gate"])
                
                if location_name != None:
                    mode = {
                        "location": location_name,
                        "gate": self.immediate_mission_schedule["gate"],
                        "name": self.service_mode,
                        "type": "I",
                        "calculated_end_time": end_time.strftime("%H:%M:%S")
                    }

                    self.immediate_mission_schedule["start_time"] = now_time.strftime("%H:%M:%S")
                    self.immediate_mission_schedule["end_time"] = end_time.strftime("%H:%M:%S")
                    self.immediate_mission_schedule["mode"] = mode

                    self.save_document("schedule", [self.immediate_mission_schedule])
                    self.is_immediate_mission = True

                    if self.cur_display == "charging" or self.is_charging == True:
                        self.publish(self.make_node("{namespace}/app_manager/undocking"), {"type": "next_idle"})
                    else:
                        self.publish(self.make_node("{namespace}/app_manager/idle"), {})

                else:
                    self.logger.info("There is no location name match with gate")

    # gate 값으로 location 값 찾기
    def find_location_with_gate(self, target_gate):
        locations = self.master_poi_doc[0]["locations"]

        for loc in locations:
            for gate in loc["gates"]:
                if gate["name"] == target_gate:
                    return loc["name"]

        return None

    def on_server_data_arrived(self, res):
        self.receive_schedules_data = [] if "cmd" not in res.body["schedules"] else res.body["schedules"]["cmd"]
        self.receive_arrivals_data = [] if "arrival" not in res.body["arrivals"] else res.body["arrivals"]["arrival"]

        tmp_arrivals_data = []
        for i in range(len(self.receive_arrivals_data)):
            data = self.receive_arrivals_data[i]

            if "estimatedDateTime" not in data:
                continue
            if "flightId" not in data:
                continue
            if "remark" not in data:
                continue
            if data["remark"] != REMARK:
                continue

            tmp_arrivals_data.append(data)

        self.receive_arrivals_data = copy.deepcopy(tmp_arrivals_data)
        del tmp_arrivals_data

        '''
            Refine required data
        '''
        self.receive_schedules_data = sorted(self.receive_schedules_data, key=lambda x: x["starttime"])
        self.receive_arrivals_data = sorted(self.receive_arrivals_data, key=lambda x: x["estimatedDateTime"])
    
        self.master_poi_doc = self.load_document("master_poi")
        self.schedule_doc = self.load_document("schedule")
        self.preference_doc = self.load_document("preferences")

        self.service_run_time = self.preferences_doc["SERVICE_RUNTIME"]
        self.time_offset_prev = self.preferences_doc["TIME_OFFSET_PREV"]
        self.time_offset_next = self.preferences_doc["TIME_OFFSET_NEXT"]
        self.service_mode = self.preference_doc["MODE"]
        self.low_battery = self.preferences_doc["LOW_BATTERY"]

        '''
            Publish changed enough battery value to Charing Module
        '''
        if self.enough_battery != self.preferences_doc["ENOUGH_BATTERY"]:
            self.enough_battery = self.preferences_doc["ENOUGH_BATTERY"]
            self.publish(self.make_node("{namespace}/charging/event/limit_voltage_level"), {
                "limit_voltage_level": self.enough_battery
            })

        '''
            Check Immediate Charging Service
        '''
        self.check_immediate_charging_schedule(self.receive_schedules_data)

        '''
            Refine Scheduler Branch Service
        '''
        self.scheduler_branch_service()


    def check_immediate_charging_schedule(self, schedules):
        for sch in schedules:
            sch_st = datetime.strptime(sch["starttime"], "%Y/%m/%d %H:%M:%S")
            sch_et = datetime.strptime(sch["endtime"], "%Y/%m/%d %H:%M:%S")

            now_time = datetime.now()

            if sch_et < now_time:
                continue
            elif sch_st <= now_time <= sch_et:
                if sch["type"] == "I":
                    mode = {
                        "location": sch["location"],
                        "gate": "-1",
                        "name": self.service_mode,
                        "type": sch["type"]
                    }

                    self.immediate_charging_schedule["start_time"] = sch_st.strftime("%H:%M:%S")
                    self.immediate_charging_schedule["end_time"] = sch_et.strftime("%H:%M:%S")
                    self.immediate_charging_schedule["mode"] = mode

                    self.is_immediate_charging = True
                
                else:
                    self.is_immediate_charging = False

    def scheduler_branch_service(self):
        '''
            [우선 순위]
            1. 배터리가 임계값보다 낮은 경우
            2. 로봇에서 입력한 긴급 임무(type = 'I')
            3. 관제에서 입력한 긴급 충전(type = 'I')
            4. 관제에서 입력한 정기 임무(type = 's')
        '''
        if self.is_low_battery == True:
            self.service_charging()
        else:
            if self.is_immediate_mission == True:
                return self.immediate_mission_schedule

            elif self.is_immediate_charging == True:
                return self.immediate_charging_schedule
            else:
                schedule_list = self.extract_schedule_list(self.receive_schedules_data, self.receive_arrivals_data)

            
    def service_charging(self):
        self.publish(self.make_node("{namespace}/app_manager/charging"), {
            "limit_voltage_level": self.enough_battery,
            "charging_mode": "low_battery",
        })


    def extract_schedule_list(self, sch_data, arr_data):
        
    


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