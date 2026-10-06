function SCORM_12_API(GetValue, SetValue, Initialize, Terminate) {
  this.LMSInitialize = function () {
    Initialize();
    return "true";
  };
  this.LMSFinish = function () {
    Terminate();
    return "true";
  };
  this.LMSCommit = function () {
    return "true";
  };
  this.LMSGetLastError = function () {
    return "0";
  };
  this.LMSGetErrorString = function (errorCode) {
    return "Some Error";
  };
  this.LMSGetDiagnostic = function (errorCode) {
    return "Some Diagnostic";
  };
  this.LMSGetValue = GetValue;
  this.LMSSetValue = SetValue;
}

function SCORM_2004_API(GetValue, SetValue, Initialize, Terminate) {
  this.Initialize = function () {
    Initialize();
    return "true";
  };
  this.Terminate = function () {
    Terminate();
    return "true";
  };
  this.Commit = function () {
    return "true";
  };
  this.GetLastError = function () {
    return "0";
  };
  this.GetErrorString = function (errorCode) {
    return "Some Error";
  };
  this.GetDiagnostic = function (errorCode) {
    return "Some Diagnostic";
  };
  this.GetValue = GetValue;
  this.SetValue = SetValue;
}

function initScorm(scormVersion, getValueFunc, setValueFunc, initializeFunc, terminateFunc) {
  // The initialize and terminate callbacks are optional: they are only used to
  // track the beginning and the end of the learner session.
  var noop = function () {};
  initializeFunc = initializeFunc || noop;
  terminateFunc = terminateFunc || noop;
  if (scormVersion == 'SCORM_12') {
    API = new SCORM_12_API(getValueFunc, setValueFunc, initializeFunc, terminateFunc);
  } else {
    API_1484_11 = new SCORM_2004_API(getValueFunc, setValueFunc, initializeFunc, terminateFunc);
  }
}
