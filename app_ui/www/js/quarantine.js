const STATE_MOVING = 'moving';
const STATE_QUARANTINE = 'quarantine';
let image_and_sound_dict = {}
let ui_apply = null;
var idx = 0;

app.controller("BodyCtrl", function ($scope, $http) {
    bodyScope = $scope;
    $scope.params_complete = false
    $scope.nats_complete = false

    $scope.getLang = (key) => {
        if ($scope.lang_v2 != undefined && key != undefined) {
            if ($scope.lang_v2[key]) {
                return $scope.lang_v2[key][$scope.lang_num];
            } else
                console.warn(key);
        } else {
            return '';
        }
    }

    $scope.ui_initialize = function () {
        $scope.quarantine_state = STATE_QUARANTINE;
        lottieloader('quarantine_mv_lottie', './contents/img/lottie/move/data.json', true, true);
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

    $scope.Initializing = () => {
        nats.addListener(namespace + '/robot_scenario/event', $scope.onQuarantine);
        nats.publish(namespace + '/inspection/event/ui_ready', {});

        $.getJSON('../document/quarantine')
        .then((img) => {
            for (let i=0; i<img.length; i++) {
                let use = Object.values(img)[i]["use"];
                let tmp = {};
                if (use == true) {
                    tmp["image"] = Object.values(img)[i]["image"];
                    tmp["speak"] = Object.values(img)[i]["speak"];
                    image_and_sound_dict[i] = tmp;
                }
            }
        })

        safeApply($scope, function (bodyScope) {});
    }

    ui_apply = function() {
        if (idx >= Object.keys(image_and_sound_dict).length) {
            idx = 0;
        }

        let image_url = Object.values(image_and_sound_dict)[idx]["image"];
        let speak_key = Object.values(image_and_sound_dict)[idx]["speak"].split(".")[0];
        let image_tag = document.getElementById("protect_img");

        // 이미지 전환
        image_tag.setAttribute("src", "/contents/img/quarantine/" + image_url);
        // 음성 발화
        create_quarantine_speak(speak_key);

        idx += 1;

        // check timestamp
        console.log("Now Time = ", new Date().toLocaleTimeString());
        safeApply($scope, function (bodyScope) {});
    }

    $scope.onQuarantine = async (msg) => {
        let service = msg.service;
        let state = msg.state;

        if (service == 'quarantine') {
            switch (state) {
                case 'moving':
                    console.log("move to quarantine station ...");
                    $scope.quarantine_state = STATE_MOVING;
    
                    lpt_control(0, 0, 0);
                    lottieloader('quarantine_mv_lottie', './contents/img/lottie/move/data.json', true, true);
    
                    LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_OFF);
                    break;
    
                case 'quarantine':
                    console.log("start quarantine service ...");
                    $scope.quarantine_state = STATE_QUARANTINE;
    
                    LED_FLOW(LED_DEVICE_HEAD, LED_COLOR_CYAN, LED_COLOR_OFF, 1, LED_DIRECTION_COUNTER, LED_REPEAT)
                    LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_CYAN)

                    // setInterval에서 설정해준 time만큼의 공백을 채워줄 수 있기 위해서 선언
                    let image_url = Object.values(image_and_sound_dict)[idx]["image"];
                    let speak_key = Object.values(image_and_sound_dict)[idx]["speak"].split(".")[0];
                    let image_tag = document.getElementById("protect_img");
                    image_tag.setAttribute("src", "/contents/img/quarantine/" + image_url);
                    create_quarantine_speak(speak_key);

                    idx += 1;

                    // check timestamp
                    console.log("Now Time = ", new Date().toLocaleTimeString());

                    setInterval("ui_apply()", 10000);
                    break;
            }
        }

        safeApply($scope, function (bodyScope) {})
    }
})