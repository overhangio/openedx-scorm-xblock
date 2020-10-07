function ScormXBlock(runtime, element, settings) {

    function SCORM_12_API() {

        this.LMSInitialize = function() {
            return "true";
        };

        this.LMSFinish = function() {
            return "true";
        };

        this.LMSGetValue = GetValue;
        this.LMSSetValue = SetValue;

        this.LMSCommit = function() {
            return "true";
        };

        this.LMSGetLastError = function() {
            return "0";
        };

        this.LMSGetErrorString = function(errorCode) {
            return "Some Error";
        };

        this.LMSGetDiagnostic = function(errorCode) {
            return "Some Diagnostic";
        };
    }

    function SCORM_2004_API() {
        this.Initialize = function() {
            return "true";
        };

        this.Terminate = function() {
            return "true";
        };

        this.GetValue = GetValue;
        this.SetValue = SetValue;

        this.Commit = function() {
            return "true";
        };

        this.GetLastError = function() {
            return "0";
        };

        this.GetErrorString = function(errorCode) {
            return "Some Error";
        };

        this.GetDiagnostic = function(errorCode) {
            return "Some Diagnostic";
        };
    }

    var GetValue = function(cmi_element) {
        var handlerUrl = runtime.handlerUrl(element, 'scorm_get_value');

        var response = $.ajax({
            type: "POST",
            url: handlerUrl,
            data: JSON.stringify({
                'name': cmi_element
            }),
            async: false
        });
        response = JSON.parse(response.responseText);
        return response.value
    };

    var SetValue = function(cmi_element, value) {
        if (cmi_element === 'cmi.core.exit' || cmi_element === 'cmi.exit') {
            $(".js-scorm-block", element).removeClass('full-screen-scorm');
        }

        var handlerUrl = runtime.handlerUrl(element, 'scorm_set_value');

        $.ajax({
            type: "POST",
            url: handlerUrl,
            data: JSON.stringify({
                'name': cmi_element,
                'value': value
            }),
            async: false,
            success: function(response) {
                if (typeof response.lesson_score != "undefined") {
                    $(".lesson_score", element).html(response.lesson_score);
                }
                $(".completion_status", element).html(response.completion_status);
            }
        });

        return "true";
    };

    $(function($) {
        if (settings.scorm_version == 'SCORM_12') {
            API = new SCORM_12_API();
        } else {
            API_1484_11 = new SCORM_2004_API();
        }

        var $scormBlock = $(".js-scorm-block", element);
        $('.js-button-full-screen', element).on("click", function() {
            $scormBlock.toggleClass("full-screen-scorm");
        });
    });
}