const MAP_ZOOM_MIN = 0.1
const MAP_ZOOM_MAX = 5
const MAP_ZOOM_DEFAULT = 1
const MAP_ZOOM_MUL = 1.3
const MAP_ZOOM_LIST = [0.1, 0.13, 0.17, 0.22, 0.29, 0.38, 0.49, 0.64, 0.83, 1.08, 1.4, 1.82, 2.37, 3]

const REC_STATE_WAIT = 0
const REC_STATE_RECORDING = 1
const REC_STATE_RECORDED = 2

const RSP_STATE_WAIT = 0
const RSP_STATE_CONNECTED = 1
const RSP_STATE_DISCONNECTED = 2

const INSPECTION_MODE = 0
const QUARANTINE_MODE = 1

const INSPECTION_MODE_NAME = "inspection"
const QUARANTINE_MODE_NAME = "quarantine"

var remote_type = "user";

var manual_action

var lrf_count_front = 0
var lrf_test_front = false
var lrf_count_back = 0
var lrf_test_back = false
var imu_count = 0
var imu_test = false
var rgbd_front_test = false
var rgbd_rear_test = false
var thermal_test = false

var move_action

var mission_data_array = {}

// register data
var mission_path = ""
var repeat_path_value = false

const TEST_COUNT = 10

const FIRE_DETECT = 0
const HIGH_TEMPERATURE = 1

function onStatusData(msg) {

}

function onBatteryData(msg) {
    safeApply(bodyScope, function (bodyScope) {
        bodyScope.battery = parseInt(msg.batteries[0].voltage_level)
        $('#battery_progressbar').val(bodyScope.battery)
        bodyScope.battery_time = getTwoString(parseInt((bodyScope.battery * 2.4) / 60)) + " : " + getTwoString(parseInt((bodyScope.battery * 2.4) % 60))
    })
}

function onRGBDFrontTest(msg) {
    if (rgbd_front_test) {
        $("#test_cam").attr('src', 'data:image/jpg;base64,' + msg.data)
        rgbd_front_test = false
    }
}

function onRGBDRearTest(msg) {
    if (rgbd_rear_test) {
        $("#test_cam").attr('src', 'data:image/jpg;base64,' + msg.data)
        rgbd_rear_test = false
    }
}

function onThermalTest(msg) {
    if (thermal_test) {
        $("#test_cam").attr('src', 'data:image/jpg;base64,' + msg.data)
        thermal_test = false
    }
}

function onLrfFront(msg) {
    if (lrf_test_front) {
        if (lrf_count_front < TEST_COUNT) {
            lrf_count_front++
        } else if (lrf_count_front == TEST_COUNT) {
            lrf_test_front = false
            bodyScope.lrf_front_msg = 'OK'
            lrf_count_front = 0
        }
    }
}

function onLrfBack(msg) {
    if (lrf_test_back) {
        if (lrf_count_back < TEST_COUNT) {
            lrf_count_back++
        } else if (lrf_count_back == TEST_COUNT) {
            lrf_test_back = false
            bodyScope.lrf_back_msg = 'OK'
            lrf_count_back = 0
        }
    }
}

function onIMUData(msg) {
    if (imu_test) {
        if (imu_count < TEST_COUNT) {
            imu_count++
        } else if (imu_count == TEST_COUNT) {
            imu_test = false
            bodyScope.imu_msg = 'OK'
            imu_count = 0
        }
    }
}

