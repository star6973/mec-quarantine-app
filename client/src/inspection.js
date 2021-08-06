import React, { useState } from "react";

// $scope.onRepeatInspecting = async (msg) => {
//     $scope.inspect_state = STATE_INSPECTING
//     $scope.image_result = STATE_LIVE

//     LED_FLOW(LED_DEVICE_HEAD, LED_COLOR_CYAN, LED_COLOR_OFF, 1, LED_DIRECTION_COUNTER, LED_REPEAT)
//     LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_CYAN)

//     safeApply($scope, function (bodyScope) {})
// }

// $scope.drawMaskRectangle = (result_data) => {
//     var canvas = $("#mask_result_canvas");
//     var context = null;
//     var rect = [];

//     if (canvas[0] !== undefined) {
//         context = canvas[0].getContext("2d");
//     } else {
//         context = canvas.getContext("2d");
//     }

//     context.clearRect(0, 0, 1280, 720);
//     context.beginPath();
//     for (var i = 0; i < result_data["mask"].length; i++) {
//         var rect = result_data["mask"][i]["rect"].replace(/[^0-9.,]/g, '').split(",");
//     }

//     context.strokStyle = 'black';
//     var rect_width = (parseFloat(rect[2]).toFixed(3) - parseFloat(rect[0]).toFixed(3)) * 300;
//     var rect_height = (parseFloat(rect[3]).toFixed(3) - parseFloat(rect[1]).toFixed(3)) * 150;

//     context.lineWidth = 3;
//     context.strokeStyle = "#FF0000";
//     context.strokeRect(parseFloat(rect[0]).toFixed(3) * 300 - 10, parseFloat(rect[1]).toFixed(3) * 150 - 10, rect_width + 20, rect_height + 20);

//     safeApply($scope, function (bodyScope) {})
// };

// $scope.onInspecting = async (msg) => {
//     var state = msg.state
//     var analysis_result = msg.event_result

//     switch (state) {
//         case 'moving':
//             console.log("move to inspection station ...")
//             $scope.inspect_state = STATE_MOVING

//             lpt_control(0, 0, 0)
//             lottieloader('inspecting_mv_lottie', '../src/img/moving.json', true, true)

//             LED_SET_COLOR(LED_DEVICE_HEAD, LED_COLOR_OFF)
//             LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_OFF)
//             break;

//         case 'inspecting':
//             console.log("start inspecting ...")
//             $scope.inspect_state = STATE_INSPECTING
//             $scope.image_result = STATE_LIVE

//             LED_FLOW(LED_DEVICE_HEAD, LED_COLOR_CYAN, LED_COLOR_OFF, 1, LED_DIRECTION_COUNTER, LED_REPEAT)
//             LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_CYAN)
//             break;

//         case 'mode_temperature':
//             $scope.inspect_state = STATE_TEMPERATURE
//             $scope.image_result = STATE_SNAPSHOT

//             LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_RED, 300, LED_COLOR_OFF, 300, LED_REPEAT)
//             LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_RED)

//             $("#temperature_result_image").attr('src', 'data:image/jpg;base64,' + $scope.thermal_image)

//             sound_and_speak('wa-prev-alert-faver2', 'Robot_Attention_1_Short', false, () => {
//                 nats.publish(namespace + '/inspection/event/ui_finish', {})

//                 $scope.onRepeatInspecting()
//                 safeApply($scope, function (bodyScope) {})
//             })
//             break;

//         case 'mode_mask':
//             $scope.inspect_state = STATE_MASK
//             $scope.image_result = STATE_SNAPSHOT

//             LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_RED, 300, LED_COLOR_OFF, 300, LED_REPEAT)
//             LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_RED)

//             if (analysis_result != undefined) {
//                 $scope.drawMaskRectangle(analysis_result)
//             }

//             $("#mask_result_image").attr('src', 'data:image/jpg;base64,' + $scope.rgb_image);                

//             sound_and_speak('wa-prev-alert-mask2', 'Robot_Attention_1_Short', false, () => {
//                 nats.publish(namespace + '/inspection/event/ui_finish', {})

