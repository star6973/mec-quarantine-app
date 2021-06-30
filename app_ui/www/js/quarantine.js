const STATE_MOVING = 'moving';
const STATE_QUARANTINE = 'quarantine';
let image_and_sound_dict = {}
let speak_quarantine_instance = null;
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
            
            console.log(image_and_sound_dict);

            safeApply($scope, function (bodyScope) {})
        })

        safeApply($scope, function (bodyScope) {});
    }

    ui_apply = function() {
        if (idx >= Object.keys(image_and_sound_dict).length) {
            idx = 0;
        }

        let img = Object.values(image_and_sound_dict)[idx]["image"];
        let key = Object.values(image_and_sound_dict)[idx]["speak"].split(".")[0];
        let image_tag = document.getElementById("protect_img");

        image_tag.setAttribute("src", "/contents/img/quarantine/" + img);
        speak_quarantine_instance = create_quarantine_speak(key);

        idx += 1;
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

                    let img = Object.values(image_and_sound_dict)[idx]["image"];
                    let key = Object.values(image_and_sound_dict)[idx]["speak"].split(".")[0];

                    let image_tag = document.getElementById("protect_img");
                    image_tag.setAttribute("src", "/contents/img/quarantine/" + img);

                    idx += 1;
                    speak_quarantine_instance = create_quarantine_speak(key);
                    console.log("Now Time = ", new Date().toLocaleTimeString());
                    setInterval("ui_apply()", 10000);
                    
                    safeApply($scope, function (bodyScope) {});
                    break;
            }
        }

        safeApply($scope, function (bodyScope) {})
    }
})