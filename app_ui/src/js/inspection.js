const STATE_MOVING = 'moving'
const STATE_SETTING = 'setting'
const STATE_INSPECTING = 'inspecting'
const STATE_TEMPERATURE = 'temperature'
const STATE_MASK = 'mask'
const STATE_DISTANCE = 'distance'
const STATE_LIVE = 'live'
const STATE_SNAPSHOT = 'snapshot'
var speak_inspect_instance = null;

app.controller("BodyCtrl", function ($scope, $http) {
    bodyScope = $scope
    $scope.params_complete = false
    $scope.nats_complete = false
    $scope.is_speaking = false

    // rsms language support로부터 비동기로 계속 값을 받아옴
    $scope.getLang = (key) => {
        if ($scope.lang_v2 != undefined && key != undefined) {
            if ($scope.lang_v2[key]) {
                return $scope.lang_v2[key][$scope.lang_num]
            } else
                console.warn(key)
        } else {
            return ''
        }
    }

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

        safeApply($scope, function (bodyScope) {})
    }

    $scope.onRepeatInspecting = async (msg) => {
        $scope.inspect_state = STATE_INSPECTING
        $scope.image_result = STATE_LIVE

        LED_FLOW(LED_DEVICE_HEAD, LED_COLOR_CYAN, LED_COLOR_OFF, 1, LED_DIRECTION_COUNTER, LED_REPEAT)
        LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_CYAN)

        safeApply($scope, function (bodyScope) {})
    }

    $scope.drawMaskRectangle = (result_data) => {
        var canvas = $("#mask_result_canvas");
        var context = null;
        var rect = [];

        if (canvas[0] !== undefined) {
            context = canvas[0].getContext("2d");
        } else {
            context = canvas.getContext("2d");
        }

        context.clearRect(0, 0, 1280, 720);
        context.beginPath();
        for (var i = 0; i < result_data["mask"].length; i++) {
            var rect = result_data["mask"][i]["rect"].replace(/[^0-9.,]/g, '').split(",");
        }

        context.strokStyle = 'black';
        var rect_width = (parseFloat(rect[2]).toFixed(3) - parseFloat(rect[0]).toFixed(3)) * 300;
        var rect_height = (parseFloat(rect[3]).toFixed(3) - parseFloat(rect[1]).toFixed(3)) * 150;

        context.lineWidth = 3;
        context.strokeStyle = "#FF0000";
        context.strokeRect(parseFloat(rect[0]).toFixed(3) * 300 - 10, parseFloat(rect[1]).toFixed(3) * 150 - 10, rect_width + 20, rect_height + 20);

        safeApply($scope, function (bodyScope) {})
    };

    $scope.onInspecting = async (msg) => {
        var state = msg.state
        var analysis_result = msg.event_result

        switch (state) {
            case 'moving':
                console.log("move to inspection station ...")
                $scope.inspect_state = STATE_MOVING

                lpt_control(0, 0, 0)
                lottieloader('inspecting_mv_lottie', '../src/img/moving.json', true, true)

                LED_SET_COLOR(LED_DEVICE_HEAD, LED_COLOR_OFF)
                LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_OFF)
                break;

            case 'inspecting':
                console.log("start inspecting ...")
                $scope.inspect_state = STATE_INSPECTING
                $scope.image_result = STATE_LIVE

                LED_FLOW(LED_DEVICE_HEAD, LED_COLOR_CYAN, LED_COLOR_OFF, 1, LED_DIRECTION_COUNTER, LED_REPEAT)
                LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_CYAN)
                break;

            case 'mode_temperature':
                $scope.inspect_state = STATE_TEMPERATURE
                $scope.image_result = STATE_SNAPSHOT

                LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_RED, 300, LED_COLOR_OFF, 300, LED_REPEAT)
                LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_RED)

                $("#temperature_result_image").attr('src', 'data:image/jpg;base64,' + $scope.thermal_image)

                sound_and_speak('wa-prev-alert-faver2', 'Robot_Attention_1_Short', false, () => {
                    nats.publish(namespace + '/inspection/event/ui_finish', {})

                    $scope.onRepeatInspecting()
                    safeApply($scope, function (bodyScope) {})
                })
                break;

            case 'mode_mask':
                $scope.inspect_state = STATE_MASK
                $scope.image_result = STATE_SNAPSHOT

                LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_RED, 300, LED_COLOR_OFF, 300, LED_REPEAT)
                LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_RED)

                if (analysis_result != undefined) {
                    $scope.drawMaskRectangle(analysis_result)
                }

                $("#mask_result_image").attr('src', 'data:image/jpg;base64,' + $scope.rgb_image);                

                sound_and_speak('wa-prev-alert-mask2', 'Robot_Attention_1_Short', false, () => {
                    nats.publish(namespace + '/inspection/event/ui_finish', {})

                    $scope.onRepeatInspecting()
                    safeApply($scope, function (bodyScope) {})
                })
                break;

            case 'mode_distance':
                $scope.inspect_state = STATE_DISTANCE
                $scope.image_result = STATE_SNAPSHOT

                LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_RED, 300, LED_COLOR_OFF, 300, LED_REPEAT)
                LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_RED)

                $("#distance_result_image").attr('src', 'data:image/jpg;base64,' + $scope.rgb_image)

                sound_and_speak('wa_prev-alert-distance', 'Robot_Attention_1_Short', false, () => {
                    nats.publish(namespace + '/inspection/event/ui_finish', {})

                    $scope.onRepeatInspecting()
                    safeApply($scope, function (bodyScope) {})
                })
                break;
        }
        safeApply($scope, function (bodyScope) {})
    }
})