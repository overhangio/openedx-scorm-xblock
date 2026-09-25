"""
Tracking events emitted by the SCORM XBlock.

SCORM packages are black boxes: the only thing the platform sees of a learner
session is the stream of SCORM API calls made by the package. This module turns
that stream into regular Open edX tracking events.

Events are emitted with ``runtime.publish``, just like any other XBlock event,
so they end up in the tracking log with the usual course/user context. Nothing
else is required from operators. Platforms that ship their events to an LRS can
additionally install the optional xAPI transformers shipped in
``openedxscorm.processors.xapi``; see the README.

Every event can be disabled individually through the XBlock settings::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "TRACKING_EVENTS_ENABLED": True,
        "TRACKING_EVENTS": {
            "interacted": True,
        },
    }
"""

import logging
from fnmatch import fnmatchcase

logger = logging.getLogger(__name__)

# All events share this prefix, which makes them easy to allow/deny as a group.
EVENT_PREFIX = "openedx.xblock.scorm"

INITIALIZED = "initialized"
INTERACTED = "interacted"
SCORED = "scored"
COMPLETED = "completed"
PASSED = "passed"
FAILED = "failed"
TERMINATED = "terminated"

#: Events that describe the state of the attempt: when a SCORM package writes
#: several elements in a single batch (``cmi.score.raw`` and ``cmi.score.scaled``,
#: typically) we only keep the last value of each of these, to avoid emitting
#: several events that describe the very same state.
STATE_EVENTS = (SCORED, COMPLETED, PASSED, FAILED)

#: Default value of the ``TRACKING_EVENTS`` setting. ``interacted`` is opt-in:
#: it is the only event of the set that is both high-volume and that carries
#: learner answers, so operators enable it deliberately.
DEFAULT_TRACKING_EVENTS = {
    INITIALIZED: True,
    INTERACTED: False,
    SCORED: True,
    COMPLETED: True,
    PASSED: True,
    FAILED: True,
    TERMINATED: True,
}

#: SCORM data model elements that are considered learner interactions. These are
#: fnmatch patterns, matched against the name of the element written by the
#: package. Defaults are the elements that a package updates when the learner
#: moves to another slide/page or answers a question. Operators who want a finer
#: (or coarser) grained stream can override the ``TRACKING_INTERACTION_ELEMENTS``
#: setting, e.g. with ``["cmi.interactions.*"]`` or ``["cmi.*"]``.
DEFAULT_INTERACTION_ELEMENTS = [
    "cmi.core.lesson_location",
    "cmi.location",
    "cmi.interactions.*.student_response",
    "cmi.interactions.*.learner_response",
]

#: Interaction values are learner data of arbitrary length (``cmi.suspend_data``
#: may be several kilobytes long) so they are truncated before being tracked.
MAX_TRACKED_VALUE_LENGTH = 255


def event_name(short_name):
    """
    Return the full tracking event name of a short event name.
    """
    return "{}.{}".format(EVENT_PREFIX, short_name)


def tracked_event_names():
    """
    Return the name of every tracking event that this XBlock may emit.

    This module has no dependency other than the standard library, so operators
    may call this from their Django settings to declare the SCORM events to
    event-routing-backends. See the "Learner activity tracking" section of the
    README.
    """
    return [event_name(short_name) for short_name in DEFAULT_TRACKING_EVENTS]


