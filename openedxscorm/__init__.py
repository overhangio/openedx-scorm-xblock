"""
The SCORM XBlock.

``ScormXBlock`` is imported lazily: importing it pulls in the Django models of
the platform, which is only possible once the app registry is ready. Operators
are expected to import ``openedxscorm.tracking`` from their Django settings --
to declare the tracking events of this XBlock to event-routing-backends -- and
that import runs long before the apps are loaded. Entry points resolve
``openedxscorm:ScormXBlock`` through attribute access, so the XBlock is still
found the usual way.
"""


def __getattr__(name):
    if name == "ScormXBlock":
        from .scormxblock import ScormXBlock  # pylint: disable=import-outside-toplevel

        return ScormXBlock
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
