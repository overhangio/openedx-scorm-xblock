"""
Pytest configuration.

The xAPI transformers of `openedxscorm.processors.xapi` are Django-dependent, so
Django has to be set up before their test module is imported. Doing it here,
once, keeps the test outcomes independent of the order in which pytest collects
the test modules. When the tests run inside an Open edX installation the
settings are already configured and this is a no-op.

event-routing-backends is an optional dependency: its application is only
declared when it is installed, and `openedxscorm/test_processors.py` skips
itself otherwise.
"""

from importlib.util import find_spec

import django
from django.conf import settings

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

if find_spec("event_routing_backends") is not None:
    INSTALLED_APPS += ["event_routing_backends", "openedxscorm.processors.xapi"]

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=INSTALLED_APPS,
        DATABASES={},
        LMS_ROOT_URL="http://localhost:18000",
        XAPI_AGENT_IFI_TYPE="external_id",
        RUNNING_WITH_TEST_SETTINGS=True,
    )
    django.setup()
