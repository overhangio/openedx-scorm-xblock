SCORM XBlock for Open edX
=========================

This is an XBlock to display `SCORM <https://en.wikipedia.org/wiki/Scorm>`__ content within the `Open edX <https://openedx.org>`__ LMS and Studio. It will save student state and report scores to the progress tab of the course.
Currently supports SCORM 1.2 and SCORM 2004 standard.

.. image:: https://github.com/overhangio/openedx-scorm-xblock/raw/master/screenshots/studio.png
    :alt: Studio view

.. image:: https://github.com/overhangio/openedx-scorm-xblock/raw/master/screenshots/lms-fullscreen.png
    :alt: Student fullscreen view

This XBlock was initially developed by `Raccoon Gang <https://raccoongang.com/>`__ and published as `edx_xblock_scorm <https://github.com/raccoongang/edx_xblock_scorm>`__. It was later improved, published on Pypi and relicensed as AGPLv3 thanks to the support of `Compliplus Ltd <https://compliplus.com/>`__.

This XBlock is not compatible with its `ancestor <https://github.com/raccoongang/edx_xblock_scorm>`__: older xblocks cannot be simply migrated to the newer one. However, this xblock can be installed next to the other one and run on the same platform for easier transition.

Features
--------

* Full SCORM data student reports for staff users
* Fullscreen display on button pressed
* Optional display in pop-up window
* Integrated grading, compatible with rescoring
* Optional custom width navigation menu interpreted from manifest file
* Compatibility with `Django storages <https://django-storages.readthedocs.io/>`__, customizable storage backend
* Learner activity tracking: SCORM API calls are emitted as tracking events and, optionally, as xAPI statements

Installation
------------

This XBlock was designed to work out of the box with `Tutor <https://docs.tutor.overhang.io>`__ (Ironwood release).
It comes bundled by default in the official Tutor releases, such that there is no need to install it manually.

For non-Tutor platforms, you should install the `Python package from Pypi <https://pypi.org/project/openedx-scorm-xblock/>`__::

    pip install openedx-scorm-xblock

In the Open edX native installation, you will have to modify the files ``/edx/etc/lms.yml`` and ``/edx/etc/studio.yml``. Replace

.. code-block:: yaml

    X_FRAME_OPTIONS: DENY

By

.. code-block:: yaml

    X_FRAME_OPTIONS: SAMEORIGIN

Usage
-----

In the Studio, go to the advanced settings of your course ("Settings" 🡒 "Advanced Settings"). In the "Advanced Module List" add "scorm". Then hit "Save changes".

Go back to your course content. In the "Add New Component" section, click "Advanced", and then "Scorm module".
Click "Edit" on the newly-created module: this is where you will upload your content package. It should be a ``.zip`` file containing an ``imsmanifest.xml`` file at the root.
The content of the package will be displayed in the Studio and the LMS after you click "Save".

Advanced configuration
----------------------

Asset url
~~~~~~~~~

By default, SCORM modules will be accessible at "/scorm/" urls and static assets will be stored in "scorm" media folders -- either on S3 or in the local storage, depending on your platform configuration. To change this behaviour, modify the xblock-specific ``LOCATION`` setting

.. code-block:: python

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "LOCATION": "alternatevalue",
    }

Custom storage backends
~~~~~~~~~~~~~~~~~~~~~~~

By default, static assets are stored in the default Open edX storage backend.

To override this behaviour, you should define a custom storage function. This function must take the xblock instance as its first and only argument.
For instance, you can store assets in different directories depending on the XBlock organization with

.. code-block:: python

    def scorm_storage(xblock):
        from django.conf import settings
        from django.core.files.storage import get_storage_class
        from openedx.core.djangoapps.site_configuration.models import SiteConfiguration

        subfolder = SiteConfiguration.get_value_for_org(
            xblock.location.org, "SCORM_STORAGE_NAME", "default"
        )
        storage_location = os.path.join(settings.MEDIA_ROOT, subfolder)
        return get_storage_class(settings.DEFAULT_FILE_STORAGE)(
            location=storage_location, base_url=settings.MEDIA_URL + "/" + subfolder
        )

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": scorm_storage,
    }

This should be added both to the LMS and the CMS settings. Instead of a function, a string that points to an importable module may be passed

.. code-block:: python

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": "my.custom.storage.module.get_scorm_storage_function",
    }

Note that the SCORM XBlock comes with extended S3 storage support out of the box. See the following section:

Accessing assets directly from storage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, scorm will proxy assets through the LMS. This is done for security and to make the backend generic enough to be used with different storage backends. However, to access assets directly from the default storage backend, add the following to the ScormXBlock settings:

