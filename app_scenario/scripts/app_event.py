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
                
                sch_st = dateutil.parser.parse(schedule["start_time"])
                sch_et = dateutil.parser.parse(schedule["end_time"])
                sch_md = schedule["mode"]

                if sch_md == SERVICE_INSPECTION:
                    self.gate_name = sch_md["gate"]
                    self.location_name = sch_md["location"]
                    self.calc_end_time = dateutil.parser.parse(sch_md["calculated_end_time"])
                    self.mode_name = sch_md["name"]
                else:
                    self.location_name = sch_md["location"]
                    self.mode_name = sch_md["name"]

                if sch_st <= self.now_time <= sch_et:
                    self.logger.info("\n ########### [IDLE] Start Time <= Now Time <= End Time!! ########### \n")
                    if self.mode_name == SERVICE_INSPECTION and self.gate_name != "-1" and self.now_time < self.calc_end_time:
                        self.start_time = self.now_time
                        self.end_time = self.calc_end_time

                    elif self.mode_name == SERVICE_QUARANTINE and self.location_name != "-1" and self.now_time < sch_et:
                        self.start_time = self.now_time
                        self.end_time = sch_et
                    
                    else:
                        self.start_time = self.now_time
                        self.end_time = sch_et

                elif self.now_time < sch_st:
                    self.logger.info("\n ########### [IDLE] Now Time <= Start Time!! ########### \n")
                    self.start_time = self.now_time
                    self.end_time = sch_st

            else:
                self.start_time = self.now_time
                self.end_time = dateutil.parser.parse("23:50:00")

        except Exception as e:
            self.start_time = self.now_time
            self.end_time = dateutil.parser.parse("23:50:00")
        
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

__class = MyLoop

if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class, manifest_path=os.path.join(os.path.dirname(__file__), "app_event.yaml")
        )
    except:
        traceback.print_exc()