#!/usr/bin/python
# -*- encoding: utf-8 coding: utf8 -*-#

import os
import signal
import traceback
from datetime import datetime, timedelta
import dateutil.parser
import copy
from urlparse import urlsplit
from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from rade.utils import *

REMARK = unicode("착륙", "utf-8")
SERVICE_INSPECTION = "inspection"
SERVICE_QUARANTINE = "quarantine"

class MyLoop(Loop):
    def on_create(self, event):
        """ Parse info from preference.yaml """
        self.preferences_doc = self.load_document("preferences")
        self.low_battery = self.preferences_doc["LOW_BATTERY"]
        self.service_mode = self.preferences_doc["MODE"]

        """ Parse info from quarantine_location.yaml """
        self.qa_loc_doc = self.load_document("quarantine_location")

        """ Erase exist schedule """
        self.save_document("schedule", [])

        """ Flags for running the service """
        self.is_charging = False
        self.is_low_battery = False
        self.is_canceled_immediate_mission = True
        self.is_canceled_immediate_charging = True
        
        """ Flags for others """
        self.cur_display = "app_console"
        self.cur_battery = 100
        self.enough_battery = 100
        self.service_run_time = 0
        self.time_offset_prev = 0
        self.time_offset_next = 0
        
        self.master_poi_doc = None
        self.schedule_doc = None
        self.immediate_response_data = None

        self.immediate_local_mission_schedule = dict()
        self.immediate_local_charging_schedule = dict()
        self.immediate_agent_charging_schedule = dict()
        self.regular_agent_mission_schedule = dict()
        
        self.receive_schedules_data = []
        self.receive_arrivals_data = []
        self.valid_master_schedule = []
        
        self.add_listener(self.make_node("{namespace}/robot_display/event"), self.on_robot_display)
        self.add_listener(self.make_node("{namespace}/sero_mobile/battery"), self.on_battery_status)
        self.add_listener(self.make_node("{namespace}/charging/low_battery"), self.on_low_battery_status)
        self.add_listener(self.make_node("{namespace}/schedule/write_immediate_mission"), self.on_immediate_local_mission_schedule)
        self.add_listener(self.make_node("{namespace}/schedule/write_immediate_charging"), self.on_immediate_local_charging_schedule)
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
    def on_immediate_local_mission_schedule(self, res):
        if "canceled" in res.body:
            self.logger.info("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] Canceled from Console Display >>>>>>>>>> \n\n")

            self.immediate_local_mission_schedule = dict()
            self.is_canceled_immediate_mission = True
            self.save_document("schedule", [])

        else:
            now_time = datetime.now() # datetime
            now_time = now_time.strftime("%H:%M:%S") # datetime -> string
            now_time = datetime.strptime(now_time, "%H:%M:%S") # string -> datetime

            end_time = res.body["end_time"]
            end_time = datetime.strptime(end_time, "%H:%M:%S") # string -> datetime

            self.immediate_local_mission_schedule = dict()
            self.is_canceled_immediate_mission = False

            # Inspection Service
            if self.service_mode == SERVICE_INSPECTION:
                gate = res.body["gate"]

                if now_time < end_time:
                    location_name = self.find_location_with_gate(gate)
                    
                    if location_name != None:
                        self.immediate_local_mission_schedule = self.create_schedule_template_for_insepction(
                            start_time=now_time.strftime("%H:%M:%S"),
                            end_time=end_time.strftime("%H:%M:%S"),
                            calc_end_time=datetime.strftime(end_time, "%H:%M:%S"),
                            type="I",
                            location=location_name,
                            gate=gate,
                            name=self.service_mode
                        )
                        
                        self.logger.info("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] Approved from Console Display >>>>>>>>>> \n\n")
                        self.save_document("schedule", [self.immediate_local_mission_schedule])
                        
                        # 충전소 안에서는 undocking을 먼저
                        if self.cur_display == "charging" or self.is_charging == True:
                            self.publish(self.make_node("{namespace}/app_manager/undocking"), {"type": "next_idle"})
                        # 충전소 밖에서는 바로 임무 수행
                        else:
                            self.publish(self.make_node("{namespace}/app_manager/idle"), {})

                    else:
                        self.logger.error("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] There is no location name match with gate >>>>>>>>>> \n\n")

                else:
                    self.logger.error("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] You entered the wrong end time >>>>>>>>>> \n\n")
                    
            # Quarantine Service
            elif self.service_mode == SERVICE_QUARANTINE:
                location = res.body["location"]

                if now_time < end_time:
                    self.immediate_local_mission_schedule = self.create_schedule_template_for_quarantine(
                        start_time=now_time.strftime("%H:%M:%S"),
                        end_time=end_time.strftime("%H:%M:%S"),
                        type="I",
                        location=location,
                        name=self.service_mode
                    )

                    self.logger.info("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] Approved from Console Display >>>>>>>>>> \n\n")
                    self.save_document("schedule", [self.immediate_local_mission_schedule])
                    
                    if self.cur_display == "charging" or self.is_charging == True:
                        self.publish(self.make_node("{namespace}/app_manager/undocking"), {"type": "next_idle"})
                    else:
                        self.publish(self.make_node("{namespace}/app_manager/idle"), {})

                else:
                    self.logger.error("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] You entered the wrong end time >>>>>>>>>> \n\n")

            else:
                self.logger.error("\n\n <<<<<<<<<< [Immediate Local Mission Schedule] You entered the wrong service mode name >>>>>>>>>> \n\n")

    # gate 값으로 location 값 찾기
    def find_location_with_gate(self, target_gate):
        locations = self.master_poi_doc[0]["locations"]

        for loc in locations:
            for gate in loc["gates"]:
                if gate["name"] == target_gate:
                    return loc["name"]
        return None

    # 로컬 즉시 충전 callback 함수
    def on_immediate_local_charging_schedule(self, res):
        if "canceled" in res.body:
            self.logger.info("\n\n <<<<<<<<<< [Immediate Local Charging Schedule] Canceled from Console Display >>>>>>>>>> \n\n")

            self.immediate_local_charging_schedule = dict()
            self.is_canceled_immediate_charging = True
            self.save_document("schedule", [])

        else:
            now_time = datetime.now() # datetime
            now_time = now_time.strftime("%H:%M:%S") # datetime -> string
            now_time = datetime.strptime(now_time, "%H:%M:%S") # string -> datetime

            end_time = res.body["end_time"]
            end_time = datetime.strptime(end_time, "%H:%M:%S") # string -> datetime

            self.immediate_local_charging_schedule = dict()
            self.is_canceled_immediate_charging = False

            # Inspection Service
            if self.service_mode == SERVICE_INSPECTION:
                self.immediate_local_charging_schedule = self.create_schedule_template_for_insepction(
                    start_time=now_time.strftime("%H:%M:%S"),
                    end_time=end_time.strftime("%H:%M:%S"),
                    calc_end_time=end_time.strftime("%H:%M:%S"),
                    type="I",
                    location="-1",
                    gate="-1",
                    name=self.service_mode
                )
                        
                self.logger.info("\n\n <<<<<<<<<< [Immediate Local Charging Schedule] Approved from Console Display >>>>>>>>>> \n\n")
                self.save_document("schedule", [self.immediate_local_charging_schedule])
                        
                # 충전소 안에서는 undocking을 먼저
                if self.cur_display == "charging" or self.is_charging == True:
                    self.publish(self.make_node("{namespace}/app_manager/undocking"), {"type": "next_idle"})
                # 충전소 밖에서는 바로 임무 수행
                else:
                    self.publish(self.make_node("{namespace}/app_manager/idle"), {})

            # Quarantine Service
            elif self.service_mode == SERVICE_QUARANTINE:
                self.immediate_local_charging_schedule = self.create_schedule_template_for_quarantine(
                    start_time=now_time.strftime("%H:%M:%S"),
                    end_time=end_time.strftime("%H:%M:%S"),
                    type="I",
                    location= "-1",
                    name=self.service_mode
                )

                self.logger.info("\n\n <<<<<<<<<< [Immediate Local Charging Schedule] Approved from Console Display >>>>>>>>>> \n\n")
                self.save_document("schedule", [self.immediate_local_charging_schedule])
                
                if self.cur_display == "charging" or self.is_charging == True:
                    self.publish(self.make_node("{namespace}/app_manager/undocking"), {"type": "next_idle"})
                else:
                    self.publish(self.make_node("{namespace}/app_manager/idle"), {})

    # inspection scheduler template
    def create_schedule_template_for_insepction(self, start_time, end_time, calc_end_time, type, location, gate, name):
        template = {
            "start_time": start_time,
            "end_time": end_time,
            "mode": {
                "calculated_end_time": calc_end_time,
                "type": type,
                "location": location,
                "gate": gate,
                "name": name
            }
        }
        return template

    # quarantine scheduler template
    def create_schedule_template_for_quarantine(self, start_time, end_time, type, location, name):
        template = {
            "start_time": start_time,
            "end_time": end_time,
            "mode": {
                "type": type,
                "location": location,
                "name": name
            }
        }
        return template

    # 관제 서버에서 1분마다 갱신
    def on_server_data_arrived(self, res):
        self.logger.info("\n\n\n <<<<<<<<<< 1분마다 갱신 시작 >>>>>>>>>> \n\n")
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

        """ Refine required data """
        self.receive_schedules_data = sorted(self.receive_schedules_data, key=lambda x: x["starttime"])
        self.receive_arrivals_data = sorted(self.receive_arrivals_data, key=lambda x: x["estimatedDateTime"])
    
        self.master_poi_doc = self.load_document("master_poi")
        self.schedule_doc = self.load_document("schedule")
        self.preferences_doc = self.load_document("preferences")

        self.service_run_time = self.preferences_doc["SERVICE_RUNTIME"]
        self.time_offset_prev = self.preferences_doc["TIME_OFFSET_PREV"]
        self.time_offset_next = self.preferences_doc["TIME_OFFSET_NEXT"]
        self.service_mode = self.preferences_doc["MODE"]
        self.low_battery = self.preferences_doc["LOW_BATTERY"]

        self.regular_agent_mission_schedule = dict()
        self.valid_master_schedule = []

        if self.service_mode == SERVICE_INSPECTION:
            self.logger.info(" <<<<<<<<<< [Step 1] Recevied Schedule & Arrivals Data >>>>>>>>>> \n")

            self.logger.info("Schedule Data = {}\n".format(self.receive_schedules_data))
            self.logger.info("Arrival Data = {}\n".format(self.receive_arrivals_data))

        elif self.service_mode == SERVICE_QUARANTINE:
            self.logger.info(" <<<<<<<<<< [Step 1] Recevied Schedule Data >>>>>>>>>> \n")

            self.logger.info("Schedule Data = {}\n".format(self.receive_schedules_data))

        else:
            self.logger.error("\n\n <<<<<<<<<< [Received Schedule] You entered the wrong service mode name >>>>>>>>>> \n\n")

        """ Publish changed enough battery value to Charing Module """
        if self.enough_battery != self.preferences_doc["ENOUGH_BATTERY"]:
            self.enough_battery = self.preferences_doc["ENOUGH_BATTERY"]
            self.publish(self.make_node("{namespace}/charging/event/limit_voltage_level"), {
                "limit_voltage_level": self.enough_battery
            })

        """ Check receive schedule and extract valid schedule(1. Immediate Local Charging 2. Immediate Local Mission 3. Immediate Agent Charging 4. Regular Agent Mission) """
        self.check_receive_schedules()

        self.logger.info("\n\n\n ================== [스케줄 결과 데이터] ================== \n")
        self.logger.info("\n Immediate Local Charging Schedule = {}\n\n".format(self.immediate_local_charging_schedule))
        self.logger.info("\n Immediate Local Mission Schedule = {}\n\n".format(self.immediate_local_mission_schedule))
        self.logger.info("\n Immediate Agent Charging Schedule = {}\n\n".format(self.immediate_agent_charging_schedule))
        self.logger.info("\n Regular Agent Mission Schedule = {}\n\n\n".format(self.regular_agent_mission_schedule))

        """
            Refine Scheduler Branch Service
        
            < 우선 순위 >
            1. Low Battery
            2. Immediate Local Charging
            3. Immediate Local Mission
            4. Immediate Agent Charging
            5. Regular Agent Mission
        """
        if self.is_low_battery == True:
            self.publish(self.make_node("{namespace}/app_manager/charging"), {
                "limit_voltage_level": self.enough_battery,
                "charging_mode": "low_battery",
            })
        
        elif self.immediate_local_charging_schedule != dict():
            self.logger.info("\n\n\n <<<<<<<<<< 로컬에서 즉시 충전 스케줄이 최종적으로 작성되었습니다. >>>>>>>>>> \n")
            pass

        else:
            if self.immediate_local_mission_schedule != dict():
                self.logger.info("\n\n\n <<<<<<<<<< 로컬에서 즉시 임무 스케줄이 최종적으로 작성되었습니다. >>>>>>>>>> \n")

                self.valid_master_schedule = [self.immediate_local_mission_schedule]

            elif self.immediate_agent_charging_schedule != dict():
                self.logger.info("\n\n\n <<<<<<<<<< 관제에서 즉시 충전 스케줄이 최종적으로 작성되었습니다. >>>>>>>>>> \n")

                self.valid_master_schedule = [self.immediate_agent_charging_schedule]
            
            elif self.immediate_local_mission_schedule == dict() and self.immediate_agent_charging_schedule == dict():
                self.logger.info("\n\n\n <<<<<<<<<< 관제에서 정기 임무 스케줄이 최종적으로 작성되었습니다. >>>>>>>>>> \n")

                self.valid_master_schedule = [self.regular_agent_mission_schedule]

            """ Branch Service Mode """
            self.change_service_module()
        
    def check_receive_schedules(self):
        self.logger.info("\n\n <<<<<<<<<< [Step 2] 즉시 로컬 충전 스케줄 체킹 시작!!! >>>>>>>>>> \n")

        # checking immediate local charging schedule
        if self.immediate_local_charging_schedule != dict():
            self.logger.warning("\n 즉시 로컬 충전 스케줄이 아직 존재합니다... \n")

            now_time = datetime.now() # datetime
            now_time = now_time.strftime("%H:%M:%S") # datetime -> string
            now_time = datetime.strptime(now_time, "%H:%M:%S") # string -> datetime

            end_time = self.immediate_local_charging_schedule["end_time"]
            end_time = datetime.strptime(end_time, "%H:%M:%S") # string -> datetime

            """ 즉시 충전은 우선 순위가 가장 높기 때문에 무조건 설정해준 end_time까지 유지한다. """
            if now_time < end_time:
                # 중간에 취소했으나, 즉시 로컬 충전 스케줄이 미처 삭제되지 않은 경우
                if self.cur_display == "console" and self.is_canceled_immediate_charging == True:
                    self.logger.info("\n 즉시 로컬 충전 스케줄을 중간에 취소했습니다... \n")

                    self.immediate_local_charging_schedule = dict()
                    self.save_document("schedule", [])

                else:
                    self.logger.info("\n 즉시 로컬 충전 스케줄이 유지되는 중입니다... \n")
                    pass

            # 시간이 지나면 초기화(1분마다 확인하는 곳이기 때문에)
            else:
                self.logger.info("\n 즉시 로컬 충전 스케줄 시간이 지났습니다... \n")
                self.immediate_local_charging_schedule = dict()

        self.logger.info("\n\n <<<<<<<<<< [Step 3] 즉시 로컬 임무 스케줄 체킹 시작!!! >>>>>>>>>> \n")

        # checking immediate local mission schedule
        if self.immediate_local_mission_schedule != dict():
            self.logger.warning("\n 즉시 로컬 임무 스케줄이 아직 존재합니다... \n")

            now_time = datetime.now() # datetime
            now_time = now_time.strftime("%H:%M:%S") # datetime -> string
            now_time = datetime.strptime(now_time, "%H:%M:%S") # string -> datetime

            end_time = self.immediate_local_mission_schedule["end_time"]
            end_time = datetime.strptime(end_time, "%H:%M:%S") # string -> datetime

            if now_time < end_time:
                # 즉시 임무를 중간에 취소하고 충전소에 복귀했으나, 즉시 로컬 임무 스케줄이 미처 삭제되지 않은 경우
                if self.cur_display in ["charging", "console"] or self.is_canceled_immediate_mission == True:
                    self.logger.info("\n 즉시 로컬 임무 스케줄을 중간에 취소했습니다... \n")

                    self.immediate_local_mission_schedule = dict()
                    self.save_document("schedule", [])

                else:
                    self.logger.info("\n 즉시 로컬 임무 스케줄이 유지되는 중입니다... \n")
                    pass
                    
            # 시간이 지나면 초기화(1분마다 확인하는 곳이기 때문에)
            else:
                self.logger.info("\n 즉시 로컬 임무 스케줄 시간이 지났습니다... \n")
                self.immediate_local_mission_schedule = dict()

        self.logger.info("\n\n <<<<<<<<<< [Step 4] 즉시 관제 충전 스케줄 체킹 시작!!! >>>>>>>>>> \n")

        # checking immediate agent charging schedule
        if self.immediate_agent_charging_schedule != dict():
            self.logger.warning("\n 즉시 관제 충전 스케줄이 아직 존재합니다... \n")

            now_time = datetime.now() # datetime
            now_time = now_time.strftime("%H:%M:%S") # datetime -> string
            now_time = datetime.strptime(now_time, "%H:%M:%S") # string -> datetime

            end_time = self.immediate_agent_charging_schedule["end_time"]
            end_time = datetime.strptime(end_time, "%H:%M:%S") # string -> datetime

            """ 즉시 충전은 우선 순위가 가장 높기 때문에 무조건 설정해준 end_time까지 유지한다. """
            if now_time < end_time:
                # 즉시 충전을 중간에 취소했으나, 즉시 관제 충전 스케줄이 미처 삭제되지 않은 경우
                if self.cur_display == "console":
                    self.logger.info("\n 즉시 관제 충전 스케줄을 중간에 취소했습니다... \n")

                    self.immediate_agent_charging_schedule = dict()
                    self.save_document("schedule", [])

                else:
                    self.logger.info("\n 즉시 관제 충전 스케줄이 유지되는 중입니다... \n")
                    pass

            # 시간이 지나면 초기화(1분마다 확인하는 곳이기 때문에)
            else:
                self.logger.info("\n 즉시 관제 충전 스케줄 시간이 지났습니다... \n")
                self.immediate_agent_charging_schedule = dict()

        self.logger.info("\n\n <<<<<<<<<< [Step 5] 정기 관제 임무 스케줄 체킹 시작!!! >>>>>>>>>> \n")

        # checking regular agent mission schedule
        for sch in self.receive_schedules_data:
            now_time = datetime.now() # datetime
            now_time = datetime.strftime(now_time, "%H:%M:%S") # datetime -> string
            now_time = dateutil.parser.parse(now_time) # string -> datetime
            
            sch_st = dateutil.parser.parse(sch["starttime"].split(" ")[1]) # string -> datetime
            sch_et = dateutil.parser.parse(sch["endtime"].split(" ")[1]) # string -> datetime

            if now_time < sch_st:
                self.logger.info("\n 다음 스케줄까지 시간이 남았습니다. 충전소로 복귀합니다... \n")
                
                if self.service_mode == SERVICE_INSPECTION:
                    self.regular_agent_mission_schedule = self.create_schedule_template_for_insepction(
                        start_time=datetime.strftime(sch_st, "%H:%M:%S"),
                        end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                        calc_end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                        type="S",
                        location=sch["location"],
                        gate="-1",
                        name=self.service_mode
                    )
                    break

                elif self.service_mode == SERVICE_QUARANTINE:
                    self.regular_agent_mission_schedule = self.create_schedule_template_for_quarantine(
                        start_time=datetime.strftime(sch_st, "%H:%M:%S"),
                        end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                        type="S",
                        location= "-1",
                        name=self.service_mode
                    )
                    break
                    
                else:
                    self.logger.error("\n\n <<<<<<<<<< [Regular Agent Mission Schedule] You entered the wrong service mode name >>>>>>>>>> \n\n")
                    break

            elif sch_st <= now_time <= sch_et:
                self.logger.info("\n 스케줄에 들어왔습니다. 계산 중 입니다... \n")

                # 관제에서 내린 긴급 충전인 경우
                if sch["type"] == "I":
                    if self.service_mode == SERVICE_INSPECTION:
                        self.immediate_agent_charging_schedule = self.create_schedule_template_for_insepction(
                            start_time=sch_st.strftime("%H:%M:%S"),
                            end_time=sch_et.strftime("%H:%M:%S"),
                            calc_end_time=sch_et.strftime("%H:%M:%S"),
                            type="I",
                            location=sch["location"],
                            gate="-1",
                            name=self.service_mode
                        )
                        break
                        
                    elif self.service_mode == SERVICE_QUARANTINE:
                        self.immediate_agent_charging_schedule = self.create_schedule_template_for_quarantine(
                            start_time=sch_st.strftime("%H:%M:%S"),
                            end_time=sch_et.strftime("%H:%M:%S"),
                            type="I",
                            location= "-1",
                            name=self.service_mode
                        )
                        break

                    else:
                        self.logger.error("\n\n <<<<<<<<<< [Immediate Agent Charging Schedule] You entered the wrong service mode name >>>>>>>>>> \n\n")
                        break

                else:
                    # 감시 모드인 경우, offset과 gate를 고려한다.
                    if self.service_mode == SERVICE_INSPECTION:
                        time_offset_prev = now_time + timedelta(minutes=self.time_offset_prev)
                        time_offset_prev = datetime.strftime(time_offset_prev, "%H:%M:%S") # datetime -> string
                        time_offset_prev = dateutil.parser.parse(time_offset_prev) # string -> datetime

                        time_offset_next = now_time + timedelta(minutes=self.time_offset_next)
                        time_offset_next = datetime.strftime(time_offset_next, "%H:%M:%S") # string -> datetime
                        time_offset_next = dateutil.parser.parse(time_offset_next) # string -> datetime

                        for arr in self.receive_arrivals_data:
                            value_time = arr["estimatedDateTime"] # unicode
                            time_estimated_arrival = "".join([value_time[i] if i % 2 == 0 else value_time[i] + ":" for i in range(len(value_time))]) + "00"
                            time_estimated_arrival = dateutil.parser.parse(time_estimated_arrival)

                            if time_offset_prev <= time_estimated_arrival <= time_offset_next:
                                if sch_et < time_estimated_arrival:
                                    self.logger.info("\n 항공편 도착 예정 시간이 관제 스케줄 end time보다 크기 때문에, 현재 관제 스케줄말고 다음 관제 스케줄을 확인해 볼 필요가 있습니다... \n")
                                    break

                                else:
                                    self.logger.info("\n 항공편 도착 예정 시간이 오프셋에 걸렸습니다... \n")

                                    calc_et = time_estimated_arrival + timedelta(minutes=self.service_run_time)

                                    if calc_et < now_time:
                                        self.logger.info("\n (항공편 도착 예정 시간 + 서비스 런 타임) 시간이 현재 시간보다 작기 때문에, 다음 항공편 도착 예정 시간을 확인해 볼 필요가 있습니다... \n")
                                        continue

                                    if calc_et >= sch_et:
                                        self.logger.info("\n (항공편 도착 예정 시간 + 서비스 런 타임) 시간이 관제 스케줄 end time보다 크기 때문에, 끝나는 시간을 재계산합니다... \n")

                                        calc_et = sch_et

                                    gate = arr["gatenumber"]
                                    calc_et = datetime.strftime(calc_et, "%H:%M:%S")

                                    if sch["location"] == self.find_location_with_gate(gate):
                                        self.logger.info("\n Find location... \n")

                                        self.regular_agent_mission_schedule = self.create_schedule_template_for_insepction(
                                            start_time=datetime.strftime(sch_st, "%H:%M:%S"),
                                            end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                                            calc_end_time=calc_et,
                                            type="S",
                                            location=sch["location"],
                                            gate=gate,
                                            name=self.service_mode
                                        )
                                        return

                                    else:
                                        self.logger.info("\n Can't find location... \n")                            
                            else:
                                self.logger.info("\n 오프셋에 걸리는 항공편 도착 예정 시간이 없습니다... \n")

                    # 방역 모드인 경우, offset과 gate를 고려하지 않는다.
                    elif self.service_mode == SERVICE_QUARANTINE:
                        self.regular_agent_mission_schedule = self.create_schedule_template_for_quarantine(
                            start_time=datetime.strftime(sch_st, "%H:%M:%S"),
                            end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                            type="S",
                            location=sch["location"],
                            name=self.service_mode
                        )
                        return

                    else:
                        self.logger.error("\n\n <<<<<<<<<< [Regular Agent Mission Schedule] You entered the wrong service mode name >>>>>>>>>> \n\n")
                        break
            
            else:
                continue

        # 계산 결과, 정기 관제 임무 스케줄이 없는 경우
        if self.regular_agent_mission_schedule == dict():
            self.logger.info("\n 적합한 항공편 혹은 스케줄 시간이 없습니다. 충전소을 시작합니다... \n")

            sch_et = dateutil.parser.parse("23:50:00")

            if self.service_mode == SERVICE_INSPECTION:
                self.regular_agent_mission_schedule = self.create_schedule_template_for_insepction(
                    start_time=datetime.strftime(now_time, "%H:%M:%S"),
                    end_time= datetime.strftime(sch_et, "%H:%M:%S"),
                    calc_end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                    type="S",
                    location=sch["location"],
                    gate="-1",
                    name=self.service_mode
                )

            elif self.service_mode == SERVICE_QUARANTINE:
                self.regular_agent_mission_schedule = self.create_schedule_template_for_quarantine(
                    start_time=datetime.strftime(now_time, "%H:%M:%S"),
                    end_time=datetime.strftime(sch_et, "%H:%M:%S"),
                    type="S",
                    location="-1",
                    name=self.service_mode
                )
            
            else:
                self.logger.error("\n\n <<<<<<<<<< [Regular Agent Mission Schedule] You entered the wrong service mode name >>>>>>>>>> \n\n")
    
    """ local에서 저장되어 있는 schedule.yaml 파일(현재 진행 중인 서비스)과 관제에서 받아온 valid_master_schedule을 비교하여 서비스를 바꿔주는 function """
    def change_service_module(self):
        self.logger.info("\n\n <<<<<<<<<< [Step 6] 서비스 모드 변환 시작!!! >>>>>>>>>> \n")

        # 현재 상태 관리 변수(0: 변화 없음, 1: 충전 스케줄 시간 바꾸기, 2: event 호출하기)
        schedule_status = 0
        change_charging_end_time = 0

        if self.cur_display not in ["charging", "inspection", "quarantine"]:
            self.logger.info("\n 서비스 중이 아니므로, 현재 서비스를 유지하겠습니다... \n")
            schedule_status = 0
        
        else:
            local_schedule = []
            agent_schedule = []
            now_time = datetime.now()

            if self.schedule_doc == []:
                local_schedule = []

            else:
                for sch in self.schedule_doc:
                    sch_st = dateutil.parser.parse(sch["start_time"])
                    sch_et = dateutil.parser.parse(sch["end_time"])

                    if sch_st <= now_time <= sch_et:
                        local_schedule = sch

            for sch in self.valid_master_schedule:
                sch_st = dateutil.parser.parse(sch["start_time"])
                sch_et = dateutil.parser.parse(sch["end_time"])

                if sch_st <= now_time <= sch_et:
                    agent_schedule = sch
        
            self.logger.info("\n 서비스 중이므로, 현재 저장된 스케줄과 갱신된 스케줄을 비교하겠습니다... \n")
            self.logger.info("\n [Local Schedule] = {} \n".format(local_schedule))
            self.logger.info("\n [Agent Schedule] = {} \n\n".format(agent_schedule))

            '''
                < 현재까지 저장된 Schedule Data 파일 VS 1분마다 갱신된 Schedule Data >
                
                편의상, 현재까지 저장된 Schedule Data = local_schedule
                        1분마다 갱신된 Schedule Data = agent_schedule

                위의 두 스케줄을 비교를 통해, schedule_status 값을 바꾼다.

                1. local_schedule = [], agent_schedule = []
                    1.1. 충전소 안에 있다 ----------------------------------> schedule_status = 0
                    1.2. 충전소 밖에 있다 ----------------------------------> schedule_status = 2

                2. local_schedule = [], agent_schedule != []
                    2.1. agent_schedule(임무) -----------------------------> schedule_status = 2
                    2.2. agent_schedule(충전) -----------------------------> schedule_status = 1
                
                3. local_schedule != [], agent_schedule = [] -------------> schedule_status = 0

                4. local_schedule != [], agent_schedule != []
                    4.1. local_schedule == agent_schedule ----------------> schedule_status = 0
                    4.2. local_schedule != agent_schedule
                        4.2.1. local_schedule(임무), agent_schedule(임무) -> schedule_status = 0
                        4.2.2. local_schedule(충전), agent_schedule(충전) -> schedule_status = 0 / 1
                        4.2.3. local_schedule(임무), agent_schedule(충전) -> schedule_status = 0 / 2
                        4.2.4. local_schedule(충전), agent_schedule(임무) -> schedule_status = 2
            '''

            if local_schedule == [] and agent_schedule == []:
                self.logger.info("\n 두 개의 스케줄 모두 존재하지 않습니다... \n")
                
                if self.is_charging == False:
                    schedule_status = 2
                
                else:
                    schedule_status = 0

            elif local_schedule == [] and agent_schedule != []:
                self.logger.info("\n 갱신된 스케줄만 존재합니다... \n")

                agent_service = agent_schedule["mode"]["gate"] if self.service_mode == SERVICE_INSPECTION else agent_schedule["mode"]["location"]
                agent_end_time = agent_schedule["end_time"]

                if self.is_charging == True and agent_service == "-1":
                    change_charging_end_time = dateutil.parser.parse(agent_end_time)
                    schedule_status = 1

                else:
                    schedule_status = 2

            elif local_schedule != [] and agent_schedule == []:
                self.logger.info("\n 저장된 스케줄만 존재합니다... \n")

                schedule_status = 0

            else:
                self.logger.info("\n 두 개의 스케줄 모두 존재합니다... \n")

                loc_service = local_schedule["mode"]["gate"] if self.service_mode == SERVICE_INSPECTION else local_schedule["mode"]["location"]
                loc_end_time = local_schedule["end_time"]

                agent_service = agent_schedule["mode"]["gate"] if self.service_mode == SERVICE_INSPECTION else agent_schedule["mode"]["location"]
                agent_end_time = agent_schedule["end_time"]
                agent_type = agent_schedule["mode"]["type"]

                if local_schedule == agent_schedule:
                    schedule_status = 0

                    if self.cur_display == "charging" and agent_service != "-1":
                        schedule_status = 2

                    else:
                        schedule_status = 0

                else:
                    # 로컬(임무), 관제(임무)
                    # 관제에서 내린 임무가 현재 로컬에서 진행되고 있는 임무와 다르더라도, 현재 로컬에서 진행되고 있는 임무를 끝내야 하기 때문에 상태 변화 없음
                    if loc_service != "-1" and agent_service != "-1":
                        schedule_status = 0

                    # 로컬(충전), 관제(충전)
                    elif loc_service == "-1" and agent_service == "-1":
                        # 충전 end_time이 서로 다른 경우, 관제 end_time으로 업데이트
                        if loc_end_time != agent_end_time:
                            change_charging_end_time = dateutil.parser.parse(agent_end_time)
                            schedule_status = 1

                        else:
                            schedule_status = 0
                    
                    # 로컬(임무), 관제(충전)
                    elif loc_service != "-1" and agent_service == "-1":
                        # 관제에서 긴급 충전 명령을 보낸 경우
                        if agent_type == "I":
                            schedule_status = 2
                        
                        else:
                            schedule_status = 0
                    
                    # 로컬(충전), 관제(임무)
                    else:
                        schedule_status = 2

        self.save_document("arrival", self.receive_arrivals_data)
        self.save_document("schedule", self.valid_master_schedule)

        if schedule_status == 0:
            self.logger.info("\n\n <<<<<<<<<< [Step 7] {} 화면 유지!!! >>>>>>>>>> \n".format(self.cur_display))
            pass
        
        elif schedule_status == 1:
            self.logger.info("\n\n <<<<<<<<<< [Step 7] {} 화면에서 충전 시간 갱신하기!!! >>>>>>>>>> \n".format(self.cur_display))

            self.publish(self.make_node("{namespace}/charging/event/end_time"), {
                "end_time": change_charging_end_time.isoformat()
            })

        elif schedule_status == 2:
            self.logger.info("\n\n <<<<<<<<<< [Step 7] {} 화면에서 서비스 바꾸기!!! >>>>>>>>>> \n".format(self.cur_display))

            if self.is_charging == True:
                self.publish(self.make_node("{namespace}/app_manager/undocking"), {"type": "next_idle"})
                
            else:
                self.publish(self.make_node("{namespace}/app_manager/idle"), {})

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