.. code-block:: python

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "PROXY_ASSETS_LMS": False,
    }    

Scorm will now use the configured storage backends default `url` method instead of proxying the data through the LMS. The url method must be defined on the configured storage class for this to work correctly.

S3 storage
~~~~~~~~~~

The SCORM XBlock will serve static assets from S3 if it is configured as the default storage for Open edX.

However, to configure S3 storage specific to scorm xblock, add the following to your LMS and CMS settings

.. code-block:: python

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": "openedxscorm.storage.s3"
    }

You may define the following additional settings in ``XBLOCK_SETTINGS["ScormXBlock"]``:

* ``S3_BUCKET_NAME`` (default: ``AWS_STORAGE_BUCKET_NAME``): to store SCORM assets in a specific bucket separate from the rest of your Open edX assets.
* ``S3_QUERY_AUTH`` (default: ``True``): boolean flag (``True`` or ``False``) for query string authentication in S3 urls. If your bucket is public, set this value to ``False``. But be aware that in such case your SCORM assets will be publicly available to everyone.
* ``S3_EXPIRES_IN`` (default: 604800): time duration (in seconds) for the presigned URLs to stay valid. The default is one week.

These settings may be added to Tutor by creating a `plugin <https://docs.tutor.overhang.io/plugins/>`__:

.. code-block:: python

    from tutor import hooks

    hooks.Filters.ENV_PATCHES.add_item(
        (
            "openedx-common-settings",
            """
    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": "openedxscorm.storage.s3",
        "S3_BUCKET_NAME": "mybucket",
        ...
    }"""
    )

Learner activity tracking
~~~~~~~~~~~~~~~~~~~~~~~~~

SCORM packages are black boxes: without instrumentation, the only thing the platform knows about a learner session is the grade and the completion status that the package chose to report. This XBlock emits a regular Open edX tracking event for the meaningful SCORM API calls, so that learner activity inside a package shows up in the tracking logs.

The following events are emitted:

.. list-table::
   :header-rows: 1

   * - Event
     - Emitted when
     - Enabled by default
   * - ``openedx.xblock.scorm.initialized``
     - The package calls ``LMSInitialize``/``Initialize``
     - yes
   * - ``openedx.xblock.scorm.interacted``
     - The learner moves through the package, or answers one of its interactions
     - no
   * - ``openedx.xblock.scorm.scored``
     - The package reports a score, on a graded block
     - yes
   * - ``openedx.xblock.scorm.completed``
     - The package reports a "completed" status
     - yes
   * - ``openedx.xblock.scorm.passed`` / ``.failed``
     - The package reports a success status
     - yes
   * - ``openedx.xblock.scorm.terminated``
     - The package calls ``LMSFinish``/``Terminate``; carries the time spent in the session
     - yes

Nothing needs to be installed or configured for these events to be emitted. Progress is not tracked here: ``cmi.progress_measure`` is already reported to the platform as block completion.

``interacted`` is the exception: it is the only event that is both high-volume and that carries learner answers, so it is off by default. Enable it with::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "TRACKING_EVENTS": {
            "interacted": True,
        },
    }

``interacted`` events are emitted when the package writes one of the SCORM elements that indicate that the learner is moving through it. By default these are the current location (``cmi.core.lesson_location`` and ``cmi.location``, which packages update when the learner turns a slide) and the responses given to the interactions of the package. This list is configurable, and accepts ``fnmatch`` patterns::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "TRACKING_INTERACTION_ELEMENTS": [
            "cmi.core.lesson_location",
            "cmi.location",
            "cmi.interactions.*",
        ],
    }

Any other event can be disabled the same way, and a single switch turns tracking off entirely, including the two extra requests that the browser makes to record the beginning and the end of a session::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "TRACKING_EVENTS_ENABLED": False,
    }

