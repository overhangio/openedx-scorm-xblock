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

By default, static assets are stored in the default Django storage backend. To override this behaviour, you should define a custom storage function. This function must take the xblock instance as its first and only argument.
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

Note that the SCORM XBlock comes with S3 storage support out of the box. See the following section:

S3 storage
~~~~~~~~~~

The SCORM XBlock may be configured to proxy static SCORM assets stored in either public or private S3 buckets.
To configure S3 storage, add the following to your LMS and CMS settings

.. code-block:: python

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": "openedxscorm.storage.s3"
    }

You may define the following additional settings in ``XBLOCK_SETTINGS["ScormXBlock"]``:

* ``S3_BUCKET_NAME`` (default: ``AWS_STORAGE_BUCKET_NAME``): to store SCORM assets in a specific bucket.
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

Development
-----------

Run unit tests with::

    $ pytest /mnt/openedx-scorm-xblock/openedxscorm/tests.py

Troubleshooting
---------------

This XBlock is maintained by Zia Fazal from `Edly <https://edly.io>`__. Community support is available from the official `Open edX forum <https://discuss.openedx.org>`__. Do you need help with this plugin? See the `troubleshooting <https://docs.tutor.overhang.io/troubleshooting.html>`__ section from the Tutor documentation.

License
-------

This work is licensed under the terms of the `GNU Affero General Public License (AGPL) <https://github.com/overhangio/openedx-scorm-xblock/blob/master/LICENSE.txt>`_.
