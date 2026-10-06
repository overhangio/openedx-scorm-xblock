"""
Transformers for the tracking events emitted by the SCORM XBlock.

These transformers are only used when
`event-routing-backends <https://github.com/openedx/event-routing-backends>`__
is installed and the optional application of this package was added to
``INSTALLED_APPS``; see the README.

The SCORM run-time data model is mapped to xAPI following the cmi5 profile:
the SCORM block is a "lesson" activity, and the events of a learner session are
mapped to the initialized/interacted/scored/completed/passed/failed/terminated
verbs.
"""

from event_routing_backends.processors.xapi.registry import XApiTransformersRegistry
from event_routing_backends.processors.xapi.transformer import XApiTransformer
from tincan import Activity, ActivityDefinition, LanguageMap, Result, Score, Verb

from openedxscorm.processors.xapi import constants
from openedxscorm.tracking import (
    COMPLETED,
    FAILED,
    INITIALIZED,
    INTERACTED,
    PASSED,
    SCORED,
    TERMINATED,
    event_name,
)


class BaseScormTransformer(XApiTransformer):
    """
    Base transformer for all SCORM XBlock events.
    """

    def get_object(self):
        """
        Return the SCORM block as a cmi5 "lesson" activity.

        Returns:
            `Activity`
        """
        return Activity(
            id=self.get_object_iri("xblock", self.get_data("data.block_id", True)),
            definition=ActivityDefinition(
                type=constants.XAPI_ACTIVITY_LESSON,
            ),
        )

    def get_context_extensions(self):
        """
        Add the SCORM version of the package to the context extensions.

        Returns:
            `Extensions`
        """
        extensions = super().get_context_extensions()
        scorm_version = self.get_data("data.scorm_version")
        if scorm_version:
            extensions[constants.XAPI_CONTEXT_SCORM_VERSION] = scorm_version
        return extensions

    def get_score(self):
        """
        Return the score of the attempt, or None if the block is not graded.

        This XBlock reads `cmi.core.score.raw` as a percentage, so a package
        that reports a raw score above its own maximum yields a scaled score
        above 1. xAPI requires `scaled` to be within [-1, 1] and `raw` to be
        within [min, max], and an LRS rejects the whole statement otherwise, so
        both are clamped rather than reported verbatim.

        Returns:
            `Score` or None
        """
        scaled = self.get_data("data.scaled_score")
        if scaled is None:
            return None
        scaled = min(max(float(scaled), -1.0), 1.0)
        raw = self.get_data("data.weighted_score")
        maximum = self.get_data("data.max_score")
        if raw is not None and maximum is not None:
            raw = min(max(float(raw), 0.0), float(maximum))
        return Score(scaled=scaled, raw=raw, max=maximum, min=0)


@XApiTransformersRegistry.register(event_name(INITIALIZED))
class ScormInitializedTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a package starts a SCORM session.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_INITIALIZED,
        display=LanguageMap({constants.EN: INITIALIZED}),
    )


@XApiTransformersRegistry.register(event_name(INTERACTED))
class ScormInteractedTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a learner interacts with a package.

    The SCORM element written by the package (the current location, or the
    response to one of its interactions) is stored in the context extensions,
    and its value is stored as the result response.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_INTERACTED,
        display=LanguageMap({constants.EN: INTERACTED}),
    )
    additional_fields = ("result",)

    def get_context_extensions(self):
        extensions = super().get_context_extensions()
        extensions[constants.XAPI_CONTEXT_CMI_ELEMENT] = self.get_data(
            "data.cmi_element", True
        )
        return extensions

    def get_result(self):
        """
        Returns:
            `Result`
        """
        return Result(response=self.get_data("data.value"))


@XApiTransformersRegistry.register(event_name(SCORED))
class ScormScoredTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a package reports a score.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_SCORED,
        display=LanguageMap({constants.EN: SCORED}),
    )
    additional_fields = ("result",)

    def get_result(self):
        """
        Returns:
            `Result`
        """
        return Result(score=self.get_score())


@XApiTransformersRegistry.register(event_name(COMPLETED))
class ScormCompletedTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a package reports completion.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_COMPLETED,
        display=LanguageMap({constants.EN: COMPLETED}),
    )
    additional_fields = ("result",)

    def get_result(self):
        """
        Returns:
            `Result`
        """
        return Result(completion=True, score=self.get_score())


@XApiTransformersRegistry.register(event_name(PASSED))
class ScormPassedTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a learner passes a package.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_PASSED,
        display=LanguageMap({constants.EN: PASSED}),
    )
    additional_fields = ("result",)

    def get_result(self):
        """
        Returns:
            `Result`
        """
        return Result(success=True, score=self.get_score())


@XApiTransformersRegistry.register(event_name(FAILED))
class ScormFailedTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a learner fails a package.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_FAILED,
        display=LanguageMap({constants.EN: FAILED}),
    )
    additional_fields = ("result",)

    def get_result(self):
        """
        Returns:
            `Result`
        """
        return Result(success=False, score=self.get_score())


@XApiTransformersRegistry.register(event_name(TERMINATED))
class ScormTerminatedTransformer(BaseScormTransformer):
    """
    Transformer for the event emitted when a package ends a SCORM session.
    """

    _verb = Verb(
        id=constants.XAPI_VERB_TERMINATED,
        display=LanguageMap({constants.EN: TERMINATED}),
    )
    additional_fields = ("result",)

    def get_result(self):
        """
        Report the time spent by the learner in the SCORM session.

        Returns:
            `Result`
        """
        return Result(
            duration=self.get_data("data.duration"),
            completion=self.get_data("data.completion_status") == "completed",
            score=self.get_score(),
        )
