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
        triggerResize();
    }
    function exitFullscreen() {
        $(element).find(".js-scorm-block").removeClass("full-screen-scorm");
        fullscreenOnNextEvent = true;
        triggerResize();
    }
    function triggerResize() {
        // This is required to trigger the actual content resize in some packages
        window.dispatchEvent(new Event('resize'));
    }

    // Student reports
    function initReports() {
        $(element).find("button.view-reports").on("click", function() {
            viewReports();
        });
        $(element).find("button.reload-report").on("click", function() {
            reloadReport();
        });
        // https://api.jqueryui.com/autocomplete/
        // note that we don't use $(...).autocomplete({}). That's because the lms has an obsolete
        // autocomplete jquery plugin which overrides the jquery.ui.autocomplete widget.
        // So we need to specify the widget namespace when we call "autocomplete"
        $.ui.autocomplete(
            {
                source: searchStudents,
                select: viewReport,
            }, $(element).find(".scorm-reports input.search-students")
        );
    }
    function searchStudents(request, response) {
        $.ajax({
            url: runtime.handlerUrl(element, 'scorm_search_students'),
            data: {
                'id': request.term
            },
        }).success(function(data) {
            response(data);
        }).fail(function() {
            response([])
        });
    }
    function viewReports() {
        // Display reports on button click
        $(element).find(".reports-togglable").toggleClass("reports-togglable-off");
    }
    var studentId = null;
    function viewReport(event, ui) {
        studentId = ui.item.data.student_id;
        getReport(studentId);
    }
    function reloadReport() {
        getReport(studentId)
    }
    function getReport(studentId) {
        var reportElement = $(element).find(".scorm-reports .report");
        reportElement.html("loading...");
        var getReportUrl = runtime.handlerUrl(element, 'scorm_get_student_state');
        $.ajax({
            url: getReportUrl,
            data: {
                'id': studentId
            },
        }).success(function(data) {
            reportElement.html(renderjson.set_show_to_level(1)(data));
        }).fail(function() {
            reportElement.html("no data found");
        }).complete(function() {
            $(element).find(".reload-report").removeClass("reports-togglable-off");
        });
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
    var setValuesUrl = runtime.handlerUrl(element, 'scorm_set_values');
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
            processSetValueQueueItems();
        }
    }
    function processSetValueQueueItems() {
        if (setValueEvents.length === 0) {
            // Exit if there is no event left in the queue
            processingSetValueEventsQueue = false;
            return;
        }
        processingSetValueEventsQueue = true;
        var data = [];
        while (setValueEvents.length > 0) {
            params = setValueEvents.shift();
            cmi_element = params[0];
            value = params[1];
            if (!cmi_element in uncachedValues) {
                // Update the local scorm data copy to fetch results faster with get_value
                settings.scorm_data[cmi_element] = value;
            }
            data.push({
                'name': cmi_element,
                'value': value
            })
        }
        $.ajax({
            type: "POST",
            url: setValuesUrl,
            data: JSON.stringify(data),
            success: function(results) {
                for (var i = 0; i < results.length; i += 1) {
                    var result = results[i];
                    if (typeof result.grade != "undefined") {
                        // Properly display at most two decimals
                        console.log(result.grade, Math.round(result.grade*100) / 100)
                        $(element).find(".grade").html(Math.round(result.grade*100) / 100);
                    }
                    $(element).find(".completion_status").html(result.completion_status);
                }
            },
            complete: function() {
                // Recursive call to itself
                processSetValueQueueItems();
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
        initReports();
    });
}
