"""
Constants used to build the xAPI statements of the SCORM XBlock events.

Verbs and activity types come from the ADL vocabulary, which is also what the
cmi5 profile uses: cmi5 is the closest thing to a standard mapping of the SCORM
run-time data model to xAPI.

The two SCORM-specific extensions are namespaced under this repository rather
than under the Open edX xAPI profile (``https://w3id.org/xapi/openedx/``), which
is governed by event-routing-backends. Moving them there is the right long-term
home; it requires agreeing on the terms upstream first.
"""

# xAPI verbs
XAPI_VERB_INITIALIZED = "http://adlnet.gov/expapi/verbs/initialized"
XAPI_VERB_INTERACTED = "http://adlnet.gov/expapi/verbs/interacted"
XAPI_VERB_SCORED = "http://adlnet.gov/expapi/verbs/scored"
XAPI_VERB_COMPLETED = "http://adlnet.gov/expapi/verbs/completed"
XAPI_VERB_PASSED = "http://adlnet.gov/expapi/verbs/passed"
XAPI_VERB_FAILED = "http://adlnet.gov/expapi/verbs/failed"
XAPI_VERB_TERMINATED = "http://adlnet.gov/expapi/verbs/terminated"

# xAPI activity types
XAPI_ACTIVITY_LESSON = "http://adlnet.gov/expapi/activities/lesson"

# xAPI extensions
SCORM_EXTENSION_PREFIX = "https://github.com/overhangio/openedx-scorm-xblock/xapi/extension"
XAPI_CONTEXT_SCORM_VERSION = "{}/scorm-version".format(SCORM_EXTENSION_PREFIX)
XAPI_CONTEXT_CMI_ELEMENT = "{}/cmi-element".format(SCORM_EXTENSION_PREFIX)

# Languages
EN = "en"
