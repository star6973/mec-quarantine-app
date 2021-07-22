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
        if (msg == 'params')
            $scope.params_complete = true
        else if (msg == 'nats')
            $scope.nats_complete = true

        if ($scope.params_complete && $scope.nats_complete) {
            $scope.Initializing()
        }
    }

    $scope.Initializing = () => {}; 
});