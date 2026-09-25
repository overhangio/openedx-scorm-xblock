"""
Tests of the xAPI transformers of the SCORM events.

These tests are skipped when event-routing-backends is not installed, since it
is an optional dependency of this package: install it with
`pip install -e ".[xapi]"`. Django settings are configured by the conftest.py
at the root of the repository.
"""

import unittest

from django.conf import settings

try:
    from event_routing_backends.processors.xapi.registry import XApiTransformersRegistry

    from openedxscorm.processors.xapi import event_transformers  # pylint: disable=unused-import

    EVENT_ROUTING_BACKENDS_INSTALLED = True
except ImportError:
    EVENT_ROUTING_BACKENDS_INSTALLED = False

from openedxscorm.tracking import DEFAULT_TRACKING_EVENTS, event_name

BLOCK_ID = "block-v1:org+course+run+type@scorm+block@1234"


def make_event(short_name, data=None):
    """
    Return an event as it is emitted by the XBlock, ready to be transformed.
    """
    return {
        "name": event_name(short_name),
        "timestamp": "2026-01-01T00:00:00.000000+00:00",
        "context": {"course_id": "course-v1:org+course+run", "user_id": 1},
        "data": dict(
            {"block_id": BLOCK_ID, "scorm_version": "SCORM_2004"}, **(data or {})
        ),
    }


@unittest.skipUnless(
    EVENT_ROUTING_BACKENDS_INSTALLED, "event-routing-backends is not installed"
)
class ScormXApiTransformersTests(unittest.TestCase):
    """
    Tests of the transformation of SCORM events to xAPI statements.
    """

    @staticmethod
    def transformer(short_name, data=None):
        """
        Return the transformer registered for a SCORM event.
        """
        return XApiTransformersRegistry.get_transformer(make_event(short_name, data))

    def test_all_events_have_a_transformer(self):
        for short_name in DEFAULT_TRACKING_EVENTS:
            self.assertIn(event_name(short_name), XApiTransformersRegistry.mapping)

    def test_object_is_the_scorm_block(self):
        transformer = self.transformer("initialized")

        activity = transformer.get_object()

        self.assertEqual(
            activity.id,
            "{}/xblock/{}".format(settings.LMS_ROOT_URL.rstrip("/"), BLOCK_ID),
        )
        self.assertEqual(
            activity.definition.type, "http://adlnet.gov/expapi/activities/lesson"
        )

    def test_verbs(self):
        expected_verbs = {
            "initialized": "http://adlnet.gov/expapi/verbs/initialized",
            "interacted": "http://adlnet.gov/expapi/verbs/interacted",
            "scored": "http://adlnet.gov/expapi/verbs/scored",
            "completed": "http://adlnet.gov/expapi/verbs/completed",
            "passed": "http://adlnet.gov/expapi/verbs/passed",
            "failed": "http://adlnet.gov/expapi/verbs/failed",
            "terminated": "http://adlnet.gov/expapi/verbs/terminated",
        }
        for short_name, verb_id in expected_verbs.items():
            self.assertEqual(self.transformer(short_name).get_verb().id, verb_id)

    def test_interacted_result(self):
        transformer = self.transformer(
            "interacted", {"cmi_element": "cmi.location", "value": "slide_3"}
        )

        self.assertEqual(transformer.get_result().response, "slide_3")
        self.assertEqual(
            transformer.get_context_extensions()[
                "https://github.com/overhangio/openedx-scorm-xblock/xapi/extension/cmi-element"
            ],
            "cmi.location",
        )

    def test_score_is_reported_in_the_result(self):
        transformer = self.transformer(
            "scored", {"scaled_score": 0.5, "weighted_score": 5.0, "max_score": 10.0}
        )

        score = transformer.get_result().score

        self.assertEqual(score.scaled, 0.5)
        self.assertEqual(score.raw, 5.0)
        self.assertEqual(score.max, 10.0)

    def test_out_of_range_scores_are_clamped(self):
        # A package that reports "cmi.core.score.raw" above 100 yields a scaled
        # score above 1, which an LRS rejects.
        transformer = self.transformer(
            "scored", {"scaled_score": 1.5, "weighted_score": 15.0, "max_score": 10.0}
        )

        score = transformer.get_result().score

        self.assertEqual(score.scaled, 1)
        self.assertEqual(score.raw, 10.0)

    def test_ungraded_blocks_have_no_score(self):
        self.assertIsNone(self.transformer("completed").get_result().score)

    def test_success_status_is_reported_in_the_result(self):
        self.assertTrue(self.transformer("passed").get_result().success)
        self.assertFalse(self.transformer("failed").get_result().success)

    def test_session_duration_is_reported_in_the_result(self):
        transformer = self.transformer(
            "terminated", {"duration": 90, "completion_status": "completed"}
        )

        result = transformer.get_result()

        self.assertEqual(result.duration.total_seconds(), 90)
        self.assertTrue(result.completion)

    def test_scorm_version_is_reported_in_the_context(self):
        transformer = self.transformer("initialized")

        self.assertEqual(
            transformer.get_context_extensions()[
                "https://github.com/overhangio/openedx-scorm-xblock/xapi/extension/scorm-version"
            ],
            "SCORM_2004",
        )
