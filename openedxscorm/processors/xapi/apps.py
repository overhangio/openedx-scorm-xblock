"""
Optional Django application that registers the xAPI transformers.

This application is **not** installed automatically: the SCORM XBlock is not a
Django plugin and adding it to ``INSTALLED_APPS`` is a deliberate choice made by
operators who route their events to an LRS. See the "Learner activity tracking"
section of the README for the settings to add.

Its only job is to import the transformers once the app registry is ready,
which registers them with event-routing-backends in every process that routes
events, including the Celery workers.
"""

from django.apps import AppConfig


class ScormXApiConfig(AppConfig):
    """
    Configuration of the optional xAPI application of the SCORM XBlock.
    """

    name = "openedxscorm.processors.xapi"
    label = "openedxscorm_xapi"
    verbose_name = "Open edX SCORM XBlock xAPI transformers"

    def ready(self):
        """
        Register the xAPI transformers of the SCORM events.
        """
        from openedxscorm.processors.xapi import (  # pylint: disable=import-outside-toplevel,unused-import
            event_transformers,
        )