function onDockingData(msg) {
    bodyScope.in_docking = msg.state
}

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
        $scope.view_mode = "secure" // secure | map | menu | detail
        // $scope.view_mode = "menu" // secure | map | menu | detail
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

        // for handling immediate charging schedule
        $scope.immediate_charging_schedule_canceled = true;
        $scope.immediate_charging_schedule_hour = "00";
        $scope.immediate_charging_schedule_minute = "00";

        $.getJSON('../document/immediate_charging_schedule')
            .then((msg) => {
                console.log('immediate schedule date : ', msg);

                $scope.immediate_charging_schedule_canceled = msg.IMMEDIATE_CHARGING_SCHEDULE_CANCELED;
                $scope.immediate_charging_schedule_hour = msg.IMMEDIATE_CHARGING_SCHEDULE_HOUR;
                $scope.immediate_charging_schedule_minute = msg.IMMEDIATE_CHARGING_SCHEDULE_MINUTE;
                $scope.in_docking = !msg.IMMEDIATE_CHARGING_SCHEDULE_CANCELED

                let today = new Date();
                let cur_hour = today.getHours();
                let cur_minute = today.getMinutes();

                // Number to String
                cur_hour = "" + cur_hour;
                cur_minute = "" + cur_minute;

                let immediate_hour_minute = $scope.immediate_charging_schedule_hour + $scope.immediate_charging_schedule_minute;
                let cur_hour_minute = cur_hour + cur_minute;

                // 현 시간이 긴급 스케줄 시간을 지났다면 UI 초기화
                if (cur_hour_minute > immediate_hour_minute) {
                    $scope.immediate_charging_schedule_canceled = true;
                    $scope.immediate_charging_schedule_hour = "00";
                    $scope.immediate_charging_schedule_minute = "00";
                }

                safeApply($scope, function (bodyScope) {});
            });

        $scope.operation_mode = 'normal'

        nats.addListener(namespace + '/workerbee_navigation/robot_pose', onRobotPose);
        nats.addListener(namespace + '/lrf/scan', onLrfScan);
        nats.addListener(namespace + '/sero_mobile/battery', onBatteryData);
        nats.addListener(namespace + '/sero_mobile/docking', onDockingData);
        nats.addListener(namespace + '/rgbd/rgb/image_raw/compressed', onRGBDFrontTest)
        nats.addListener(namespace + '/d435i/color/image_raw/compressed', onRGBDRearTest)
        nats.addListener(namespace + '/rtsp02/image_raw/compressed', onThermalTest)

        nats.addListener(namespace + '/lrf/front/scan', onLrfFront)
        nats.addListener(namespace + '/lrf/back/scan', onLrfBack)
        nats.addListener(namespace + '/imu_data_throttle', onIMUData)


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

        // LED_SET_COLOR(LED_DEVICE_BOTTOM, parseInt('000000',16))
        // LED_SET_COLOR(LED_DEVICE_HEAD, parseInt('000000',16))

        $scope.debug = DEBUG
        if (DEBUG) {
            // $scope.remote_type = "master";
            // $scope.view_mode = 'menu'
            // $scope.popup_visible = true

            var ctx = document.getElementById('chart_canvas').getContext('2d');

            var config = {
                type: 'line',
                data: {
                    labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
                    datasets: [{
                        label: 'BATTERY~',
                        backgroundColor: '#000000',
                        borderColor: '#444444',
                        data: [
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            10
                        ],
                        fill: false,
                    }]
                },
                options: {
                    responsive: true,
                    title: {
                        display: true,
                        text: 'Battery Chart'
                    },
                    tooltips: {
                        mode: 'index',
                        intersect: false,
                    },
                    hover: {
                        mode: 'nearest',
                        intersect: true
                    },
                    scales: {
                        xAxes: [{
                            display: true,
                            scaleLabel: {
                                display: true,
                                labelString: 'Month'
                            }
                        }],
                        yAxes: [{
                            display: true,
                            scaleLabel: {
                                display: true,
                                labelString: 'Value'
                            }
                        }]
                    }
                }
            };

            window.myLine = new Chart(ctx, config);

            $scope.showChart = () => {
                console.log('==showchart==')
                $('.chart_ct').show()
            }

            $scope.closeChart = () => {
                console.log('==closechart==')
                $('.chart_ct').hide()
            }

            $scope.queryChartData = (msg) => {
                console.log('==query==', msg)
                switch (msg) {
                    case 'month':
                        break;
                    case 'week':
                        break;
                    case 'day':
                        break;
                }
                window.myLine.update()
            }
        }

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
        }

        setInterval(() => {
            $scope.getClock()
            $scope.remain_charging_time = `서비스 재개 예정시간 ${$scope.diffHours}:${$scope.diffMinutes}:${$scope.diffSeconds}`

            safeApply($scope, function ($scope) {})
        }, 1000);
        
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

    // schedule register data function
    $scope.onClickRegister = function () {
        // $scope.start_time_box

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
        location_list = location_list.filter((x, idx) => idx === location_list.indexOf(x)); // 중복 제거

        // 오름차순 정렬
        location_list = location_list.sort((a, b) => {
            return a - b;
        });

        console.log("location_list = ", location_list)
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

    $scope.onChargingStart = function () {
        let nowTime = new Date();
        let chargingTime = new Date();

        chargingTime.setMinutes(chargingTime.getMinutes() + $scope.charging_time);

        let hour = chargingTime.getHours()
        let min = chargingTime.getMinutes()

        hour = hour.toString().padStart(2, "0")
        min = min.toString().padStart(2, "0")

        // 현재 날짜가 충전 시간 적용한 날짜와 다르다면(익일을 넘어간 거)
        if (nowTime.getDate() !== chargingTime.getDate()) {
            hour = 23
            min = 50
        }

        $scope.immediate_charging_schedule_hour = hour;
        $scope.immediate_charging_schedule_minute = min;
        $scope.immediate_charging_schedule_canceled = false;

        console.log("end hour : ", $scope.immediate_charging_schedule_hour);
        console.log("end_minute : ", $scope.immediate_charging_schedule_minute);

        nats.publish(namespace + '/schedule/write_immediate_charging', {
            end_time: $scope.immediate_charging_schedule_hour + ":" + $scope.immediate_charging_schedule_minute + ":" + "00"
        });

        var msg = {
            "IMMEDIATE_CHARGING_SCHEDULE_HOUR": $scope.immediate_charging_schedule_hour,
            "IMMEDIATE_CHARGING_SCHEDULE_MINUTE": $scope.immediate_charging_schedule_minute,
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

        cancel_all_action()
        callManager('idle')
    }

    $scope.onChargingStop = async function () {
        console.log("onChargingStop")

        $scope.immediate_charging_schedule_hour = "00";
        $scope.immediate_charging_schedule_minute = "00";
        $scope.immediate_charging_schedule_canceled = true;

        $scope.remain_charging_time = `서비스 재개 예정시간 ${"00"}:${"00"}:${"00"}`
        safeApply($scope, function ($scope) {})

        nats.publish(namespace + '/schedule/write_immediate_charging', {
            canceled: true
        });

        var msg = {
            "IMMEDIATE_CHARGING_SCHEDULE_HOUR": $scope.immediate_charging_schedule_hour,
            "IMMEDIATE_CHARGING_SCHEDULE_MINUTE": $scope.immediate_charging_schedule_minute,
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

    $scope.onLEDBottomTest = function () {
        console.log("onLEDBottomTest")
        LED_BLINK(LED_DEVICE_BOTTOM, LED_COLOR_CYAN, 1000, LED_COLOR_WHITE, 1000, LED_REPEAT_NO)
    }

    $scope.onLEDHeadTest = function () {
        console.log("onLEDHeadTest")
        LED_BLINK(LED_DEVICE_HEAD, LED_COLOR_CYAN, 1000, LED_COLOR_WHITE, 1000, LED_REPEAT_NO)

    }

    $scope.onClickNetworkTest = function (mode) {
        $.getJSON('../tools/command/lte_test', function (data) {
            console.log(data)
            if (data.error)
                $scope.lte_available = false
            else
                $scope.lte_available = true
            safeApply($scope, function ($scope) {})
        })
    }

    $scope.onLrfFrontStart = function () {
        lrf_test_front = true
        $scope.lrf_front_msg = null
    }

    $scope.onLrfBackStart = function () {
        lrf_test_back = true
        $scope.lrf_back_msg = null
    }

    $scope.onIMUStart = function () {
        imu_test = true
        $scope.imu_msg = null
    }

    $scope.onRGBDFrontStart = function () {
        rgbd_front_test = true
    }
    $scope.onRGBDRearStart = function () {
        rgbd_rear_test = true
    }
    $scope.onThermalStart = function () {
        thermal_test = true
    }


    $scope.showTouchTest = function () {
        $('#touch_test').show()
    }

    $scope.closeTouchTest = function () {
        $('#touch_test').hide()
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

    $scope.onMicroPhoneRecording = () => {
        if ($scope.rec_state != REC_STATE_RECORDING) {
            $scope.rec_state = REC_STATE_RECORDING
            safeApply($scope, function ($scope) {})
            $.getJSON('../tools/command/rec_mic', function (data) {
                console.log('=============', data)
                $scope.rec_state = REC_STATE_RECORDED

                safeApply($scope, function ($scope) {})
            })
        }
    }

    $scope.onMicroPhonePlay = () => {
        var src = "http://127.0.0.1:8080/media/mic_test.wav";
        var audio = new Audio(src);
        audio.play();
    }

    $scope.mapping_mode = false
    $scope.onStartMapping = async function () {
        console.log("onStartMapping");
        $scope.mapping_mode = true;

        var url = 'http://0.0.0.0:8080/mapbox/backup';
        console.log(url);
        $.ajax({
            url: url,
            type: "POST",
            dataType: "json",
            success: function (data) {
                console.log(data);
            },
            error: function (data) {
                console.error(data);
            }

        });

        nats.publish(namespace + '/robot_display/lock_screen', {
            lock: true
        });
        setTimeout(function () {
            nats.publish(namespace + '/robot_display/lock_screen', {
                lock: false
            });
        }, 10000);
        var node = namespace + '/mapping/start';
        console.log(node);
        var req = new Requester(nats, 'console', node, null, null);
        req.request({}, 120000, true);
        var result = await req.wait_finish(null);
        console.log(result);
    }

    $scope.onStopMapping = async function () {
        console.log("onStopMapping");
        $scope.mapping_mode = false
        nats.publish(namespace + '/robot_display/lock_screen', {
            lock: true
        });
        var filename = new Date().toISOString();
        var node = namespace + '/mapping/save';
        var req = new Requester(nats, 'console', node, null, null);
        req.request({
            file_name: filename
        }, 120000, true);
        var result = await req.wait_finish(null);
        console.log(result);
        var node = namespace + '/mapping/stop';
        var req1 = new Requester(nats, 'console', node, null, null);
        req1.request({}, 120000, true);
        var result = await req1.wait_finish(null);
        console.log(result);
        nats.publish(namespace + '/robot_display/lock_screen', {
            lock: false
        });
        $("#popup_noti_mapping_finish").css('display', 'inherit');
    }

    // <== 맵 업데이트
    function mapUpdate() {
        return new Promise(function (resolve, reject) {
            var url = 'http://0.0.0.0:8080/mapbox/get/dir/map';
            const TIMEOUT_MAPUPDATE = 240000; //240sec
            $.ajax({
                url: url,
                type: "GET",
                dataType: "json",
                success: async function (data) {
                    var node = namespace + '/map_update/update'
                    req = new Requester(nats, NATS_CONFIG.robotName, node, null, null);
                    var filename = data.message + "/map.yaml"
                    console.log(filename);
                    var result = await req.request({
                        filename: filename
                    }, TIMEOUT_MAPUPDATE);
                    console.log(result)
                    nats.publish(namespace + "/robot_display/lock_screen", {
                        lock: false
                    });
                    $("#map_set_popup").css('display', 'none');
                    resolve();
                },
                error: function (data) {
                    console.error("ERROR");
                    nats.publish(namespace + "/robot_display/lock_screen", {
                        lock: false
                    });
                    $("#map_set_popup").css('display', 'none');
                    reject();
                }
            })
        })
    }

    $scope.onMapBoxListRefresh = function () {
        $.getJSON('../mapbox/list', function (data) {
            console.log(data)
            safeApply($scope, function ($scope) {
                console.log('map_box', data);
                $scope.map_box = []
                $scope.map_box.push({
                    name: "~origin",
                    url: null,
                    origin: true,
                    selected: false
                })
                for (var i in data.list) {
                    $scope.map_box.push({
                        name: data.list[i].name,
                        url: data.list[i].url,
                        origin: false,
                        selected: false
                    });
                }
            })
        })
    }

    $scope.onShowPopupMapUpdate = function () {
        console.log("onShowPopupMapUpdate");
        var count = 0;
        for (var i in $scope.map_box) {
            if ($scope.map_box[i].selected) count++;
        }
        if (count > 0) {
            $("#map_set_popup").css('display', 'inherit');
        } else {
            $("#popup_noti_select_map").css('display', 'inherit');
        }
    }

    $scope.onHidePopupMapUpdate = function () {
        console.log("onHidePopupMapUpdate");
        $("#map_set_popup").css('display', 'none');
    }

    $scope.onMapUpdate = async function () {
        console.log("onMapUpdate");
        // if (bodyScope.is_demo_setting)
        // 	bodyScope.set_check.set_map = true
        // $("#map_set_popup").css('display', 'none');
        nats.publish(namespace + "/robot_display/lock_screen", {
            lock: true
        });
        $("#map_set_popup").css('display', 'none');
        var item;
        for (var i in $scope.map_box) {
            if ($scope.map_box[i].selected) item = $scope.map_box[i];
        }

        async function on_success(data) {
            await mapUpdate();
            if (bodyScope.is_demo_setting)
                bodyScope.set_check.set_map = true
            await getScope('RobotInitPos').map_load();
        }

        function on_error(data) {
            console.error("ERROR");
            nats.publish(namespace + "/robot_display/lock_screen", {
                lock: false
            });
            $("#map_set_popup").css('display', 'none');
        }

        if (item.origin) {
            var url = 'http://0.0.0.0:8080/mapbox/recovery';
            console.log(url);
            $.ajax({
                url: url,
                type: "POST",
                dataType: "json",
                success: on_success,
                error: on_error
            });
        } else {
            var url = 'http://0.0.0.0:8080/mapbox/map_copy/' + item.url;
            console.log(url);
            $.ajax({
                url: url,
                type: "POST",
                dataType: "json",
                success: on_success,
                error: on_error
            });
        }
    }

    $scope.onShowPopupMapDelete = function () {
        console.log("onShowPopupMapDelete");
        var count = 0;
        for (var i in $scope.map_box) {
            if ($scope.map_box[i].selected) count++;
        }
        if (count > 0) {
            $("#popup_delete_map").css('display', 'inherit');
        } else {
            $("#popup_noti_select_map").css('display', 'inherit');
        }
    }

    $scope.onHidePopupMapDelete = function () {
        console.log("onHidePopupMapDelete");
        $("#popup_delete_map").css('display', 'none');
    }

    $scope.onMapDelete = async function () {
        console.log("onMapDelete");
        $("#popup_delete_map").css('display', 'none');
        var item;
        for (var i in $scope.map_box) {
            if ($scope.map_box[i].selected) item = $scope.map_box[i];
        }
        var url = 'http://0.0.0.0:8080/mapbox/delete/' + item.url;
        console.log(url);
        $.ajax({
            url: url,
            type: "POST",
            dataType: "json",
            success: async function (data) {
                console.log(data);
            },
            error: function (data) {
                console.error(data);
            }
        });
        $scope.onMapBoxListRefresh();
    }

    $scope.onMapboxSelect = function (index) {
        console.log("onMapboxSelect", index);
        for (var i in $scope.map_box) {
            $scope.map_box[i].selected = false;
        }
        $scope.map_box[index].selected = true;
    }

    $scope.onHidePopupNotiSelectMap = function () {
        $("#popup_noti_select_map").css('display', 'none');
    }

    $scope.onHidePopupNotiMappingFinish = function () {
        console.log("onHidePopupNotiMappingFinish");
        $("#popup_noti_mapping_finish").css('display', 'none');
    }

    $scope.onRecoveryOldMap = function () {
        console.log("onRecoveryOldMap");
        nats.publish(namespace + "/robot_display/lock_screen", {
            lock: true
        });
        $("#popup_noti_mapping_finish").css('display', 'none');
        var url = 'http://0.0.0.0:8080/mapbox/recovery';
        console.log(url);
        $.ajax({
            url: url,
            type: "POST",
            dataType: "json",
            success: async function (data) {
                console.log(data);
                await mapUpdate();
                nats.publish(namespace + "/robot_display/lock_screen", {
                    lock: false
                });
            },
            error: function (data) {
                console.error(data);
            }

        });
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

    // $('#runtime_slider').rangeslider({
    //     polyfill: false,
    //     rangeClass: 'rangeslider',
    //     fillClass: 'rangeslider__fill',
    //     handleClass: 'rangeslider__handle2',

    //     onSlide: function (position, value) {
    //         safeApply($scope, function ($scope) {
    //             $scope.service_runtime = value;
    //         })
    //     },
    //     onSlideEnd: function (position, value) {}
    // });


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