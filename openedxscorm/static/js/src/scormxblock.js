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

    var fullscreenOnNextEvent = true;
    function enterFullscreen() {
        $(element).find(".js-scorm-block").addClass("full-screen-scorm");
    }
    function exitFullscreen() {
        $(element).find(".js-scorm-block").removeClass("full-screen-scorm");
        fullscreenOnNextEvent = true;
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
        return response.value;
    };

    var SetValue = function(cmi_element, value) {
        // The first event causes the module to go fullscreen
        // when the setting is enabled
        if (fullscreenOnNextEvent) {
            fullscreenOnNextEvent = false;
            if (settings.fullscreen_on_launch) {
                enterFullscreen();
            }
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
                    $(element).find(".lesson_score").html(response.lesson_score);
                }
                $(element).find(".completion_status").html(response.completion_status);
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
        $(element).find("button.full-screen-on").on("click", function() {
            enterFullscreen();
        });
        $(element).find("button.full-screen-off").on("click", function() {
            exitFullscreen();
        });
    });
}