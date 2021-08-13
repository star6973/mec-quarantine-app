#!/usr/bin/python
# -*- encoding: utf-8 coding: utf8 -*-#

import os
import signal
import cv2
import traceback
import base64
import json
import datetime
import requests
import numpy as np
import rospy
import requests
import ros_numpy
import uuid
import math
from rade.utils import *
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage, PointCloud2
from sensor_msgs.msg import PointCloud2
from pedestrian_detection.msg import Pedestrians
from rade.modulebase import Loop, RosWrapper
from rade.common import ResponseInfo
from sensor_msgs.msg import CompressedImage, Image, PointCloud2
from std_msgs.msg import String

TRY_REQUEST_TIME = 10

class MyLoop(Loop):
    def on_create(self, event):
        '''
            Read the required yaml file
        '''
        self.preference_doc = self.load_document("preferences")
        self.robo_info_doc = self.load_document("robot_infos")
        self.cas_info_doc = self.load_document("cctv_analysis_server_infos")

        '''
            Parse info from preferences.yaml
        '''
        self.threshold_temp = self.preference_doc["TEMPERATURE_LIMIT"]
        self.threshold_mask = self.preference_doc["MASK_LIMIT"]
        self.threshold_dist = self.preference_doc["DISTANCE_LIMIT"]

        self.use_internal_temperature_analysis = self.preference_doc["USE_INTERNAL_TEMPERATURE_ANALYSIS"]
        self.use_internal_mask_analysis = self.preference_doc["USE_INTERNAL_MASK_ANALYSIS"]
        self.use_external_mask_analysis = self.preference_doc["USE_EXTERNAL_MASK_ANALYSIS"]
        self.use_internal_distance_analysis = self.preference_doc["USE_INTERNAL_DISTANCE_ANALYSIS"]
        self.use_external_distance_analysis = self.preference_doc["USE_EXTERNAL_DISTANCE_ANALYSIS"]
        
        '''
            Parse info from robot_infos.yaml
        '''
        self.cctv_id = self.robo_info_doc["ROBOT_ID"]
        self.cctv_pos = self.robo_info_doc["ROBOT_LOCATION"]

        '''
            Parse info from cctv_analysis_server_infos.yaml
        '''
        self.server_url = self.cas_info_doc["SERVER_URL"]
        self.cctv_type = self.cas_info_doc["CCTV_TYPE"]
        self.post_register_api = self.cas_info_doc["POST_REGISTER_API"]
        self.post_event_result_api = self.cas_info_doc["POST_EVENT_RESULT_API"]
        self.screen_width = float(self.cas_info_doc["SCREEN_WIDTH"])
        self.screen_height = float(self.cas_info_doc["SCREEN_HEIGHT"])
        
        '''
            Flags for others
        '''
        self.rgbd_image = None
        self.depth_image = None
        self.rgbd_width = None
        self.rgbd_height = None
        self.depth_width = None
        self.depth_height = None
        self.raw_rgbd_image = None
        self.raw_thermal_image = None

        self.detect_temperature = False
        self.detect_mask = []
        self.detect_distance = False

        self.request_id_and_image_buffer = [
            {'': None}, 
            {'': None},
            {'': None},
            {'': None}, 
            {'': None},
            {'': None},
            {'': None}, 
            {'': None},
            {'': None},
            {'': None}
        ]
        
        self.rid_buffer_len = len(self.request_id_and_image_buffer)
        self.rid_put_idx = 0

        '''
            Register on CCTV Analysis Server
        '''
        register_response = None
        for i in range(TRY_REQUEST_TIME):
            register_response = self.register_cctv_analysis_server()
            if register_response != None:
                break
            else:
                i += 1

        if register_response != None:
            self.transfer_image_url = json.loads(register_response.json())["transfer_image_url"]
            self.logger.info("\n\n 영상 전송 서버 URL = {}".format(self.transfer_image_url))
            self.logger.info("\n\n <<<<<<<<<< Register CCTV Server Success >>>>>>>>>> \n\n")
        else:
            self.logger.warning("\n\n <<<<<<<<<< Register CCTV Server Fail >>>>>>>>>> \n\n")

        '''
            < Event Listener Function >

            1. 고온 감지(내부) -------> /hikvision_thermal_camera_node/face_temperature
            2. 마스크 감지(내부) -----> /pedestrian_detector/pedestrians
            3. 거리두기 감지(내부) ---> /pedestrian_detector/pedestrians
            4. 마스크 감지(외부) -----> /rgbd/rgb/image_rect_color_throttle
            5. 거리두기 감지(외부) ---> /rgbd/rgb/image_rect_color_throttle, /rgbd/depth/points_throttle

            * 외부 모듈을 사용하는 경우, 
              마스크 감지에는 rgb 이미지만 필요하고,
              거리두기 감지에는 rgb 이미지와 depth 이미지가 필요하다.
        '''

        self.logger.info("모듈 선택 리스트")
        self.logger.info("고온 감지 모듈 = ", self.use_internal_temperature_analysis)
        self.logger.info("마스크 감지 모듈 = ", self.use_internal_mask_analysis)
        self.logger.info("거리두기 감지 모듈 = ", self.use_internal_distance_analysis)
        self.logger.info("마스크 감지(외부) 모듈 = ", self.use_external_mask_analysis)
        self.logger.info("거리두기 감지(외부) 모듈 = ", self.use_external_distance_analysis)

        # 고온 감지용(내부 모듈)
        if self.use_internal_temperature_analysis == True:
            rospy.Subscriber("/hikvision_thermal_camera_node/face_temperature", String, self.on_internal_analysis_temperature)
        
        # 마스크, 거리두기 감지용(내부 모듈)
        if self.use_internal_mask_analysis == True or self.use_internal_distance_analysis == True:
            rospy.Subscriber("/pedestrian_detector/pedestrians", Pedestrians, self.on_internal_analysis_mask_and_distance)
        
        # 마스크, 거리두기 감지용(외부 모듈)
        if self.use_external_mask_analysis == True or self.use_external_distance_analysis == True:
            rospy.Subscriber("/rgbd/rgb/image_rect_color_throttle", Image, self.on_external_analysis_rgb_for_mask_and_distance)
            rospy.Subscriber("/rgbd/depth/points_throttle", PointCloud2, self.on_external_analysis_depth_for_mask_and_distance)

        # UI 전송용 이미지
        rospy.Subscriber("/rgbd/rgb/image_raw/compressed", CompressedImage, self.on_rgb_img_for_ui)
        rospy.Subscriber("/rtsp02/image_raw/compressed", CompressedImage, self.on_thermal_img_for_ui)
        
        # inspection.py에서 request listener
        self.add_listener(self.make_node("{namespace}/agent_analysis_data/transfer_image"), self.on_analysis_data)

        return ResponseInfo()

    def on_resume(self, event):
        return ResponseInfo()

    def on_loop(self):
        return ResponseInfo()

    def on_pause(self, event):
        return ResponseInfo()

    def on_destroy(self, event):
        return ResponseInfo()

    def register_cctv_analysis_server(self):
        response = None

        try:
            event_type = {
                'temperature': 0,
                'mask': 1 if self.use_external_mask_analysis == True else 0,
                'distance': 1 if self.use_external_distance_analysis == True else 0,
                'fall_down': 0,
                'fire': 0
            }

            request_body = {
                "cctv_id": self.cctv_id,
                "cctv_type": self.cctv_type,
                "event_type": event_type,
            }

            response = requests.post(
                url=self.server_url + self.post_register_api,
                json=request_body
            )

            self.logger.info("\n\n <<<<<<<<<< Register CCTV Server Response Status Code = {} >>>>>>>>>> \n\n".format(response.status_code))

        except Exception:
            response = None

        return response

    # 고온 감지(내부 모듈) callback function
    def on_internal_analysis_temperature(self, res):
        res_str = res.data.split(",")
        self.detect_temperature = True if float(res_str[1]) > float(self.threshold_temp) else False

    # 마스크, 거리두기 감지(내부 모듈) callback function
    def on_internal_analysis_mask_and_distance(self, res):
        if self.use_internal_mask_analysis == True:
            faces = res.faces
            
            if len(faces) > 0:
                for face in faces:
                    if self.get_distance_2d_array(face.position) > self.threshold_mask:
                        continue
                
                    if face.with_mask == False:
                        rect = dict()

                        # 화면 크기에 맞춰 정규화
                        rect["rect"] = str(
                            [
                                [float(face.bbox.xmin)/self.screen_width, float(face.bbox.ymin)/self.screen_height],
                                [float(face.bbox.xmax)/self.screen_width, float(face.bbox.ymax)/self.screen_height],
                            ]
                        )
                        self.detect_mask.append(rect)

                        self.logger.info("=========== Callback Function ==========", self.detect_mask)

        if self.use_internal_distance_analysis == True:
            pedestrians = res.pedestrians
            pedestrians_num = len(pedestrians)

            if pedestrians_num <= 1:
                self.detect_distance = False

            else:
                for i in range(pedestrians_num-1):
                    if self.get_distance_2d_array(pedestrians[i].position) > self.threshold_dist:
                        continue

                    for j in range(i+1, pedestrians_num):
                        if self.get_distance_2d_array(pedestrians[j].position) > self.threshold_dist:
                            continue

                        x1 = pedestrians[i].position.point.x
                        y1 = pedestrians[i].position.point.y
                        z1 = pedestrians[i].position.point.z
                        x2 = pedestrians[j].position.point.x
                        y2 = pedestrians[j].position.point.y
                        z2 = pedestrians[j].position.point.z
                        
                        distance = ((((x2 - x1 )**2) + ((y2-y1)**2) + ((z2-z1)**2) )**0.5)

                        if distance < 1.0:
                            self.detect_distance = True

    def get_distance_2d_array(self, position):
        dist = math.sqrt(position.point.x*position.point.x + position.point.y*position.point.y)
        return dist

    # 마스크, 거리두기 감지용(외부 모듈) - RGB 데이터
    def on_external_analysis_rgb_for_mask_and_distance(self, data):
        self.rgbd_width = data.width
        self.rgbd_height = data.height

        cv_bridge = CvBridge()
        cv_image = cv_bridge.imgmsg_to_cv2(data, "passthrough")
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

        encoded_data = cv2.imencode('.jpg', cv_image)[1].tobytes()

        self.rgbd_image = base64.b64encode(encoded_data)

    # 마스크, 거리두기 감지용(외부 모듈) - DEPTH 데이터
    def on_external_analysis_depth_for_mask_and_distance(self, data):
        pc = ros_numpy.numpify(data)
        
        if len(pc.shape) == 1:
            pc = np.expand_dims(pc, axis=0)

        self.depth_height, self.depth_width = pc.shape[:2]

        distance_matrix = []
        fields = pc.dtype.names[:3]  # [x, y, z]
        np_points = np.zeros((self.depth_height * self.depth_width, len(fields)), dtype=np.float32)
        
        for i, f in enumerate(fields):
            np_points[:, i] = pc[f].flatten()

        for a in np_points:
            distance_matrix.append(a)

        distance_matrix = np.array(distance_matrix)

        self.depth_image = base64.b64encode(distance_matrix)

    # UI 전송용 - RGB 데이터
    def on_rgb_img_for_ui(self, data):
        self.raw_rgbd_image = base64.b64encode(data.data)
    
    # UI 전송용 - THERMAL 데이터
    def on_thermal_img_for_ui(self, data):
        self.raw_thermal_image = base64.b64encode(data.data)

    '''
        * 내부 모듈인 경우 먼저 데이터를 저장하고 결과를 보내줘야 한다.
        * 외부 모듈인 경우 1초 정도 delay가 생긴다.
        * 우선 순위: 고온 > 마스크 > 거리두기

        1. 고온 감지(내부 모듈) 결과 저장
        2. 마스크 미착용 감지(내부 모듈) 결과 저장
        3. 사회적거리두기 위반 감지(내부 모듈) 결과 저장        
        4. 영상 분석 서버에 분석 의뢰
            4.1. 이미지 전송
            4.2. 분석 결과 request
                4.2.1. 마스크 미착용 감지(외부 모듈)시 결과 저장
                4.2.2. 사회적 거리두기 위반 감지(외부 모듈)시 결과 저장
        5. 결과 전송
    '''
    # inspection에서 요청하는 event listener
    def on_analysis_data(self, res):
        self.logger.info("\n\n 영상 분석 시작 !!!")

        event_result = {
            "temperature": False,
            "mask": [],
            "distance": False
        }
        event_image = None
        result_data = {}

        # 1. 고온 감지(우선 순위 1)
        if self.detect_temperature == True:
            event_image = self.raw_thermal_image
            self.publish(self.make_node("{namespace}/agent_analysis_data/thermal_detected_data"), {"data": event_image})

            event_result["temperature"] = self.detect_temperature
            result_data["state"] = "mode_temperature"
            result_data["event_result"] = event_result
            self.publish(self.make_node("{namespace}/robot_scenario/event"), result_data)
                
        # 2. 마스크 감지(우선 순위 2)
        elif len(self.detect_mask) > 0:
            self.logger.info("\n\n Detected Mask !!!")

            event_image = self.raw_rgbd_image
            self.publish(self.make_node("{namespace}/agent_analysis_data/rgbd_detected_data"), {"data": event_image})

            event_result["mask"] = self.detect_mask
            result_data["state"] = "mode_mask"
            result_data["event_result"] = event_result
            self.publish(self.make_node("{namespace}/robot_scenario/event"), result_data)

        # 3. 거리두기 감지(우선 순위 3)
        elif self.detect_distance == True:
            event_image = self.raw_rgbd_image
            self.publish(self.make_node("{namespace}/agent_analysis_data/rgbd_detected_data"), {"data": event_image})

            event_result["distance"] = self.detect_distance
            result_data["state"] = "mode_distance"
            result_data["event_result"] = event_result
            self.publish(self.make_node("{namespace}/robot_scenario/event"), result_data)

        else:
            self.logger.info("\n\n End Data Ananlysis!!!")
            self.logger.info("\n\n 감지가 안된 경우이므로 다시 inspection 시작")
            self.publish(self.make_node("{namespace}/agent_analysis_data/analysis_ready"), {})

__class = MyLoop
if __name__ == "__main__":
    signal.signal(signal.SIGINT, exit)
    try:
        wrapper = RosWrapper(
            __class,
            manifest_path=os.path.join(
                os.path.dirname(__file__), "app_agent_analysis.yaml"
            ),
        )
    except:
        traceback.print_exc()