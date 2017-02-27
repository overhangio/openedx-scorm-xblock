function ScormXBlock(runtime, element, settings) {

  function SCORM_12_API(){

    this.LMSInitialize = function(){
      console.log('LMSInitialize');
      return "true";
    };

    this.LMSFinish = function() {
      console.log("LMSFinish");
      return "true";
    };

    this.LMSGetValue = GetValue;
    this.LMSSetValue = SetValue;

    this.LMSCommit = function() {
        console.log("LMSCommit");
        return "true";
    };

    this.LMSGetLastError = function() {
      console.log("GetLastError");
      return "0";
    };

    this.LMSGetErrorString = function(errorCode) {
      console.log("LMSGetErrorString");
      return "Some Error";
    };

    this.LMSGetDiagnostic = function(errorCode) {
      console.log("LMSGetDiagnostic");
      return "Some Diagnostice";
    }
  }

  function SCORM_2004_API(){
    this.Initialize = function(){
      console.log('LMSInitialize');
      return "true";
    };

    this.Terminate = function() {
      console.log("LMSFinish");
      return "true";
    };

    this.GetValue = GetValue;
    this.SetValue = SetValue;

    this.Commit = function() {
        console.log("LMSCommit");
        return "true";
    };

    this.GetLastError = function() {
      console.log("GetLastError");
      return "0";
    };

    this.GetErrorString = function(errorCode) {
      console.log("LMSGetErrorString");
      return "Some Error";
    };

    this.GetDiagnostic = function(errorCode) {
      console.log("LMSGetDiagnostic");
      return "Some Diagnostice";
    }
  }

  var GetValue = function (cmi_element) {
    var handlerUrl = runtime.handlerUrl(element, 'scorm_get_value');

    var response = $.ajax({
      type: "POST",
      url: handlerUrl,
      data: JSON.stringify({'name': cmi_element}),
      async: false
    });
    response = JSON.parse(response.responseText);
    console.log("Getvalue for " + cmi_element + " = " + response.value);
    return response.value
  };

  var SetValue = function (cmi_element, value) {
    console.log("LMSSetValue " + cmi_element + " = " + value);
    var handlerUrl = runtime.handlerUrl( element, 'scorm_set_value');

    $.ajax({
      type: "POST",
      url: handlerUrl,
      data: JSON.stringify({'name': cmi_element, 'value': value}),
      async: false,
      success: function(response){
        if (typeof response.lesson_score != "undefined"){
          $(".lesson_score", element).html(response.lesson_score);
        }
        $(".completion_status", element).html(response.completion_status);
      }
    });

    return "true";
  };

  $(function ($) {
    if (settings.version_scorm == 'SCORM_12') {
      API = new SCORM_12_API();
    } else {
      API_1484_11 = new SCORM_2004_API();
    }
    console.log("Initial SCORM data...");
  });
}
