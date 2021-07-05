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
            Check Immediate Charging Service
        '''

        self.check_receive_schedules()
        self.logger.info("Check Schedule Finish!!")

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
            schedule_list = []
            if self.is_immediate_mission == True:
                self.logger.info("Branch Immediate Mission\n\n")
                schedule_list = [self.immediate_mission_schedule]

            elif self.is_immediate_charging == True:
                self.logger.info("Branch Immediate Charging\n\n")
                schedule_list = [self.immediate_charging_schedule]

            else:
                self.logger.info("Branch Regular Mission\n\n")
                schedule_list = [self.regular_mission_schedule]

            self.logger.info("Final Schedule List = {}".format(schedule_list))
            # self.change_module(schedule_list)
        
    def check_receive_schedules(self):
        for sch in self.receive_schedules_data:
            now_time = datetime.now() # datetime
            now_time = datetime.strftime(now_time, "%H:%M:%S") # datetime -> string
            now_time = dateutil.parser.parse(now_time) # string -> datetime
            
            # self.logger.info("schedule_start_time = {}".format(sch["starttime"]))
            # self.logger.info("schedule_end_time = {}".format(sch["endtime"]))

            # sch_st = datetime.strptime(sch["starttime"].split(" ")[1], "%H:%M:%S") # string -> datetime
            sch_st = dateutil.parser.parse(sch["starttime"].split(" ")[1])
            # sch_et = datetime.strptime(sch["endtime"].split(" ")[1], "%H:%M:%S") # string -> datetime
            sch_et = dateutil.parser.parse(sch["endtime"].split(" ")[1])

            # self.logger.info("now_time = {}".format(now_time))
            # self.logger.info("schedule_start_time = {}".format(sch_st))
            # self.logger.info("schedule_end_time = {}".format(sch_et))

            if sch_et < now_time:
                self.logger.info("\ncurrent time >>>>> schedule end time")
                continue

            elif now_time < sch_st:
                self.logger.info("\ncurrent time <<<<< schedule end time")
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
                self.logger.info("\ncurrent time is in range scheudle time\n")
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
                        self.logger.info("This is Inspection Scheduler!!!!")
                        time_offset_prev = now_time + timedelta(minutes=self.time_offset_prev)
                        time_offset_prev = datetime.strftime(time_offset_prev, "%H:%M:%S") # string -> datetimee

                        time_offset_next = now_time + timedelta(minutes=self.time_offset_next)
                        time_offset_next = datetime.strftime(time_offset_next, "%H:%M:%S") # string -> datetime


                        self.logger.info("time_offset_prev = {}".format(time_offset_prev))
                        self.logger.info("time_offset_next = {}".format(time_offset_next))

                        for arr in self.receive_arrivals_data:
                            value_time = arr["estimatedDateTime"] # unicode
                            time_estimated_arrival = "".join([value_time[i] if i % 2 == 0 else value_time[i] + ":" for i in range(len(value_time))]) + "00"
                            time_estimated_arrival = dateutil.parser.parse(time_estimated_arrival)

                            self.logger.info("estimatedDateTime = {}".format(time_estimated_arrival))

                            if time_offset_prev <= time_estimated_arrival <= time_offset_next:
                                self.logger.info("\nestimatedDateTime is in range time offset!!\n")
                                if sch_et < time_estimated_arrival:
                                    break
                                else:
                                    calc_et = time_estimated_arrival + timedelta(minutes=self.service_run_time)

                                    if calc_et < now_time:
                                        self.logger.warning("Current time has passed the service end time. So skip !!!\n")
                                        continue

                                    if calc_et >= sch_et:
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
                                        self.logger.info("There is no location name match with gate")
                                        self.regular_mission_schedule = dict()

                    # 방역 모드인 경우, offset을 고려하지 않는다.
                    else:
                        self.logger.info("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ This is Quarantine Scheduler!!!!")
                        for arr in self.receive_arrivals_data:
                            value_time = arr["estimatedDateTime"] # unicode
                            time_estimated_arrival = "".join([value_time[i] if i % 2 == 0 else value_time[i] + ":" for i in range(len(value_time))]) + "00"
                            time_estimated_arrival = dateutil.parser.parse(time_estimated_arrival)

                            # self.logger.info("\n\n now time = {}\n".format(now_time))
                            # self.logger.info("\n\n time estimated arrival = {}\n".format(time_estimated_arrival))
 
                            if sch_et < time_estimated_arrival:
                                break
                            elif sch_st <= time_estimated_arrival <= sch_et:
                                self.logger.info("\n\n Time Estimated Arrival in range Schedule Time!! GO Quarantine!!")
                                self.logger.info("Schedule Start time = {}".format(sch_st))
                                self.logger.info("Scheduel End time = {}".format(sch_et))
                                calc_et = sch_et

                                gate = arr["gatenumber"]
                                # calc_et = datetime.strftime(calc_et, "%H:%M:%S")

                                self.logger.info("Gate = {}".format(gate))

                                if sch["location"] == self.find_location_with_gate(gate):
                                    self.logger.info("Find Location with gate !!! = {}".format(sch["location"]))
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
                                    self.logger.info("There is no location name match with gate")
                                    self.regular_mission_schedule = dict()

                    # 오프셋에 걸친 항공편이 없는 경우                    
                    if self.regular_mission_schedule == dict():
                        self.logger.info("there is no Schedule in time")
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

    def change_module(self, schedule_list):
        ################ 비교 + schedule 비교, 다르면 모듈 전환 #############################
        # For Flag Variables
        do_nothing = False
        pub_charging = False
        charging_end_time = None
        call_idle = False

        self.logger.info("@@@@@@@ 현재 시나리오 : ", self.cur_scenario)

        # 시나리오 수행 중이 아닌 console이 띄워진 경우이다.
        if self.cur_scenario != "inspection" and self.cur_scenario != "charging":
            do_nothing = True
        # inspection, charging과 같은 시나리오 수행 중에서만 스케줄 변경에 대한 행동을 취한다.
        else:
            in_doc_schedule = None
            in_received_schedule = None

            cur_time = datetime.datetime.now()

            # 도큐먼트로부터의 스케줄
            for schedule in self.schedule_doc:
                # dateutil.parser.parse에 의해 현 날짜로 년/월/일이 맞춰짐
                schedule_start_time = dateutil.parser.parse(schedule["start_time"])
                schedule_end_time = dateutil.parser.parse(schedule["end_time"])

                if (schedule_start_time <= cur_time) and (cur_time <= schedule_end_time):
                    in_doc_schedule = schedule

            # 받아온 스케줄 리스트로부터의 스케줄
            for schedule in schedule_list:
                schedule_start_time = dateutil.parser.parse(schedule["start_time"])
                schedule_end_time = dateutil.parser.parse(schedule["end_time"])

                if (schedule_start_time <= cur_time and cur_time <= schedule_end_time):
                    in_received_schedule = schedule

            # 둘 다 스케줄 안에 있다
            if in_received_schedule != None and in_doc_schedule != None:
                self.logger.info("@@@@@@@ 현 시간이 받아온 스케줄과 문서의 스케줄 안에 동시에 있다.")

                # 현재 점검이고, 받아온 스케줄이 긴급 모드로 인한 충전이라면 충전으로 가야한다.
                if (in_received_schedule["mode"]["type"] == "I" and in_received_schedule["mode"]["gate"] == "-1" and self.cur_scenario == "inspection"):
                    self.logger.info("@@@@@@@ 현재 점검이고, 받아온 스케줄이 긴급 모드로 인한 충전이라면 충전으로 가야한다.")
                    call_idle = True

                # 긴급 스케줄은 아닌, 정기 스케줄인데 현 스케줄에 변화가 없다.
                elif in_received_schedule == in_doc_schedule:
                    self.logger.info("@@@@@@@ 현재 스케줄이 같다.")

                    # 방어 코드 : 만에 하나 현재 상태는 '충전', 스케줄 명령이 '감시'인데 스케줄이 같다고 판별한 경우
                    if (self.cur_scenario == "charging" and in_received_schedule["mode"]["gate"] != "-1"):
                        call_idle = True
                    else:
                        do_nothing = True
                # 현 스케줄에 변화가 생겼다.
                else:
                    self.logger.info("@@@@@@@ 현재 스케줄이 다르다.")
                    # 현재 모두 충전 시나리오인가?
                    if (in_doc_schedule["mode"]["gate"] == "-1") and (in_received_schedule["mode"]["gate"] == "-1"):
                        self.logger.info("@@@@@@@ 현재 모두 충전 시나리오다.")
                        # 스케줄 종료 시간에 변화가 있는가?
                        if (in_received_schedule["end_time"] != in_doc_schedule["end_time"]):
                            self.logger.info("@@@@@@@ 그리고 스케줄 종료 시간에 변화가 있는 것이다.")

                            pub_charging = True
                            charging_end_time = dateutil.parser.parse(in_received_schedule["end_time"])
                        else:
                            do_nothing = True

                    # 기존 스케줄과 받아온 스케줄이 현재 점검인 경우.
                    # 끝내면서 어차피 inspection이 idle 호출한다.
                    elif (in_doc_schedule["mode"]["gate"] != "-1") and (in_received_schedule["mode"]["gate"] != "-1"):
                        self.logger.info("@@@@@@@ 현재 모두  점검 중이다.")
                        self.logger.info("@@@@@@@ 기존 점검을 마저 끝낸다.")
                        do_nothing = True

                    # 기존 스케줄이 점검인데, 받아온 스케줄이 충전이라면
                    elif (in_doc_schedule["mode"]["gate"] != "-1") and (in_received_schedule["mode"]["gate"] == "-1"):
                        self.logger.info("@@@@@@@ 기존 스케줄이 점검인데, 받아온 스케줄이 충전이다.")
                        self.logger.info("@@@@@@@ 스케줄 자체는 안 변했고, 도착편이 오프셋을 벗어나 만들 스케줄이 없는 경우이다.")
                        self.logger.info("@@@@@@@ 기존 점검을 마저 끝낸다.")
                        do_nothing = True
                    # 기존 스케줄이 충전인데, 받아온 스케줄이 점검이라면p
                    else:
                        self.logger.info("@@@@@@@ 기존 스케줄이 충전인데, 받아온 스케줄이 점검인 경우이다.")
                        self.logger.info("@@@@@@@ IDLE 호출한다.")
                        call_idle = True

            # 둘 다 스케줄 안에 없다 => 이전 스케줄과 다음 스케줄 사이에 있다. => 이는 곧 충전이다.
            elif in_received_schedule == None and in_doc_schedule == None:
                self.logger.info("@@@@@@@ 현 시간이 받아온 스케줄과 문서의 스케줄 안에 동시에 없다.")

                if self.is_charging == False:
                    self.logger.info("@@@@@@@ 현재 점검 중이면 충전으로 전환한다.")
                    call_idle = True
                else:
                    # end_time 계산 => 현 시간부로 다음 스케줄 시작 전까지 충전
                    # 만일 새로 받아온 스케줄 리스트에서 다음 스케줄이 없다면, 23:59:59로 설정
                    for schedule in schedule_list:
                        schedule_start_time = dateutil.parser.parse(schedule["start_time"])

                        if cur_time < schedule_start_time:
                            charging_end_time = schedule_start_time
                            break

                    if charging_end_time is None:
                        charging_end_time = dateutil.parser.parse("23:59:59")

                    pub_charging = True

            # 받아온 스케줄이 변경된 경우이다.
            else:
                self.logger.info("@@@@@@@ 어느 하나는 현 시간에 걸리고 다른 것은 걸리지 않는 경우이다.")
                self.logger.info("@@@@@@@ 이는 스케줄이 바뀐 경우이다!")

                # 현재 충전 중인데, 바뀐 스케줄이 충전일 경우 한 번 더 충전하는 것을 생략한다.
                if ((in_received_schedule != None) and (in_received_schedule["mode"]["gate"] == "-1") and (self.is_charging == True)):
                    charging_end_time = dateutil.parser.parse(in_received_schedule["end_time"])
                    pub_charging = True
                else:
                    call_idle = True

        # 도큐먼트에 받아온 정보 및 그로부터 계산한 스케줄 저장.
        # 때문에, idle이 참일 경우, 이 수정된 문서를 바탕으로 호출할 것이다.
        self.save_document("arrival", self.receive_arrivals_data)
        self.save_document("schedule", schedule_list)

        if do_nothing:
            self.logger.info("@@@@@@@ do nothing : 아무 것도 안 한다!")
            pass
        elif pub_charging:
            self.logger.info("@@@@@@@ pub charging : 충전 시나리오에 end time 던지기!")
            self.logger.info("@@@@@@@ charging_end_time : ", charging_end_time)
            self.publish(self.make_node("{namespace}/charging/event/end_time"), {
                "end_time": charging_end_time.isoformat()
            })
        elif call_idle:
            # docking 이면 빼고 해야됨 => 도킹 중인지는 charging 여부로 판단하지 말기
            if self.is_charging == True:
                self.logger.info("@@@@@@@ call idle & charging : IDLE이 호출돼야 하는데, 현재 도킹 중이다!")
                self.logger.info("@@@@@@@ 따라서 언도킹부터 진행한다.")
                self.publish(self.make_node("{namespace}/app_manager/undocking"), {
                    "type": "next_idle"
                })
            else:
                self.logger.info("@@@@@@@ call idle & not charging : IDLE이 호출!")
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