Sending SCORM activity to an LRS (xAPI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This package also ships xAPI transformers for the events above, so that platforms running `event-routing-backends <https://github.com/openedx/event-routing-backends>`__ can forward SCORM activity to their LRS (`Aspects <https://docs.openedx.org/projects/openedx-aspects/>`__, for instance). They are **opt-in**: nothing is registered unless you ask for it.

Statements follow the `cmi5 <https://github.com/AICC/CMI-5_Spec_Current>`__ profile: the SCORM block is an ADL "lesson" activity, the verbs are the ADL ``initialized``/``interacted``/``scored``/``completed``/``passed``/``failed``/``terminated`` verbs, and the score, the success status and the session duration are reported in the statement result.

Register the transformers and let the SCORM events through the event pipeline, in the LMS and the CMS settings::

    INSTALLED_APPS.append("openedxscorm.processors.xapi")

    from openedxscorm.tracking import tracked_event_names

    SCORM_TRACKING_EVENTS = tracked_event_names()

    # The events that event-routing-backends processes.
    EVENT_TRACKING_BACKENDS_ALLOWED_XAPI_EVENTS += SCORM_TRACKING_EVENTS

    # Each backend of the tracking pipeline filters events on its own copy of that
    # list, taken when event-routing-backends defined the backends. An event that is
    # missing from these copies is discarded before it reaches a transformer.
    _event_transformer = EVENT_TRACKING_BACKENDS["event_transformer"]["OPTIONS"]
    for _processors in (
        _event_transformer["processors"],
        _event_transformer["backends"]["xapi"]["OPTIONS"]["processors"],
    ):
        for _processor in _processors:
            if _processor["ENGINE"].endswith("NameWhitelistProcessor"):
                _processor["OPTIONS"]["whitelist"] = set(
                    _processor["OPTIONS"]["whitelist"]
                ) | set(SCORM_TRACKING_EVENTS)

    # Platforms that ship their tracking logs through the event bus, as Aspects does
    # when ASPECTS_ENABLE_EVENT_BUS_PRODUCER is enabled, filter on one more copy.
    try:
        EVENT_BUS_TRACKING_LOGS.update(SCORM_TRACKING_EVENTS)
    except NameError:
        pass

``openedxscorm.tracking`` imports nothing from the platform, so the settings may import it.

With Tutor, these settings belong in the ``openedx-lms-production-settings`` and ``openedx-cms-production-settings`` patches, and in their ``-development-`` counterparts: those are applied after event-routing-backends has defined ``EVENT_TRACKING_BACKENDS``, which the snippet above amends.

Development
-----------

Run unit tests with::

    $ pytest /mnt/openedx-scorm-xblock/openedxscorm/tests.py /mnt/openedx-scorm-xblock/openedxscorm/test_processors.py

The tests of the xAPI transformers are skipped unless the optional dependency is installed (``pip install -e ".[xapi]"``).

Troubleshooting
---------------

This XBlock is maintained by Syed Ali Abbas from `Edly <https://edly.io>`__. Community support is available from the official `Open edX forum <https://discuss.openedx.org>`__. Do you need help with this plugin? See the `troubleshooting <https://docs.tutor.overhang.io/troubleshooting.html>`__ section from the Tutor documentation.

Versioning
----------

This XBlock follows an independent ``MAJOR.MINOR.PATCH`` versioning scheme and is **not** tied to the Open edX or Tutor release version. While earlier releases tracked the Tutor version, this package is a standalone XBlock with no dependency on Tutor. To avoid downgrading the already-published version, ``19`` is retained as the current major version, and the project is versioned independently from this release onward.

Contributing
------------

We welcome contributions to this repo! Here are the guidelines for contributing:

Pull Requests
~~~~~~~~~~~~~

For changes to the SCORM XBlock, open a pull request on this repository. Take care to target your pull request to the proper branch:

* **Target master** if your change is compatible with the latest official Open edX release and it carries no major backwards-incompatibility nor risk of regression. This ensures that the latest stable release benefits from bug fixes and incremental improvements. Once merged, your change will automatically be forward-ported to nightly.

* **Target nightly** if your change is only compatible with Open edX's master branches and/or your change would be disruptive to production site operators. If merged, your change will be incorporated into master at the time of the next named Open edX release.

At the beginning of each Open edX named release testing period, we split off from nightly a special pending release branch (e.g., sumac or teak). If your change is necessary for that pending release, merge it to said branch. At the end of the testing period, the pending branch will be merged into master and deleted. As with any set of changes merged to master, they will then be forward-ported to nightly.

Changelog Entry
~~~~~~~~~~~~~~~

Create a changelog entry for significant changes (excluding reformatting or documentation) by running::

    make changelog-entry

Edit the newly created file following the default formatting instructions in the generated file.

Commit Messages
~~~~~~~~~~~~~~~

Write clear Git commit titles and messages. Detail the rationale for your changes, the issue being addressed, and your solution. Include links to relevant forum discussions and describe your use case. Detailed explanations are valuable. For commit titles, follow conventional commits guidelines.

Additionally, if your pull request addresses an existing GitHub issue, include 'Close #XXX' in your commit message, where XXX is the issue number.

License
-------

This work is licensed under the terms of the `GNU Affero General Public License (AGPL) <https://github.com/overhangio/openedx-scorm-xblock/blob/master/LICENSE.txt>`_.
