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

    // We only make calls to the get_value handler when absolutely required.
    // These calls are synchronous and they can easily clog the scorm display.
    var uncachedValues = [
        "cmi.core.lesson_status",
        "cmi.completion_status",
        "cmi.success_status",
        "cmi.core.score.raw",
        "cmi.score.raw"
    ];
    var getValueUrl = runtime.handlerUrl(element, 'scorm_get_value');
    var GetValue = function(cmi_element) {
        if (cmi_element in uncachedValues) {
            var response = $.ajax({
                type: "POST",
                url: getValueUrl,
                data: JSON.stringify({
                    'name': cmi_element
                }),
                async: false
            });
            response = JSON.parse(response.responseText);
            return response.value;
        } else if (cmi_element in settings.scorm_data) {
            return settings.scorm_data[cmi_element];
        }
        return "";
    };

    var setValueEvents = [];
    var processingSetValueEventsQueue = false;
    var setValueUrl = runtime.handlerUrl(element, 'scorm_set_value');
    var SetValue = function(cmi_element, value) {
        // The first event causes the module to go fullscreen
        // when the setting is enabled
        if (fullscreenOnNextEvent) {
            fullscreenOnNextEvent = false;
            if (settings.fullscreen_on_launch) {
                enterFullscreen();
            }
        }
        SetValueAsync(cmi_element, value);
        return "true";
    }
    function SetValueAsync(cmi_element, value) {
        setValueEvents.push([cmi_element, value]);
        if (!processingSetValueEventsQueue) {
            // There is no running queue processor so we start one
            processSetValueQueueItem();
        }
    }
    function processSetValueQueueItem() {
        if (setValueEvents.length === 0) {
            // Exit if there is no event left in the queue
            processingSetValueEventsQueue = false;
            return;
        }
        processingSetValueEventsQueue = true;
        params = setValueEvents.shift();
        cmi_element = params[0];
        value = params[1];
        if (!cmi_element in uncachedValues) {
            // Update the local scorm data copy to fetch results faster with get_value
            settings.scorm_data[cmi_element] = value;
        }
        $.ajax({
            type: "POST",
            url: setValueUrl,
            data: JSON.stringify({
                'name': cmi_element,
                'value': value
            }),
            success: function(response) {
                if (typeof response.lesson_score != "undefined") {
                    $(element).find(".lesson_score").html(response.lesson_score);
                }
                $(element).find(".completion_status").html(response.completion_status);
            },
            complete: function() {
                // Recursive call to itself
                processSetValueQueueItem();
            }
        });
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