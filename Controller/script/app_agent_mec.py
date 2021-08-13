#!/usr/bin/python
# -*- encoding: utf-8 coding: utf8 -*-#

import os
import signal
import traceback
import datetime
import requests
from rade.modulebase import *
from rade.common import ResponseInfo

TRY_REQUEST_TIME = 10
class MyLoop(Loop):
    def on_create(self, event):
        '''
            Parse info from from robot_infos.yaml
        '''
        self.robo_info_doc = self.load_document("robot_infos")
        self.robo_id = self.robo_info_doc["ROBOT_ID"]
        self.robo_terminal = self.robo_info_doc["ROBOT_TERMINAL"]
        self.robo_zone = self.robo_info_doc["ROBOT_ZONE"]
        self.robo_sort = self.robo_info_doc["ROBOT_SORT"]
        self.robo_mode = self.robo_info_doc["ROBOT_MODE"]
        self.robo_desc = self.robo_info_doc["ROBOT_DESC"]

        '''
            Parse info from from control_server_infos.yaml
        '''
        self.control_server_infos = self.load_document("control_server_infos")
        self.control_server_url = self.control_server_infos["SERVER_URL"]
        self.control_server_authkey = self.control_server_infos["SERVER_AUTHKEY"]
        self.control_server_content_type = self.control_server_infos["SERVER_CONTENT_TYPE"]
        self.control_server_report_time_cycle = self.control_server_infos["SERVER_REQUEST_CYCLE_TIME"]

        self.get_api_schedule = self.control_server_infos["GET_SCHEDULE_API"]
        self.get_api_arrival = self.control_server_infos["GET_ARRIVAL_API"]
        self.post_api_register = self.control_server_infos["POST_REGISTER_API"]

        '''
            Make request header
        '''
        self.request_get_header = {
            "authkey": self.control_server_authkey
        }
        self.request_post_header = {
            "content-type": self.control_server_content_type,
            "authkey": self.control_server_authkey,
        }

        '''
            Flags for others
        '''
        self.is_first_report = True
        self.report_time = datetime.datetime.now()

        register_response = None
        for i in range(TRY_REQUEST_TIME):
            register_response = self.register_robot_control_server()
            if register_response != None:
                break
            else:
                i += 1

        if register_response != None:
            self.logger.info("\n\n <<<<<<<<<< Register Robot Success >>>>>>>>>> \n\n")
        else:
            self.logger.warning("\n\n <<<<<<<<<< Register Robot Fail >>>>>>>>>> \n\n")

        return ResponseInfo()
    
    def on_resume(self, event):
        return ResponseInfo()

    def on_loop(self):
        if self.is_first_report is True:
            self.send_server_data_to_scheduler_module()
            self.is_first_report = False
            self.report_time = datetime.datetime.now() + datetime.timedelta(seconds=self.server_report_time_cycle)
        
        else:
            if datetime.datetime.now() >= self.report_time:
                self.send_server_data_to_scheduler_module()
                self.report_time = datetime.datetime.now() + datetime.timedelta(seconds=self.server_report_time_cycle)

        return ResponseInfo()

    def on_pause(self, event):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    # 관제 서버에 로봇 등록 API
    def register_robot_control_server(self):
        response = None

        try:
            request_body = {
                "register": {
                    "id": self.robo_id,
                    "terminal": self.robo_terminal,
                    "zone": self.robo_zone,
                    "sort": self.robo_sort,
                    "desc": self.robo_desc,
                },
                "time": datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            }
            
            response = requests.post(
                url=self.server_url + self.post_api_register,
                headers=self.request_post_header,
                json=request_body,
                verify=False,
            )

            self.logger.info("\n\n <<<<<<<<<< Register Robot Response Status Code = {} >>>>>>>>>> \n\n".format(response.status_code))

        except Exception:
            response = None

        return response

    # 관제 서버로부터 스케줄 데이터 호출 API
    def request_schedule_from_control_server(self):
        response = None

        try:
            request_params = {
                "id": self.robo_id,
                "time": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            }

            response = requests.get(
                url=self.server_url + self.get_api_schedule,
                headers=self.request_get_header,
                params=request_params,
                verify=False,
            )

            self.logger.info("\n\n <<<<<<<<<< Request Schedule Data Response Status Code = {} >>>>>>>>>> \n\n".format(response.status_code))

        except Exception:
            response = None

        return response

    # 관제 서버로부터 항공편 데이터 호출 API
    def request_arrival_from_control_server(self):
        request_params = {
            "id": self.robo_id,
            "time": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        }

        try:
            response = requests.get(
                url=self.server_url + self.get_api_arrival,
                headers=self.request_get_header,
                params=request_params,
                verify=False,
            )

            response.encoding = "UTF-8"

            self.logger.info("\n\n <<<<<<<<<< Request Arrival Data Response Status Code = {} >>>>>>>>>> \n\n".format(response.status_code))

        except Exception:
            response = None

        return response

    # 관제로부터 받아온 스케줄/항공편 데이터를 scheduler module로 publish
    def send_server_data_to_scheduler_module(self):
        response_schedule = self.request_schedule_from_control_server()

        if response_schedule != None:
            response_schedule = response_schedule.json()
        else:
            self.logger.warning("\n\n <<<<<<<<<< Request Schedule Data Fail >>>>>>>>>> \n\n")            

        response_arrival = self.request_arrival_from_control_server()

        if response_arrival != None:
            response_arrival = response_arrival.json()
        else:
            self.logger.warning("\n\n <<<<<<<<<< Request Arrival Data Fail >>>>>>>>>> \n\n")

        result_control_server_data = dict()
        if response_schedule != None and response_arrival != None:
            result_control_server_data["schedules"] = response_schedule
            result_control_server_data["arrivals"] = response_arrival

            self.publish(self.make_node("{namespace}/control_server_data/arrived"), result_control_server_data)

__class = MyLoop
if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class,
            manifest_path=os.path.join(os.path.dirname(__file__), "app_agent_mec.yaml"),
        )
    except:
        traceback.print_exc()