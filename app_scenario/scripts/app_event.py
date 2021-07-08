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

        self.check_schedule()

        return ResponseInfo()

    def on_loop(self):
        return ResponseInfo()

    def on_pause(self, evnet):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    def check_schedule(self):
        self.now_time = datetime.now()

        try:
            if len(self.schedule_doc) != 0:
                # 첫 번째 인덱스 위치의 schedule 정보만 필요
                schedule = self.schedule_doc[0]
                self.logger.info("Schedule Yaml Data = {}\n\n".format(schedule))

                sch_st = dateutil.parser.parse(schedule["start_time"])
                sch_et = dateutil.parser.parse(schedule["end_time"])
                sch_md = schedule["mode"]

                self.logger.info("Start Time = ", sch_st)
                self.logger.info("End Time = ", sch_et)
                self.logger.info("Mode = ", sch_md)
                self.logger.info("\n\n")

                if sch_md["name"] == SERVICE_INSPECTION:
                    self.logger.info("감시모드 스케줄이 입력되었습니다\n")

                    self.gate_name = sch_md["gate"]
                    self.location_name = sch_md["location"]
                    self.calc_end_time = dateutil.parser.parse(sch_md["calculated_end_time"])
                    self.mode_name = sch_md["name"]

                elif sch_md["name"] == SERVICE_QUARANTINE:
                    self.logger.info("방역모드 스케줄이 입력되었습니다\n")

                    self.location_name = sch_md["location"]
                    self.mode_name = sch_md["name"]

                else:
                    self.logger.info("서비스명이 틀립니다!!")

                # 감시 모드나 방역 모드나 schedule_endtime이 서비스 끝의 기준이다.
                if sch_st <= self.now_time <= sch_et:
                    self.logger.info("\n ########### [IDLE] Start Time <= Now Time <= End Time!! ########### \n")

                    # 감시 모드 스케줄이 제대로 작동하려면
                    # 1) Inspection mode 2) gate != "-1" 3) 현재 시간 <= calculated_end_time
                    if self.mode_name == SERVICE_INSPECTION and self.gate_name != "-1" and self.now_time <= self.calc_end_time:
                        self.logger.info("\n감시 모드이면서 게이트가 존재하는 경우!!\n")
                        self.start_time = self.now_time
                        self.end_time = self.calc_end_time
                    
                    # 방역 모드 스케줄이 제대로 작동하려면
                    # 1) Quarantine mode 2) gate != "-1" 3) 현재 시간 <= sch_et
                    elif self.mode_name == SERVICE_QUARANTINE and self.location_name != "-1":
                        self.logger.info("\n방역 모드이면서 로케이션이 존재하는 경우!!\n")
                        self.start_time = self.now_time
                        self.end_time = sch_et
                    
                    # 게이트나 로케이션이 존재하지 않으면 schedule_end_time까지 충전해야 한다.
                    else:
                        self.logger.info("\n현재 {} 모드인데, 게이트나 로케이션이 존재하지 않는 경우!!\n".format(self.mode_name))
                        self.start_time = self.now_time
                        self.end_time = sch_et

                elif self.now_time < sch_st:
                    self.logger.info("\n ########### [IDLE] Now Time <= Start Time!! ########### \n")
                    self.start_time = self.now_time
                    self.end_time = sch_st

                else:
                    self.logger.info("\n ########### [IDLE] End Time <= Now Time !! ########### \n")
                    self.start_time = self.now_time
                    self.end_time = dateutil.parser.parse("23:50:00")

            else:
                self.start_time = self.now_time
                self.end_time = dateutil.parser.parse("23:50:00")

        except Exception as e:
            self.start_time = None
            self.end_time = None
        
        self.logger.info("\n\n ================ DATA ================ \n\n")
        self.logger.info("Mode Name = {}\n".format(self.mode_name))
        self.logger.info("Start Time = {}\n".format(self.start_time))
        self.logger.info("End Time = {}\n".format(self.end_time))
        self.logger.info("Calc End Time = {}\n".format(self.calc_end_time))        
        self.logger.info("Gate Name = {}\n".format(self.gate_name))
        self.logger.info("Location Name = {}\n".format(self.location_name))

        if self.start_time == None and self.end_time == None:
            self.start_time = self.now_time
            self.end_time = dateutil.parser.parse("23:00:00")
            self.logger.info("무엇인가 잘못 넣은 거임!!")
            self.logger.info("\n ########### Start Time = [] and End Time = [], Start Charging!! (Feat. IDLE) ########### \n")

            self.publish(
                self.make_node("{namespace}/app_manager/charging"),
                {
                    "start_time": self.start_time.isoformat(),
                    "end_time": self.end_time.isoformat(),
                    "charging_mode": "charging",
                },
            )

        else:
            '''
                1. inspection
                2. quarantine
                3. charging
            '''
            if self.mode_name == SERVICE_INSPECTION and self.gate_name != None and self.gate_name != "-1":
                self.logger.info("\n ########### Start Inspection!! (Feat. IDLE) ########### \n")

                self.publish(
                    self.make_node("{namespace}/app_manager/inspection"),
                    {
                        "end_time": self.end_time.isoformat(),
                        "gate": self.gate_name,
                        "location": self.location_name
                    },
                )

            elif self.mode_name == SERVICE_QUARANTINE and self.location_name != None and self.location_name != "-1":
                self.logger.info("\n ########### Start Quarantine!! (Feat. IDLE) ########### \n")

                self.publish(
                    self.make_node("{namespace}/app_manager/quarantine"),
                    {
                        "end_time": self.end_time.isoformat(),
                        "location": self.location_name
                    },
                )

            else:
                self.logger.info("\n ########### Start Charging!! (Feat. IDLE) ########### \n")

                self.publish(
                    self.make_node("{namespace}/app_manager/charging"),
                    {
                        "start_time": self.start_time.isoformat(),
                        "end_time": self.end_time.isoformat(),
                        "charging_mode": "charging",
                    },
                )