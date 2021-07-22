const SECURE_MODE = "secure"
const INSPECTION_MODE = "inspection"
const QUARANTINE_MODE = "quarantine"

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
        $scope.view_mode = SECURE_MODE
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

    $scope.Initializing(() => {
        $.getJSON("../document/preferences")
            .then((doc) => {
                if (doc["MODE"] == INSPECTION_MODE) {
                    $scope.service_mode = INSPECTION_MODE
                } else {
                    $scope.service_mode = QUARANTINE_MODE
                }
            })
    })

    /*
        handle for immediate schedule
    */
    $scope.imm_sch_cancel = true
    $scope.imm_sch_hour = "00"
    $scope.imm_sch_min = "00"

    $.getJSON("../document/immediate_schedule")
        .them((doc) => {
            let hour = "" + new Date().getHours();
            let minute = "" + new Date().getMinutes();
            
            let imm_time = $scope.imm_sch_hour + $scope.imm_sch_min
            let cur_time = hour + minute

            if (cur_time > imm_time) {
                $scope.imm_sch_cancel = true
                $scope.imm_sch_hour = "00"
                $scope.imm_sch_min = "00"
            } else {
                $scope.imm_sch_cancel = msg.IMMEDIATE_SCHEDULE_CANCELED
                $scope.imm_sch_hour = msg.IMMEDIATE_SCHEDULE_HOUR
                $scope.imm_sch_min = msg.IMMEDIATE_SCHEDULE_MINUTE
            }

            safeApply($scope, function (bodyScope) {})
});