//                 $scope.onRepeatInspecting()
//                 safeApply($scope, function (bodyScope) {})
//             })
//             break;

//         case 'mode_distance':
//             $scope.inspect_state = STATE_DISTANCE
//             $scope.image_result = STATE_SNAPSHOT

//             LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_RED, 300, LED_COLOR_OFF, 300, LED_REPEAT)
//             LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_RED)

//             $("#distance_result_image").attr('src', 'data:image/jpg;base64,' + $scope.rgb_image)

//             sound_and_speak('wa_prev-alert-distance', 'Robot_Attention_1_Short', false, () => {
//                 nats.publish(namespace + '/inspection/event/ui_finish', {})

//                 $scope.onRepeatInspecting()
//                 safeApply($scope, function (bodyScope) {})
//             })
//             break;
//     }
//     safeApply($scope, function (bodyScope) {})
// }

function Inspection() {
    const [lang, getLang] = useState();

    const STATE_MOVING = 'moving'
    const STATE_SETTING = 'setting'
    const STATE_INSPECTING = 'inspecting'
    const STATE_TEMPERATURE = 'temperature'
    const STATE_MASK = 'mask'
    const STATE_DISTANCE = 'distance'
    const STATE_LIVE = 'live'
    const STATE_SNAPSHOT = 'snapshot'

    bodyScope = $scope
    $scope.params_complete = false
    $scope.nats_complete = false
    $scope.is_speaking = false

    $scope.ui_initialize = function () {
        $scope.inspect_state = STATE_MOVING
        $scope.image_result = STATE_LIVE

        lottieloader('inspecting_mv_lottie', '../src/img/moving.json', true, true)
        
        LED_SET_COLOR(LED_DEVICE_HEAD, LED_COLOR_OFF)
        LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_OFF)
    }

    $scope.ui_initialize()

    $scope.check_initialized = (msg) => {
        if (msg == 'params')
            $scope.params_complete = true
        else if (msg == 'nats')
            $scope.nats_complete = true

        if ($scope.params_complete && $scope.nats_complete) {
            $scope.Initializing()
        }
    }

    $scope.onThermal = (msg) => {
        $scope.thermal_image = msg.data;
    }

    $scope.onRGB = (msg) => {
        $scope.rgb_image = msg.data;
    }

    // inspecting scenario의 초기 시작
    $scope.Initializing = () => {
        nats.addListener(namespace + '/robot_scenario/event', $scope.onInspecting);
        nats.addListener(namespace + '/agent_analysis_data/rgbd_detected_data', $scope.onRGB); // RGB 이미지를 계속 받고 있는 함수
        nats.addListener(namespace + '/agent_analysis_data/thermal_detected_data', $scope.onThermal); // Thermal 이미지를 계속 받고 있는 함수
        nats.publish(namespace + '/inspection/event/ui_ready', {})

        let params = getParams()
        $scope.end_time = params.end_time
        $scope.fever_degrees = 37.5
        $scope.rgb_image = null
        $scope.thermal_image = null
        $scope.end_time = decodeURIComponent($scope.end_time).replace('T', ' ')

        setTimeout(() => {
            let player = new JSMpeg.Player('ws://localhost:1234', {
                canvas: document.getElementById('canvas'),
                autoplay: true,
                audio: false,
                loop: true,
            });
            console.log("rtsp stream call success")
        }, 2000);
    }

    return (
        <div>
            <div id="inspecting_mv" ng-show="inspect_state == 'moving'">
                <div class="title_text_style" id="title">{{getLang("TEXT/MOVE/MOVE_TITLE")}}</div>
                <div class="title_sub_text_style" id="title_sub">{{getLang("TEXT/MOVE/MOVE_SUB_TITLE")}}</div>
                <div id="inspecting_mv_lottie"></div>
            </div>
            <div
                id="inspecting"
                ng-show="inspect_state != 'moving'"
                ng-class="{'background_red' : inspect_state != 'inspecting', 'background_blue' : inspect_state == 'inspecting'}">
                <div class="main_menu_top" ng-show="inspect_state == 'inspecting'">
                    <div class="title_text_style2" id="title">{{getLang("TEXT/INSPECT/INSPECTING_TITLE")}}</div>
                </div>
                <div class="main_menu_top" ng-show="inspect_state == 'temperature'">
                    <div class="title_text_style2" id="title">Fever over {{fever_degrees}} °C</div>
                </div>
                <div class="main_menu_top" ng-show="inspect_state == 'mask'">
                    <div class="title_text_style2" id="title">{{getLang("TEXT/INSPECT/MASK_SUB_TITLE")}}</div>
                </div>
                <div class="main_menu_top" ng-show="inspect_state == 'distance'">
                    <div class="title_text_style2" id="title">{{getLang("TEXT/INSPECT/DISTANCE_SUB_TITLE")}}</div>
                </div>
                <div class="main_menu_bottom">
                    <div class="bottom_left" ng-show="inspect_state == 'inspecting'">
                        <div class="img_items">
                            <img id="mask_img" src="./contents/img/inspection/medical-mask.png"/>
                            <img id="distance_img" src="./contents/img/inspection/physical_distancing.png"/>
                            <img id="quarantine_img" src="./contents/img/inspection/quarantine.png"/>
                        </div>
                        <div class="text_items">
                            <div class="title_sub_text_style2">{{getLang("TEXT/INSPECTING/MASK_IMAGE")}}</div>
                            <div class="title_sub_text_style2">{{getLang("TEXT/INSPECTING/DISTANCE_IMAGE")}}</div>
                            <div class="title_sub_text_style2">{{getLang("TEXT/INSPECTING/QUARANTINE_IMAGE")}}</div>
                        </div>
                    </div>
                    <div class="bottom_left2" ng-show="inspect_state == 'temperature'">
                        <img
                            id="alert_mask_img"
                            src="./contents/img/inspection/wa_prev-alert-fever.png"/>
                        <div class="title_sub_text_style3">{{getLang("TEXT/INSPECT/TEMPERATURE_TITLE")}}</div>
                    </div>
                    <div class="bottom_left2" ng-show="inspect_state == 'mask'">
                        <img
                            id="alert_fever_img"
                            src="./contents/img/inspection/wa_prev-alert-mask.png"/>
                        <div class="title_sub_text_style3">{{getLang("TEXT/INSPECT/MASK_TITLE")}}</div>
                    </div>
                    <div class="bottom_left2" ng-show="inspect_state == 'distance'"><img
                        id="alert_distance_img"
                        src="./contents/img/inspection/wa_prev-alert-distance.png"/>
                        <div class="title_sub_text_style3">{{getLang("TEXT/INSPECT/DISTANCE_TITLE")}}</div>
                    </div>
                    <div class="bottom_right" ng-show="image_result == 'live'">
                        <canvas id="canvas" style="width : 1280px; height: 720px;"></canvas>
                        <div class="title_sub_text_style4">Service end time: {{end_time}}</div>
                    </div>
                    <div class="bottom_right" ng-show="image_result == 'snapshot'">
                        <img
                            id="temperature_result_image"
                            ng-show="inspect_state == 'temperature'"
                            style="width : 1280px; height: 720px;"/>
                        <canvas
                            id="temperature_result_canvas"
                            ng-show="inspect_state == 'temperature'"
                            style="width : 1280px; height: 720px;" />
                        <img
                            id="mask_result_image"
                            ng-show="inspect_state == 'mask'"
                            style="width : 1280px; height: 720px; z-index: 1"/>
                        <canvas
                            id="mask_result_canvas"
                            ng-show="inspect_state == 'mask'"
                            style="width : 1280px; height: 720px; z-index: 2" />
                        <img
                            id="distance_result_image"
                            ng-show="inspect_state == 'distance'"
                            style="width : 1280px; height: 720px;"/>
                        <canvas
                            id="distance_result_canvas"
                            ng-show="inspect_state == 'distance'"
                            style="width : 1280px; height: 720px;" />
                        <div class="title_sub_text_style4">Service end time: {{end_time}}</div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Inspection;