class ScormTrackingMixin:
    """
    Emit tracking events for the SCORM API calls made by a package.

    This mixin is meant to be used by :class:`openedxscorm.scormxblock.ScormXBlock`;
    it expects the ``xblock_settings`` property and the SCORM fields to be defined
    by the host class.
    """

    # Events collected while a batch of SCORM elements is being processed. `None`
    # means that no batch is open and that events are emitted right away.
    _pending_events = None

    @property
    def tracking_settings(self):
        """
        Return the tracking-related XBlock settings, with defaults applied.
        """
        settings = self.xblock_settings
        if not isinstance(settings, dict):
            # No settings service (XBlock workbench, unit tests...).
            settings = {}
        events = dict(DEFAULT_TRACKING_EVENTS)
        configured_events = settings.get("TRACKING_EVENTS")
        if isinstance(configured_events, dict):
            events.update(configured_events)
        interaction_elements = settings.get(
            "TRACKING_INTERACTION_ELEMENTS", DEFAULT_INTERACTION_ELEMENTS
        )
        return {
            "enabled": settings.get("TRACKING_EVENTS_ENABLED", True),
            "events": events,
            "interaction_elements": list(interaction_elements),
        }

    @property
    def is_tracking_enabled(self):
        """
        Return True if this block emits tracking events at all.
        """
        return bool(self.tracking_settings["enabled"])

    def is_tracking_event_enabled(self, short_name):
        """
        Return True if the event with this short name should be emitted.
        """
        settings = self.tracking_settings
        return bool(settings["enabled"]) and bool(settings["events"].get(short_name))

    def is_tracked_interaction(self, element_name):
        """
        Return True if writing this SCORM element counts as a learner interaction.
        """
        return any(
            fnmatchcase(element_name, pattern)
            for pattern in self.tracking_settings["interaction_elements"]
        )

    def publish_scorm_event(self, short_name, data=None):
        """
        Emit a single SCORM tracking event, unless it was disabled by the operator.
        """
        if not self.is_tracking_event_enabled(short_name):
            return
        event_data = {
            "block_id": str(self.scope_ids.usage_id),
            "scorm_version": self.scorm_version,
        }
        event_data.update(data or {})
        if self._pending_events is None:
            self._emit_scorm_event(short_name, event_data)
        else:
            self._pending_events.append((short_name, event_data))

    def _emit_scorm_event(self, short_name, event_data):
        """
        Publish the event through the runtime.

        Tracking must never get in the way of the learner: a runtime that does
        not support event publishing, or a failure to publish, is logged and
        ignored.
        """
        try:
            self.runtime.publish(self, event_name(short_name), event_data)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Failed to publish the '%s' tracking event of the SCORM block %s",
                short_name,
                event_data.get("block_id"),
            )

    def open_tracking_batch(self):
        """
        Start collecting events instead of emitting them right away.

        SCORM packages write several elements per API round-trip; collecting the
        resulting events makes it possible to emit a single event per state
        change. Callers are responsible for calling `close_tracking_batch`.
        """
        self._pending_events = []

    def close_tracking_batch(self):
        """
        Emit the events collected since `open_tracking_batch` was called.
        """
        pending, self._pending_events = self._pending_events or [], None
        last_state_event = {
            short_name: index
            for index, (short_name, _data) in enumerate(pending)
            if short_name in STATE_EVENTS
        }
        for index, (short_name, event_data) in enumerate(pending):
            if short_name in STATE_EVENTS and last_state_event[short_name] != index:
                continue
            self._emit_scorm_event(short_name, event_data)

    def scorm_score_data(self):
        """
        Return the score of the attempt, for blocks that are graded.

        Ungraded blocks have no score to report: this XBlock only keeps track of
        the score of a package when the block itself is graded.
        """
        if not self.has_score:
            return {}
        return {
            "scaled_score": self.lesson_score,
            "weighted_score": self.get_grade(),
            "max_score": self.weight,
        }

    def track_scorm_session_start(self):
        """
        Emit the event associated to a ``LMSInitialize``/``Initialize`` API call.
        """
        self.publish_scorm_event(
            INITIALIZED,
            {
                "completion_status": self.lesson_status,
                "success_status": self.success_status,
            },
        )

    def track_scorm_session_end(self, duration=None):
        """
        Emit the event associated to a ``LMSFinish``/``Terminate`` API call.

        Arguments:
            duration (float): time on task, in seconds, or None if unknown.
        """
        data = {
            "completion_status": self.lesson_status,
            "success_status": self.success_status,
        }
        if duration is not None:
            data["duration"] = duration
        data.update(self.scorm_score_data())
        self.publish_scorm_event(TERMINATED, data)

    def track_set_value(
        self,
        name,
        value,
        completion_status=None,
        success_status=None,
        lesson_score=None,
    ):
        """
        Emit the events associated to a single ``SetValue`` API call.

        Arguments mirror the values computed by
        :meth:`openedxscorm.scormxblock.ScormXBlock.set_value`: only the values
        that the package actually changed are passed.
        """
        if self.is_tracked_interaction(name):
            self.publish_scorm_event(
                INTERACTED,
                {
                    "cmi_element": name,
                    "value": str(value)[:MAX_TRACKED_VALUE_LENGTH],
                },
            )
        if lesson_score is not None:
            self.publish_scorm_event(SCORED, self.scorm_score_data())
        if completion_status == "completed":
            data = {"completion_status": completion_status}
            data.update(self.scorm_score_data())
            self.publish_scorm_event(COMPLETED, data)
        if success_status in (PASSED, FAILED):
            data = {"success_status": success_status}
            data.update(self.scorm_score_data())
            self.publish_scorm_event(success_status, data)
