"""
All xAPI transformers of the SCORM XBlock.

Importing this module registers the transformers in the event-routing-backends
registry. It is imported by :class:`openedxscorm.processors.xapi.apps.ScormXApiConfig`
so that the transformers are available in every process that routes events,
including the Celery workers.
"""

from openedxscorm.processors.xapi.event_transformers.scorm_events import (
    ScormCompletedTransformer,
    ScormFailedTransformer,
    ScormInitializedTransformer,
    ScormInteractedTransformer,
    ScormPassedTransformer,
    ScormScoredTransformer,
    ScormTerminatedTransformer,
)
