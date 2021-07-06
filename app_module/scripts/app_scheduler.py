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

class MyLoop(Loop):
    def on_create(self, event):
        '''
            Parse info from preference.yaml
        '''
        self.preferences_doc = self.load_document("preferences")
        self.low_battery = self.preferences_doc["LOW_BATTERY"]
        self.service_mode = self.preferences_doc["MODE"]

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
        self.regular_mission_schedule = dict()
        
        self.receive_schedules_data = []
        self.receive_arrivals_data = []
        self.valid_master_schedule = []
        
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

            now_time = datetime.now() # datetime
            now_time = now_time.strftime("%H:%M:%S") # datetime -> string
            now_time = datetime.strptime(now_time, "%H:%M:%S") # string -> datetime

            end_time = datetime.strptime(self.immediate_mission_schedule["end_time"], "%H:%M:%S") # string -> datetime

            if now_time < end_time:
                location_name = self.find_location_with_gate(self.immediate_mission_schedule["gate"])
                
                if location_name != None:
                    mode = {
                        "location": location_name,
                        "gate": self.immediate_mission_schedule["gate"],
                        "name": self.service_mode,
                        "type": "I",
                        "calculated_end_time": datetime.strftime(end_time, "%H:%M:%S")
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
        self.preferences_doc = self.load_document("preferences")

        self.service_run_time = self.preferences_doc["SERVICE_RUNTIME"]
        self.time_offset_prev = self.preferences_doc["TIME_OFFSET_PREV"]
        self.time_offset_next = self.preferences_doc["TIME_OFFSET_NEXT"]
        self.service_mode = self.preferences_doc["MODE"]
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
            Check receive schedule and extract valid schedule(1. Immediate Mission 2. Immediate Charging 3. Regular Mission)
        '''
        self.check_receive_schedules()

        self.logger.info("\n\n Immediate Mission Schedule = {}\n".format(self.immediate_mission_schedule))
        self.logger.info("\n Immediate Charging Schedule = {}\n".format(self.immediate_charging_schedule))
        self.logger.info("\n Regular Mission Schedule = {}\n\n".format(self.regular_mission_schedule))

        '''
            Refine Scheduler Branch Service
        '''
        if self.is_low_battery == True:
            self.publish(self.make_node("{namespace}/app_manager/charging"), {
                "limit_voltage_level": self.enough_battery,
                "charging_mode": "low_battery",
            })
        else:
            self.valid_master_schedule = []
            if self.is_immediate_mission == True:
                self.logger.info("@@@@@@@@@@@ Branch Immediate Mission @@@@@@@@@@@ \n\n")
                self.valid_master_schedule = [self.immediate_mission_schedule]

            elif self.is_immediate_charging == True:
                self.logger.info("@@@@@@@@@@@ Branch Immediate Charging @@@@@@@@@@@ \n\n")
                self.valid_master_schedule = [self.immediate_charging_schedule]

            else:
                self.logger.info("@@@@@@@@@@@ Branch Regular Mission @@@@@@@@@@@ \n\n")
                self.valid_master_schedule = [self.regular_mission_schedule]

            self.logger.info("Valid Master Schedule List = {}".format(self.valid_master_schedule))
            self.change_service_module()
        
    def check_receive_schedules(self):
        for sch in self.receive_schedules_data:
            now_time = datetime.now() # datetime
            now_time = datetime.strftime(now_time, "%H:%M:%S") # datetime -> string
            now_time = dateutil.parser.parse(now_time) # string -> datetime
            
            sch_st = dateutil.parser.parse(sch["starttime"].split(" ")[1]) # string -> datetime
            sch_et = dateutil.parser.parse(sch["endtime"].split(" ")[1]) # string -> datetime

            if sch_et < now_time:
                continue

            elif now_time < sch_st:
                self.logger.info("\n 스케줄 종료 후, 다음 스케줄까지 남는 시간 동안 충전 시나리오 시작\n")
                mode = {
                    "location": sch["location"],
                    "gate": "-1",
                    "name": self.service_mode,
                    "type": "S"
                }
                
                self.regular_mission_schedule["start_time"] = datetime.strftime(sch_st, "%H:%M:%S")
                self.regular_mission_schedule["end_time"] = datetime.strftime(sch_et, "%H:%M:%S")
                self.regular_mission_schedule["mode"] = mode
                break

            elif sch_st <= now_time <= sch_et:
                # 긴급 충전인 경우
                if sch["type"] == "I":
                    self.is_immediate_charging = True

                    mode = {
                        "location": sch["location"],
                        "gate": "-1",
                        "name": self.service_mode,
                        "type": sch["type"]
                    }

                    self.immediate_charging_schedule["start_time"] = sch_st.strftime("%H:%M:%S")
                    self.immediate_charging_schedule["end_time"] = sch_et.strftime("%H:%M:%S")
                    self.immediate_charging_schedule["mode"] = mode
                    break

                # 정기 임무인 경우
                else:
                    self.is_immediate_charging = False
                    self.is_immediate_mission = False

                    # 감시 모드인 경우, offset을 고려해준다.
                    if self.service_mode == "inspection":
                        self.logger.info("\n@@@@@@@@@@@@@@@@@@ 감시 스케줄 작성하기 !!!!\n")
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
                                    break
                                else:
                                    self.logger.info("\n\n Time Estimated Arrival in range Schedule Time!! GO Inspection!!")
                                    self.logger.info("Schedule Start time = {}".format(sch_st))
                                    self.logger.info("Estimated Time = {}".format(time_estimated_arrival))
                                    self.logger.info("Schedule End time = {}".format(sch_et))

                                    calc_et = time_estimated_arrival + timedelta(minutes=self.service_run_time)
                                    self.logger.info("Calculated End time = {}".format(calc_et))

                                    if calc_et < now_time:
                                        self.logger.warning("Current time has passed the service end time. So skip !!!\n")
                                        continue

                                    if calc_et >= sch_et:
                                        self.logger.info("Calculated End Time over passed Schedule End Time!!!\n")
                                        calc_et = sch_et

                                    gate = arr["gatenumber"]
                                    calc_et = datetime.strftime(calc_et, "%H:%M:%S")

                                    if sch["location"] == self.find_location_with_gate(gate):
                                        mode = {
                                            "location": sch["location"],
                                            "gate": gate,
                                            "name": self.service_mode,
                                            "type": "S",
                                            "calculated_end_time": calc_et
                                        }
                                        
                                        self.regular_mission_schedule["start_time"] = datetime.strftime(sch_st, "%H:%M:%S")
                                        self.regular_mission_schedule["end_time"] = datetime.strftime(sch_et, "%H:%M:%S")
                                        self.regular_mission_schedule["mode"] = mode
                                        break

                                    else:
                                        self.logger.info("There is no location name match with gate(Feat. Inspection)")
                                        self.regular_mission_schedule = dict()

                    # 방역 모드인 경우, offset을 고려하지 않는다.
                    else:
                        self.logger.info("\n@@@@@@@@@@@@@@@@@@ 방역 스케줄 작성하기 !!!!\n")
                        for arr in self.receive_arrivals_data:
                            value_time = arr["estimatedDateTime"] # unicode
                            time_estimated_arrival = "".join([value_time[i] if i % 2 == 0 else value_time[i] + ":" for i in range(len(value_time))]) + "00"
                            time_estimated_arrival = dateutil.parser.parse(time_estimated_arrival)

                            if sch_et < time_estimated_arrival:
                                break

                            elif sch_st <= time_estimated_arrival <= sch_et:
                                self.logger.info("\n\n Time Estimated Arrival in range Schedule Time!! GO Quarantine!!")
                                self.logger.info("Schedule Start time = {}".format(sch_st))
                                self.logger.info("Estimated Time = {}".format(time_estimated_arrival))
                                self.logger.info("Schedule End time = {}".format(sch_et))

                                if sch["location"] == self.find_location_with_gate(arr["gatenumber"]):
                                    self.logger.info("\n\n Find Location with gate !!! = {}, {}".format(sch["location"], arr["gatenumber"]))
                                    
                                    mode = {
                                        "location": sch["location"],
                                        "gate": arr["gatenumber"],
                                        "name": self.service_mode,
                                        "type": "S",
                                        "calculated_end_time": datetime.strftime(sch_et, "%H:%M:%S")
                                    }
                                    
                                    self.regular_mission_schedule["start_time"] = datetime.strftime(sch_st, "%H:%M:%S")
                                    self.regular_mission_schedule["end_time"] = datetime.strftime(sch_et, "%H:%M:%S")
                                    self.regular_mission_schedule["mode"] = mode
                                    break

                                else:
                                    self.logger.info("There is no location name match with gate(Feat. Quarantine)")
                                    self.regular_mission_schedule = dict()

                    # 정기 임무 중 스케줄 시간에 걸린 항공편이 없는 경우                    
                    if self.regular_mission_schedule == dict():
                        self.logger.info("\n\n @@@@@@ There is no Schedule in time\n")
                        mode = {
                            "location": sch["location"],
                            "gate": "-1",
                            "name": self.service_mode,
                            "type": "S",
                            "calculated_end_time": datetime.strftime(sch_et, "%H:%M:%S")
                        }

                        self.regular_mission_schedule["start_time"] = datetime.strftime(sch_st, "%H:%M:%S")
                        self.regular_mission_schedule["end_time"] = datetime.strftime(sch_et, "%H:%M:%S")
                        self.regular_mission_schedule["mode"] = mode
                    
                    break
    '''
        local에서 저장되어 있는 schedule.yaml 파일(현재 진행 중인 서비스)과 관제에서 받아온 valid_master_schedule을 비교하여 서비스를 바꿔주는 function
    '''
    def change_service_module(self):
        '''
            현재 상태 관리 변수
            0: 변화 없음
            1: 충전 스케줄 바꾸기
            2: event 호출하기
        '''
        schedule_status = 0
        change_charging_end_time = 0

        self.logger.info("Current Service Display: {}".format(self.cur_display))

        '''
            로컬 vs 관제
            1. 로컬 = [], 관제 = []                 # 현재 시간이 이전 스케줄과 다음 스케줄 사이에 있는 경우, status = 1
            2. 로컬 != [], 관제 != []               # 현재 시간이 스케줄 범위 내에 있는 경우
                2-1. 로컬 == 관제                   # status = 0
                2-2. 로컬 != 관제
                    2-2-1. 로컬(임무), 관제(임무)    # status = 0
                    2-2-2. 로컬(충전), 관제(충전)    # local_schedule_end_time = agent_schedule_end_time if local_schedule_end_time != agent_schedule_end_time else status = 0
                    2-2-3. 로컬(임무), 관제(충전)    # status = 2 if agent_schedule == "I" else status = 0
                    2-2-4. 로컬(충전), 관제(임무)    # status = 2
            3. 나머지 예외 상황
        '''
        if self.cur_display not in ["charging", "inspection", "quarantine"]:
            schedule_status = 0
        else:
            local_schedule = []
            agent_schedule = []
            now_time = datetime.now()

            for sch in self.schedule_doc:
                sch_st = dateutil.parser.parse(sch["start_time"])
                sch_et = dateutil.parser.parse(sch["end_time"])

                if sch_st <= now_time <= sch_et:
                    local_schedule = sch
            
            self.logger.info("@@@@@@@@ 현재 시간 범위 내에 있는 로컬 스케줄 = {}\n\n".format(local_schedule))

            for sch in self.valid_master_schedule:
                sch_st = dateutil.parser.parse(sch["start_time"])
                sch_et = dateutil.parser.parse(sch["end_time"])

                if sch_st <= now_time <= sch_et:
                    agent_schedule = sch

            self.logger.info("@@@@@@@@ 현재 시간 범위 내에 있는 관제 스케줄 = {}\n\n".format(agent_schedule))

            if local_schedule == [] and agent_schedule == []:
                self.logger.info("\nLocal Schedule is Empty. Agent Schedule is Empty.\n")

                if self.is_charging == False:
                    schedule_status = 2

            elif local_schedule != [] and agent_schedule != []:
                self.logger.info("\nLocal Schedule is not Empty. Agent Schedule is not Empty.\n")
                
                loc_service = local_schedule["mode"]["gate"]
                loc_end_time = local_schedule["end_time"]

                agent_service = agent_schedule["mode"]["gate"]
                agent_end_time = agent_schedule["end_time"]
                agent_type = agent_schedule["mode"]["type"]

                if local_schedule == agent_schedule:
                    schedule_status = 0

                    '''
                        방어 코드(왜 필요한지 모르겠음, 일단 냅두자)
                        if self.cur_display == "charging" and agent_service != "-1":
                            schedule_status = 2
                        else:
                            schedule_status = 0
                    '''

                else:
                    # 로컬(임무), 관제(임무)
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

            elif local_schedule == [] and agent_schedule != []:
                self.logger.info("\nLocal Schedule is Empty. Agent Schedule is not Empty.\n")

                agent_service = agent_schedule["mode"]["gate"]
                agent_end_time = agent_schedule["end_time"]
                
                if self.is_charging == True and agent_service == "-1":
                    change_charging_end_time = dateutil.parser.parse(agent_end_time)
                    schedule_status = 1
                else:
                    schedule_status = 2

            else:
                self.logger.info("\nLocal Schedule is not Empty. Agent Schedule is Empty.\n")
                pass
        
        self.save_document("arrival", self.receive_arrivals_data)
        self.save_document("schedule", self.valid_master_schedule)

        if schedule_status == 0:
            self.logger.info("Status == 0, No Change")

            pass
        
        elif schedule_status == 1:
            self.logger.info("Status == 1, Change Charging Service")

            self.publish(self.make_node("{namespace}/charging/event/end_time"), {
                "end_time": change_charging_end_time.isoformat()
            })

        elif schedule_status == 2:
            self.logger.info("Status == 2, Change Mission Service")

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