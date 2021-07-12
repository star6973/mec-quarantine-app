#!/usr/bin/python
# -*- coding: utf8 -*-#

import os
import signal
import traceback
from datetime import datetime
import dateutil.parser

from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from rade.utils import *

SERVICE_INSPECTION = "inspection"
SERVICE_QUARANTINE = "quarantine"

class MyLoop(Loop):
    def on_create(self, event):
        return ResponseInfo()
    
    def on_resume(self, event):
        '''
            Read the required yaml file
        '''
        self.schedule_doc = self.load_document("schedule")

        '''
            Flags for others
        '''
        self.now_time = None
        self.start_time = None
        self.end_time = None
        self.calc_end_time = None
        self.mode_name = None
        self.gate_name = None
        self.location_name = None

        '''
            Start Check Schedule and Mission Start
        '''
        self.check_schedule()

        return ResponseInfo()

    def on_loop(self):
        return ResponseInfo()

    def on_pause(self, evnet):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    def check_schedule(self):
        self.logger.info("\n\n\n <<<<<<<<<< [IDLE Start] >>>>>>>>>> \n\n\n")

        self.now_time = datetime.now()
        self.start_time = None
        self.end_time = None

        if len(self.schedule_doc) != 0:
            # 첫 번째 인덱스 위치의 schedule 정보만 필요
            schedule = self.schedule_doc[0]
            sch_st = dateutil.parser.parse(schedule["start_time"])
            sch_et = dateutil.parser.parse(schedule["end_time"])
            sch_md = schedule["mode"]

            if sch_md["name"] == SERVICE_INSPECTION:
                self.logger.info("\n <<<<<<<<<< 감시모드 스케줄 입력 >>>>>>>>>> \n\n")

                self.gate_name = sch_md["gate"]
                self.location_name = sch_md["location"]
                self.calc_end_time = dateutil.parser.parse(sch_md["calculated_end_time"])
                self.mode_name = sch_md["name"]

                if sch_st <= self.now_time <= sch_et:
                    self.logger.info("\n [IDLE] Start Time <= Now Time <= End Time \n")
                    
                    if self.now_time < self.calc_end_time:
                        self.logger.info("\n 감시 모드이면서 현재 시간이 Calc End Time 안에 있습니다... \n")

                        if self.gate_name != "-1":
                            self.logger.info("\n 게이트가 존재합니다... \n")

                            self.start_time = self.now_time
                            self.end_time = self.calc_end_time

                        else:
                            self.logger.info("\n 게이트가 존재하지 않습니다... \n")

                            self.start_time = self.now_time
                            self.end_time = sch_et

                    else:
                        self.logger.info("\n 감시 모드이면서 현재 시간이 Calc End Time 벗어났습니다... \n")
                        self.logger.info("\n 강제로 충전을 시작합니다... \n")
                        
                        self.start_time = self.now_time
                        self.end_time = sch_et
                        self.gate_name = "-1"

                elif self.now_time < sch_st:
                    self.logger.info("\n [IDLE] Now Time < Start Time \n")
                    self.logger.info("\n 다음 스케줄까지 시간이 남아있습니다... \n")
                    
                    self.start_time = self.now_time
                    self.end_time = sch_st

                else:
                    self.logger.info("\n [IDLE] End Time < Now Time \n")
                    self.logger.info("\n 더이상 스케줄이 없습니다... ")
                    self.logger.info("\n 강제로 충전을 시작합니다... \n")

                    self.start_time = self.now_time
                    self.end_time = dateutil.parser.parse("23:50:00")
                    self.gate_name = "-1"

            elif sch_md["name"] == SERVICE_QUARANTINE:
                self.logger.info("\n\n <<<<<<<<<< 방역모드 스케줄 입력 >>>>>>>>>> \n\n")

                self.location_name = sch_md["location"]
                self.mode_name = sch_md["name"]

                if sch_st <= self.now_time <= sch_et:
                    self.logger.info("\n [IDLE] Start Time <= Now Time <= End Time \n")

                    self.start_time = self.now_time
                    self.end_time = sch_et

                elif self.now_time < sch_st:
                    self.logger.info("\n [IDLE] Now Time < Start Time \n")
                    self.logger.info("\n 다음 스케줄까지 시간이 남아있습니다... \n")
                    
                    self.start_time = self.now_time
                    self.end_time = sch_st

                else:
                    self.logger.info("\n [IDLE] End Time < Now Time \n")
                    self.logger.info("\n 더이상 스케줄이 없습니다... ")
                    self.logger.info("\n 강제로 충전을 시작합니다... \n")

                    self.start_time = self.now_time
                    self.end_time = dateutil.parser.parse("23:50:00")
                    self.location_name = "-1"

            else:
                self.logger.error("\n\n <<<<<<<<<< [IDLE] You entered the wrong service mode name >>>>>>>>>> \n\n")

        self.logger.info("\n\n\n ================== [스케줄 결과 데이터] ================== \n")
        self.logger.info("Mode Name = {}\n".format(self.mode_name))
        self.logger.info("Start Time = {}\n".format(self.start_time))
        self.logger.info("End Time = {}\n".format(self.end_time))
        self.logger.info("Calc End Time = {}\n".format(self.calc_end_time))        
        self.logger.info("Gate Name = {}\n".format(self.gate_name))
        self.logger.info("Location Name = {}\n".format(self.location_name))

        if self.start_time == None and self.end_time == None:
            self.logger.info("\n 강제 충전 시작!! \n")

            self.start_time = self.now_time
            self.end_time = dateutil.parser.parse("23:00:00")
            self.publish(
                self.make_node("{namespace}/app_manager/charging"),
                {
                    "start_time": self.start_time.isoformat(),
                    "end_time": self.end_time.isoformat(),
                    "charging_mode": "charging",
                },
            )

        else:
            if self.mode_name == SERVICE_INSPECTION and self.gate_name != None and self.gate_name != "-1":
                self.logger.info("\n 감시 서비스 시작!! \n")

                self.publish(
                    self.make_node("{namespace}/app_manager/inspection"),
                    {
                        "end_time": self.end_time.isoformat(),
                        "gate": self.gate_name,
                        "location": self.location_name
                    },
                )

            elif self.mode_name == SERVICE_QUARANTINE and self.location_name != None and self.location_name != "-1":
                self.logger.info("\n 방역 서비스 시작!! \n")

                self.publish(
                    self.make_node("{namespace}/app_manager/quarantine"),
                    {
                        "end_time": self.end_time.isoformat(),
                        "location": self.location_name
                    },
                )

            else:
                self.logger.info("\n 충전 서비스 시작!! \n")

                self.publish(
                    self.make_node("{namespace}/app_manager/charging"),
                    {
                        "start_time": self.start_time.isoformat(),
                        "end_time": self.end_time.isoformat(),
                        "charging_mode": "charging",
                    },
                )

__class = MyLoop

if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class, manifest_path=os.path.join(os.path.dirname(__file__), "app_event.yaml")
        )
    except:
        traceback.print_exc()