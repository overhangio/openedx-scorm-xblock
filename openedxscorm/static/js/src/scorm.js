function SCORM_12_API(GetValue, SetValue) {
  this.LMSInitialize = function () {
    return "true";
  };
  this.LMSFinish = function () {
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

function SCORM_2004_API(GetValue, SetValue) {
  this.Initialize = function () {
    return "true";
  };
  this.Terminate = function () {
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

function initScorm(scormVersion, getValueFunc, setValueFunc) {
  if (scormVersion == 'SCORM_12') {
    API = new SCORM_12_API(getValueFunc, setValueFunc);
  } else {
    API_1484_11 = new SCORM_2004_API(getValueFunc, setValueFunc);
  }
}
