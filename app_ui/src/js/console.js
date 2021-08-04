const INSPECTION_MODE = 0
const QUARANTINE_MODE = 1
const INSPECTION_MODE_NAME = "inspection"
const QUARANTINE_MODE_NAME = "quarantine"

app.controller("BodyCtrl", function ($scope, $http) {
    bodyScope = $scope

    $scope.params_complete = false
    $scope.nats_complete = false

    $scope.getLang = (key) => {
        if ($scope.lang_v2 != undefined && key != undefined) {
            if ($scope.lang_v2[key])
                return $scope.lang_v2[key][$scope.lang_num]
            else
                console.warn(key)
        } else {
            return ''
        }
    }

    $scope.ui_initialize = function () {
        $scope.view_mode = "secure"
    }

    $scope.ui_initialize()

    $scope.check_initialized = (msg) => {
        console.log('** ', msg, ' initialized **')

        if (msg == 'params')
            $scope.params_complete = true
        else if (msg == 'nats')
            $scope.nats_complete = true

        if ($scope.params_complete && $scope.nats_complete) {
            $scope.Initializing()
        }
    }

    $scope.Initializing = () => {
        console.log('** angularjs initializing start **')

        $scope.style = {};
        $scope.detail_mode

        $scope.currentMenu = 0;
        $scope.remote_type = "user" // user | master
        $scope.driving_mode = "auto" // auto | manual

        $scope.in_docking = false

        $scope.popup_visible = false;
        $scope.popup_restart_visible = false;

        $scope.battery = 90;

        $scope.rec_state = REC_STATE_WAIT
        $scope.touch_style = {}

        $scope.cur_time
        setInterval(() => {
            $scope.cur_time = moment().format('llll');
            safeApply($scope, function ($scope) {})
        }, 1000);

        $scope.time_offset_prev = Number.parseInt(TIME_OFFSET_PREV)
        $scope.time_offset_next = Number.parseInt(TIME_OFFSET_NEXT)

        $("#slider").ionRangeSlider({
            type: "double",
            skin: "round",
            postfix: "분",
            min: -50,
            max: 50,
            from: $scope.time_offset_prev,
            to: $scope.time_offset_next,
            grid: false,
            from_min: -50, // set min position for FROM handle (replace FROM to TO to change handle)
            from_max: 0, // set max position for FROM handle
            from_shadow: false, // highlight restriction for FROM handle
            to_min: 0, // set min position for FROM handle (replace FROM to TO to change handle)
            to_max: 50, // set max position for FROM handle
            to_shadow: true, // highlight restriction for FROM handle
            onChange: function (data) {
                $scope.time_offset_prev = data.from
                $scope.time_offset_next = data.to

                safeApply($scope, function ($scope) {})
            },
        });
        var slider = $("#slider").data("ionRangeSlider");
        slider.reset();

        $('#battery_progressbar').val($scope.battery)

        $("#touch_test").bind("touchstart mousedown", function (e) {
            if (e.changedTouches != null) {
                $scope.touch_style.left = e.changedTouches[0].pageX
                $scope.touch_style.top = e.changedTouches[0].pageY
            }
        })

        $('#volume_slider').rangeslider({
            polyfill: false,
            rangeClass: 'rangeslider',
            fillClass: 'rangeslider__fill',
            handleClass: 'rangeslider__handle2',

            onSlide: function (position, value) {
                safeApply($scope, function ($scope) {
                    $scope.volume = value;
                })
            },
            onSlideEnd: function (position, value) {
                console.log('volume call', $scope.volume)
            }
        });

        $scope.onMapBoxListRefresh();

        $.getJSON('../tools/command/getvolume', function (data) {
            safeApply($scope, function ($scope) {
                console.log('current volume ', data)
                $scope.volume = parseInt(data.message)
                $('#volume_slider').val($scope.volume).change();
            })
        })

        $.getJSON('../document/preferences')
            .then((doc) => {
                console.log('preferences = ', doc)

                if (doc["MODE"] == "inspection") {
                    $scope.service_mode = INSPECTION_MODE
                    $scope.service_mode_name = "감시모드"
                } else {
                    $scope.service_mode = QUARANTINE_MODE
                    $scope.service_mode_name = "방역모드"
                }
            })

        $.getJSON('../document/schedule')
            .then((doc) => {
                console.log('schedule = ', doc)
                $scope.schedule_list = doc
                safeApply($scope, function (bodyScope) {})

                return $.getJSON('../document/robot_infos')
            })
            .then((doc) => {
                $scope.robot_name = doc.ROBOT_ID
                $scope.robot_terminal = ROBOT_MATCH_TERMINAL[doc.TERMINAL]
                $scope.robot_zone = ROBOT_MATCH_ZONE[doc.ZONE]
                safeApply($scope, function (bodyScope) {})
            })

        // for handling immediate mission schedule
        $scope.immediate_mission_schedule_canceled = true;
        $scope.immediate_mission_schedule_hour = "00";
        $scope.immediate_mission_schedule_minute = "00";

        if ($scope.service_mode == INSPECTION_MODE) {
            $scope.gate = "230";
            $.getJSON('../document/immediate_schedule')
                .then((msg) => {
                    console.log('immediate schedule date : ', msg);

                    $scope.immediate_mission_schedule_canceled = msg.IMMEDIATE_MISSION_SCHEDULE_CANCELED;
                    $scope.immediate_mission_schedule_hour = msg.IMMEDIATE_MISSION_SCHEDULE_HOUR;
                    $scope.immediate_mission_schedule_minute = msg.IMMEDIATE_MISSION_SCHEDULE_MINUTE;

                    let today = new Date();
                    let cur_hour = today.getHours();
                    let cur_minute = today.getMinutes();

                    // Number to String
                    cur_hour = "" + cur_hour;
                    cur_minute = "" + cur_minute;

                    let immediate_hour_minute = $scope.immediate_mission_schedule_hour + $scope.immediate_mission_schedule_minute;
                    let cur_hour_minute = cur_hour + cur_minute;

                    // 현 시간이 긴급 스케줄 시간을 지났다면 UI 초기화
                    if (cur_hour_minute > immediate_hour_minute) {
                        $scope.immediate_mission_schedule_canceled = true;
                        $scope.immediate_mission_schedule_hour = "00";
                        $scope.immediate_mission_schedule_minute = "00";
                        $scope.gate = "230";
                    }

                    safeApply($scope, function (bodyScope) {});
                });

        } else {
            $scope.location = "230";
            $.getJSON('../document/immediate_schedule')
                .then((msg) => {
                    console.log('immediate schedule date : ', msg);

                    $scope.immediate_mission_schedule_canceled = msg.IMMEDIATE_MISSION_SCHEDULE_CANCELED;
                    $scope.immediate_mission_schedule_hour = msg.IMMEDIATE_MISSION_SCHEDULE_HOUR;
                    $scope.immediate_mission_schedule_minute = msg.IMMEDIATE_MISSION_SCHEDULE_MINUTE;

                    let today = new Date();
                    let cur_hour = today.getHours();
                    let cur_minute = today.getMinutes();

                    // Number to String
                    cur_hour = "" + cur_hour;
                    cur_minute = "" + cur_minute;

                    let immediate_hour_minute = $scope.immediate_mission_schedule_hour + $scope.immediate_mission_schedule_minute;
                    let cur_hour_minute = cur_hour + cur_minute;

                    // 현 시간이 긴급 스케줄 시간을 지났다면 UI 초기화
                    if (cur_hour_minute > immediate_hour_minute) {
                        $scope.immediate_mission_schedule_canceled = true;
                        $scope.immediate_mission_schedule_hour = "00";
                        $scope.immediate_mission_schedule_minute = "00";
                        $scope.location = "W_101";
                    }

                    safeApply($scope, function (bodyScope) {});
                });
        }

        $scope.immediate_charging_schedule_hour = "00";
        $scope.immediate_charging_schedule_minute = "00"

        $.getJSON('../document/immediate_charging_schedule')
            .then((msg) => {
                console.log('즉시 충전 스케줄 = ', msg);

                const isCanceld = msg.IMMEDIATE_CHARGING_SCHEDULE_CANCELED;
                let chFormat = "";

                if (!isCanceld) {
                    chFormat = msg.IMMEDIATE_CHARGING_SCEHDULE_TIME; // YYYY-MM-DD HH:MM:00
                    $scope.immediate_charging_schedule_hour = chFormat.split(" ")[1].split(":")[0];
                    $scope.immediate_charging_schedule_minute = chFormat.split(" ")[1].split(":")[1];
                }

                $scope.in_docking = !isCanceld;

                const nowTime = new Date();
                const chTime = new Date(chFormat);

                // 현 시간이 즉시 충전 스케줄 시간을 지났다면 UI 초기화
                if (nowTime > chTime) {
                    isCanceled = true;
                    $scope.immediate_charging_schedule_hour = "00";
                    $scope.immediate_charging_schedule_minute = "00";
                }

                // 즉시 충전 스케줄을 취소했다면 UI 초기화
                else if (isCanceld) {
                    $scope.remain_charging_time = `서비스 재개 예정시간 ${"00"}:${"00"}:${"00"}`
                }

                safeApply($scope, function (bodyScope) {});
            });

        $scope.getClock = () => {
            const nowTime = new Date()
            const schTime = new Date()

            schTime.setHours(parseInt($scope.immediate_charging_schedule_hour))
            schTime.setMinutes(parseInt($scope.immediate_charging_schedule_minute))
            schTime.setSeconds(0);

            let diffTime = new Date();
            diffTime.setHours(schTime.getHours() - nowTime.getHours())
            diffTime.setMinutes(schTime.getMinutes() - nowTime.getMinutes())
            diffTime.setSeconds(schTime.getSeconds() - nowTime.getSeconds())

            if (!$scope.in_docking) {
                $scope.diffHours = "00"
                $scope.diffMinutes = "00"
                $scope.diffSeconds = "00"
            } else {
                $scope.diffHours = diffTime.getHours().toString().padStart(2, "0")
                $scope.diffMinutes = diffTime.getMinutes().toString().padStart(2, "0")
                $scope.diffSeconds = diffTime.getSeconds().toString().padStart(2, "0")
            }
            safeApply($scope, function (bodyScope) {});
        }

        setInterval(() => {
            $scope.getClock()
            $scope.remain_charging_time = `서비스 재개 예정시간 ${$scope.diffHours}:${$scope.diffMinutes}:${$scope.diffSeconds}`

            safeApply($scope, function ($scope) {})
        }, 1000);

        $scope.operation_mode = 'normal'

        var list = document.querySelectorAll(".demo-key");
        var keys = ["1", "2", "3", "CLR", "4", "5", "6", "0", "7", "8", "9", "OK",
            "1", "2", "3", "CLR", "4", "5", "6", "0", "7", "8", "9", "OK",
            "1", "2", "3", "CLR", "4", "5", "6", "0", "7", "8", "9", "OK"
        ];
        for (var i = 0; i < list.length; i++) {
            list[i].param = {
                key: keys[i]
            };
            list[i].addEventListener("mousedown", onClickPw);
        }

        $scope.operating_time = 'default_service_time : ' + DEFAULT_SERVICE_TIME
        $scope.battery_threshold = Number.parseInt(THRESHOLD_BATTERY)
        $scope.time_threshold = Number.parseInt(THRESHOLD_TIME)

        $scope.service_runtime = SERVICE_RUNTIME;
        $scope.time_offset_prev = TIME_OFFSET_PREV;
        $scope.time_offset_next = TIME_OFFSET_NEXT;

        LED_SET_COLOR(LED_DEVICE_BOTTOM, LED_COLOR_OFF)
        LED_SET_COLOR(LED_DEVICE_HEAD, LED_COLOR_OFF)
        lpt_control(0, 0, 0)

        $("#runtime_slider").ionRangeSlider({
            skin: "round",
            postfix: "분",
            min: 0,
            max: 100,
            step: 1,
            from: $scope.service_runtime,
            grid: false,
            onChange: function (data) {
                safeApply($scope, function ($scope) {
                    $scope.service_runtime = data.from;
                })
            },
        });
        var runtime_slider = $("#runtime_slider").data("ionRangeSlider");
        runtime_slider.reset();

        $scope.charging_time_value = Number.parseInt(CHARGING_TIME)
        $('#charging_slider').val($scope.charging_time_value).change()

        $scope.battery_low = Number.parseInt(LOW_BATTERY)
        $('#low_slider').val($scope.battery_low).change()

        $scope.battery_enough = Number.parseInt(ENOUGH_BATTERY)
        $('#enough_slider').val(bodyScope.battery_enough).change()

        safeApply($scope, function (bodyScope) {})

        console.log('** angular initializing complete **')
    }

    $scope.onClickLeftMenu = function (idx) {
        if ($scope.is_demo_setting)
            $scope.showPopup()
        else
            $scope.currentMenu = idx;
    }

    $scope.showPopup = function () {
        $scope.popup_visible = !$scope.popup_visible;
    }

    $scope.closePopup = function () {
        $scope.operation_mode = 'demo'
        $scope.popup_visible = !$scope.popup_visible;
    }

    $scope.showRestartPopup = function () {
        $scope.popup_restart_visible = !$scope.popup_restart_visible;
    }

    $scope.closeRestartPopup = function () {
        $scope.popup_restart_visible = !$scope.popup_restart_visible;
    }

    $scope.changeServiceMode = function (mode) {
        if (mode == 0) {
            console.log("감시모드를 선택했습니다")
            $scope.service_mode = INSPECTION_MODE
            $scope.change_service_mode_name = INSPECTION_MODE_NAME
            $scope.service_mode_name = "감시모드"
            $scope.popup_restart_visible = !$scope.popup_restart_visible;
        } else {
            console.log("방역모드를 선택했습니다")
            $scope.service_mode = QUARANTINE_MODE
            $scope.change_service_mode_name = QUARANTINE_MODE_NAME
            $scope.service_mode_name = "방역모드"
            $scope.popup_restart_visible = !$scope.popup_restart_visible;
        }

        $.getJSON('../document/preferences')
            .then((msg) => {
                console.log(msg)
                msg.MODE = $scope.change_service_mode_name

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })


        $.getJSON('../document/schedule')
            .then((msg) => {
                console.log("schedule = ", msg)
                msg = []

                var body = {
                    filename: 'schedule',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })
    }

    $scope.onRestart = async function () {
        var body = {}

        $.post('../tools/command/reboot', body, (msg) => {
            console.log(msg)
        })
    }

    $scope.onClickDetailClose = function (e) {
        console.log("onClickDetailClose");
        if ($('.chart_ct').css('display') != 'none') {
            $scope.closeChart()
        } else {
            $scope.view_mode = 'menu'
        }
    }

    $scope.onClickDetail = function (cur, detail) {
        $scope.view_mode = 'detail'
        $scope.detail_mode = detail
    }

    $scope.onClickLocationControl = function (e) {
        $scope.view_mode = 'map'

        setTimeout(() => {
            mapScope.map.setup({
                camera: {
                    x: mapScope.pos.x,
                    y: mapScope.pos.y,
                }
            });

        }, 200);
    }

    $scope.onRefreshSchedule = function () {
        $.getJSON('../document/schedule')
            .then((doc) => {
                console.log('schedule = ', doc)
                $scope.schedule_list = doc
                safeApply($scope, function (bodyScope) {})
            })
    }

    $scope.onSaveVolume = function () {
        let body = {
            volume: $scope.volume
        }

        $.post('../tools/command/setvolume', body, msg => {
            console.log(msg)
        })
    }

    $scope.onSaveThreshold = function () {
        console.log($scope.battery_threshold, $scope.time_threshold)
        $.getJSON('../document/preferences')
            .then((msg) => {
                console.log(msg)
                msg.THRESHOLD_BATTERY = $('#quantity2').val()
                msg.THRESHOLD_TIME = $('#quantity').val()

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })
    }

    $scope.onClickManualStart = function (e) {
        if (manual_action)
            manual_action.cancel()
        setTimeout(async () => {
            var goal = {
                goal: {
                    collision_detection: false
                }
            }

            var node = namespace + '/workerbee_navigation/manual_driving'
            manual_action = new Requester(nats, NATS_CONFIG.robotName, node, msg => {
                console.log(msg)
                $scope.driving_mode = 'auto'
                var txt = 'Stopped '
                if (msg.body != null && msg.body.state != null)
                    if (msg.body.state.action_state.code == 1) {
                        msg.body.state.action_state.faults.forEach(ele => {
                            txt += ele.name + ' '
                        });
                    }

                $scope.driving_mode_failed = txt
                safeApply($scope, function ($scope) {})
            }, (msg) => {
                // console.log(msg)
            })
            var result = await manual_action.request(goal)
            console.log(result)
        }, 500)
        $scope.driving_mode = 'manual'
        $scope.driving_mode_failed = 'STARTED'
    }

    $scope.onClickManualStop = function (e) {
        if (manual_action)
            manual_action.cancel()
    }

    $scope.onSetOperatingTime = () => {
        $scope.show_keyboard_operating = true
    }

    $scope.onAddChargingTime = () => {
        $scope.show_keyboard_charging = true
    }

    $scope.onReviseChargingTime = () => {
        $scope.show_keyboard_charging = true
    }

    $scope.onRemoveChargingTime = (idx) => {
        $scope.charging_schedule.splice(idx, 1)
        $scope.sort_list()
        $scope.write_schedule()
    }

    $scope.sort_list = () => {
        $scope.charging_schedule.sort(function (a, b) {
            if (a.start_time > b.start_time)
                return 1;
            else
                return -1;
        })
    }

    $scope.onClickRegister = function () {
        var start_time = document.getElementById("start_time_box").value;
        var end_time = document.getElementById("end_time_box").value;

        // mission_data_array["start_time"] = start_time_box
        mission_data_array["start_time"] = start_time
        mission_data_array["end_time"] = end_time
        mission_data_array["mission"] = mission_path
        mission_data_array["repeat"] = repeat_path_value

        ordinary_data = $scope.schedule_list;
        ordinary_data[ordinary_data.length] = mission_data_array;
        $scope.schedule_list = ordinary_data;

        $scope.write_schedule();

        $scope.view_mode = 'menu'
    }

    $scope.getSelectBoxValue = function () {
        mission_path = document.getElementById("mission_select").value;
    }

    $scope.getCheckBoxValue = function () {
        var repeat_path = document.getElementById("cb");
        repeat_path_value = $(repeat_path).prop("checked");
    }

    $scope.makeHourSelectBox = function () {
        $('#hour_select').children('option').remove();

        var Html = [];
        var value = "";

        for (var i = 0; i < 24; i++) {
            if (i < 10) {
                value = "0" + i;
            } else {
                value = i;
            }

            Html[i] = "<option value = " + i + ">" + value + "</option>;"
        }

        $("#hour_select").append(Html.join(''));
    }

    $scope.makeMinuteSelectBox = function () {
        $('#minute_select').children('option').remove();

        var Html = [];
        var value = "";

        for (var i = 0; i < 60; i += 10) {
            if (i < 10) {
                value = "0" + i;
            } else {
                value = i;
            }

            Html[i] = "<option value = " + i + ">" + value + "</option>;"
        }

        $("#minute_select").append(Html.join(''));
    }

    $scope.makeGateSelectBox = function () {
        $('#gate_select').children('option').remove();

        var gate_list = [230, 231, 232, 233, 246, 247, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 245, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 254, 266, 267, 268, 269, 270];
        gate_list = gate_list.filter((x, idx) => idx === gate_list.indexOf(x)); // 중복 제거

        // 오름차순 정렬
        gate_list = gate_list.sort((a, b) => {
            return a - b;
        });

        console.log("gate_list = ", gate_list)
        var Html = [];

        for (var i = 0; i < gate_list.length; i++) {
            Html[i] = "<option value = " + i + ">" + String(gate_list[i]) + "</option>;"
        }

        $("#gate_select").append(Html.join(''));
    }

    $scope.makeLocationSelectBox = function () {
        $('#location_select').children('option').remove();

        var location_list = ["W_101", "W_102", "W_103", "E_101", "E_102", "E_103"];
        location_list = location_list.filter((x, idx) => idx === location_list.indexOf(x));
        location_list = location_list.sort((a, b) => {
            return a - b;
        });
        var Html = [];

        for (var i = 0; i < location_list.length; i++) {
            Html[i] = "<option value = " + i + ">" + String(location_list[i]) + "</option>;"
        }

        $("#location_select").append(Html.join(''));
    }

    $scope.write_schedule = () => {
        console.log("write_schedule function is called !!!");

        if ($scope.service_mode == INSPECTION_MODE) {

            $scope.immediate_mission_schedule_hour = $("#hour_select option:selected").text();
            $scope.immediate_mission_schedule_minute = $("#minute_select option:selected").text();
            $scope.gate = $("#gate_select option:selected").text();
            $scope.immediate_mission_schedule_canceled = false;

            console.log("end hour : ", $scope.immediate_mission_schedule_hour);
            console.log("end_minute : ", $scope.immediate_mission_schedule_minute);
            console.log("gate : ", $scope.gate);

            nats.publish(namespace + '/schedule/write_immediate_mission', {
                gate: $scope.gate,
                end_time: $scope.immediate_mission_schedule_hour + ":" + $scope.immediate_mission_schedule_minute + ":" + "00"
            });

            var msg = {
                "IMMEDIATE_MISSION_SCHEDULE_HOUR": $scope.immediate_mission_schedule_hour,
                "IMMEDIATE_MISSION_SCHEDULE_MINUTE": $scope.immediate_mission_schedule_minute,
                "GATE": $scope.gate,
                "IMMEDIATE_MISSION_SCHEDULE_CANCELED": $scope.immediate_mission_schedule_canceled
            };

        } else {

            $scope.immediate_mission_schedule_hour = $("#hour_select option:selected").text();
            $scope.immediate_mission_schedule_minute = $("#minute_select option:selected").text();
            $scope.location = $("#location_select option:selected").text();
            $scope.immediate_mission_schedule_canceled = false;

            console.log("end hour : ", $scope.immediate_mission_schedule_hour);
            console.log("end_minute : ", $scope.immediate_mission_schedule_minute);
            console.log("location : ", $scope.location);

            nats.publish(namespace + '/schedule/write_immediate_mission', {
                location: $scope.location,
                end_time: $scope.immediate_mission_schedule_hour + ":" + $scope.immediate_mission_schedule_minute + ":" + "00"
            });

            var msg = {
                "IMMEDIATE_MISSION_SCHEDULE_HOUR": $scope.immediate_mission_schedule_hour,
                "IMMEDIATE_MISSION_SCHEDULE_MINUTE": $scope.immediate_mission_schedule_minute,
                "LOCATION": $scope.location,
                "IMMEDIATE_MISSION_SCHEDULE_CANCELED": $scope.immediate_mission_schedule_canceled
            };

        }

        var body = {
            filename: 'immediate_schedule',
            data: JSON.stringify(msg),
            format: 'yaml'
        };

        $.post('../document/write', body, (msg) => {
            console.log(msg)
        });
    }

    $scope.cancel_schedule = () => {
        if ($scope.service_mode == INSPECTION_MODE) {
            // 화면의 select 박스 옵션 값 디폴트로 초기화
            $('#hour_select').val('0').prop('selected', true);
            $('#minute_select').val('0').prop('selected', true);
            $('#gate_select').val('0').prop('selected', true);

            // scope 변수도 디폴트 옵션 값으로
            $scope.immediate_mission_schedule_hour = $("#hour_select option:selected").text();
            $scope.immediate_mission_schedule_minute = $("#minute_select option:selected").text();
            $scope.gate = $("#gate_select option:selected").text();
            $scope.immediate_mission_schedule_canceled = true;

            nats.publish(namespace + '/schedule/write_immediate_mission', {
                canceled: true
            });

            var msg = {
                "IMMEDIATE_MISSION_SCHEDULE_HOUR": $scope.immediate_mission_schedule_hour,
                "IMMEDIATE_MISSION_SCHEDULE_MINUTE": $scope.immediate_mission_schedule_minute,
                "GATE": $scope.gate,
                "IMMEDIATE_MISSION_SCHEDULE_CANCELED": $scope.immediate_mission_schedule_canceled
            };
        } else {
            // 화면의 select 박스 옵션 값 디폴트로 초기화
            $('#hour_select').val('0').prop('selected', true);
            $('#minute_select').val('0').prop('selected', true);
            $('#location_select').val('0').prop('selected', true);

            // scope 변수도 디폴트 옵션 값으로
            $scope.immediate_mission_schedule_hour = $("#hour_select option:selected").text();
            $scope.immediate_mission_schedule_minute = $("#minute_select option:selected").text();
            $scope.location = $("#location_select option:selected").text();
            $scope.immediate_mission_schedule_canceled = true;

            nats.publish(namespace + '/schedule/write_immediate_mission', {
                canceled: true
            });

            var msg = {
                "IMMEDIATE_MISSION_SCHEDULE_HOUR": $scope.immediate_mission_schedule_hour,
                "IMMEDIATE_MISSION_SCHEDULE_MINUTE": $scope.immediate_mission_schedule_minute,
                "LOCATION": $scope.location,
                "IMMEDIATE_MISSION_SCHEDULE_CANCELED": $scope.immediate_mission_schedule_canceled
            };
        }

        var body = {
            filename: 'immediate_schedule',
            data: JSON.stringify(msg),
            format: 'yaml'
        };

        $.post('../document/write', body, (msg) => {
            console.log(msg)
        });
    }

    $scope.onClickKeyClose = () => {
        $scope.show_keyboard_operating = false
        $scope.show_keyboard_charging = false
    }

    $scope.onChargingStart = async function () {
        const nowTime = new Date();
        const chTime = new Date();
        chTime.setMinutes(nowTime.getMinutes() + $scope.charging_time);

        const chForm = `${chTime.getFullYear()}-${(chTime.getMonth() + 1).toString().padStart(2, "0")}-${chTime.getDate().toString().padStart(2, "0")}` // YYYY-MM-DD 형식
        const chHour = chTime.getHours().toString().padStart(2, "0")
        const chMin = chTime.getMinutes().toString().padStart(2, "0")
        const reqForm = `${chForm} ${chHour}:${chMin}:00`

        $scope.immediate_charging_schedule_hour = chHour;
        $scope.immediate_charging_schedule_minute = chMin;
        $scope.immediate_charging_schedule_canceled = false;

        nats.publish(namespace + '/schedule/write_immediate_charging', {
            end_time: reqForm
        });

        var msg = {
            "IMMEDIATE_CHARGING_SCEHDULE_TIME": reqForm,
            "IMMEDIATE_CHARGING_SCHEDULE_CANCELED": $scope.immediate_charging_schedule_canceled
        };

        var body = {
            filename: 'immediate_charging_schedule',
            data: JSON.stringify(msg),
            format: 'yaml'
        };

        $.post('../document/write', body, (msg) => {
            console.log(msg)
        });

        $.getJSON('../document/preferences')
            .then((msg) => {
                msg.CHARGING_TIME = $scope.charging_time_value

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })

        $scope.in_docking = true

        await cancel_all_action()
        // callManager('idle')
    }

    $scope.onChargingStop = async function () {
        $scope.immediate_charging_schedule_hour = "00";
        $scope.immediate_charging_schedule_minute = "00";
        $scope.immediate_charging_schedule_canceled = true;
        $scope.remain_charging_time = `서비스 재개 예정시간 ${$scope.immediate_charging_schedule_hour}:${$scope.immediate_charging_schedule_minute}:${"00"}`

        nats.publish(namespace + '/schedule/write_immediate_charging', {
            canceled: true
        });

        var msg = {
            "IMMEDIATE_CHARGING_SCHEDULE_CANCELED": $scope.immediate_charging_schedule_canceled
        };

        var body = {
            filename: 'immediate_charging_schedule',
            data: JSON.stringify(msg),
            format: 'yaml'
        };

        $.post('../document/write', body, (msg) => {
            console.log(msg)
        });

        $.getJSON('../document/preferences')
            .then((msg) => {
                msg.CHARGING_TIME = 30

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })

        $scope.in_docking = false

        await cancel_all_action()
    }

    $scope.getDetailMode = () => {
        switch ($scope.detail_mode) {
            case 'network':
                return '네트워크 관리<br>(Network)'
            case 'unittest':
                return '개별 테스트<br>(Device Test)'
            case 'battery':
                return '배터리 잔량<br>(Battery Info)'
            case 'time_set':
                return 'Service Time Setting'
            case 'map_list':
                return '맵 목록<br>(Map list)'
            case 'language':
                return '언어 선택<br> (Language)'
            case 'mission':
                return 'Mission Setting'
        }
    }

    $scope.onClickServiceStart = function () {
        console.log("onClickServiceStart");
        console.log("현재 도킹 상태 : ", $scope.in_docking);
        if ($scope.in_docking)
            callManager('undocking');
        else
            callManager('idle');
    }

    $('#charging_slider').rangeslider({
        polyfill: false,
        rangeClass: 'rangeslider',
        fillClass: 'rangeslider__fill',
        handleClass: 'rangeslider__handle2',

        onInit: function () {
            $rangeEl = this.$range;

            // get range index labels 
            var rangeLabels = this.$element.attr('labels');
            rangeLabels = rangeLabels.split(', ');

            // add labels
            $rangeEl.append('<div class="rangeslider__labels"></div>');
            $(rangeLabels).each(function (index, value) {
                $rangeEl.find('.rangeslider__labels').append('<span class="rangeslider__labels__label" style="margin-top: -70px; font-size: 30px; font-weight: bold">' + value + '</span>');
            })
        },

        onSlide: function (position, value) {
            safeApply($scope, function ($scope) {
                if (value === 30) {
                    $scope.charging_time = 30;
                } else if (value === 60) {
                    $scope.charging_time = 60;
                } else if (value === 90) {
                    $scope.charging_time = 120;
                } else if (value === 120) {
                    $scope.charging_time = 240;
                } else if (value === 150) {
                    $scope.charging_time = 480;
                } else if (value === 180) {
                    $scope.charging_time = 900;
                }

                $scope.charging_time_value = value
                console.log("Charging Time = ", $scope.charging_time);
            })
        },
        onSlideEnd: function (position, value) {}
    });

    $('#low_slider').rangeslider({
        polyfill: false,
        rangeClass: 'rangeslider',
        fillClass: 'rangeslider__fill',
        handleClass: 'rangeslider__handle2',

        onSlide: function (position, value) {
            safeApply($scope, function ($scope) {
                $scope.battery_low = value;
            })
        },
        onSlideEnd: function (position, value) {}
    });

    $('#enough_slider').rangeslider({
        polyfill: false,
        rangeClass: 'rangeslider',
        fillClass: 'rangeslider__fill',
        handleClass: 'rangeslider__handle2',

        onSlide: function (position, value) {
            safeApply($scope, function ($scope) {
                $scope.battery_enough = value;
            })
        },
        onSlideEnd: function (position, value) {}
    });

    $scope.onSaveLow = function () {
        $.getJSON('../document/preferences')
            .then((msg) => {
                console.log(msg)
                msg.LOW_BATTERY = $scope.battery_low

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })
    }

    $scope.onSaveEnough = function () {
        $.getJSON('../document/preferences')
            .then((msg) => {
                console.log(msg)
                msg.ENOUGH_BATTERY = $scope.battery_enough

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })
    }

    $scope.onSaveServiceRuntime = function () {
        $.getJSON('../document/preferences')
            .then((msg) => {
                console.log(msg)
                msg.SERVICE_RUNTIME = $scope.service_runtime

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })
    }

    $scope.onSaveOffset = function () {
        $.getJSON('../document/preferences')
            .then((msg) => {
                console.log(msg)
                msg.TIME_OFFSET_PREV = $scope.time_offset_prev
                msg.TIME_OFFSET_NEXT = $scope.time_offset_next

                var body = {
                    filename: 'preferences',
                    data: JSON.stringify(msg),
                    format: 'yaml'
                }

                $.post('../document/write', body, (msg) => {
                    console.log(msg)
                })
            })
    }
});