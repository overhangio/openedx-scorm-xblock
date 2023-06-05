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
* Compatibility with `Django storages <https://django-storages.readthedocs.io/>`__, customizable storage backend
* Works with Maple, the latest Open edX release (use v12 for Lilac, v11 for Koa, v10 for Juniper and v9 for Ironwood)

Installation
------------

This XBlock was designed to work out of the box with `Tutor <https://docs.tutor.overhang.io>`__ (Ironwood release). It comes bundled by default in the official Tutor releases, such that there is no need to install it manually.

For non-Tutor platforms, you should install the `Python package from Pypi <https://pypi.org/project/openedx-scorm-xblock/>`__::

    pip install openedx-scorm-xblock

In the Open edX native installation, you will have to modify the files ``/edx/etc/lms.yml`` and ``/edx/etc/studio.yml``. Replace::

    X_FRAME_OPTIONS: DENY

By::

    X_FRAME_OPTIONS: SAMEORIGIN

Usage
-----

In the Studio, go to the advanced settings of your course ("Settings" 🡒 "Advanced Settings"). In the "Advanced Module List" add "scorm". Then hit "Save changes".

Go back to your course content. In the "Add New Component" section, click "Advanced", and then "Scorm module". Click "Edit" on the newly-created module: this is where you will upload your content package. It should be a ``.zip`` file containing an ``imsmanifest.xml`` file at the root. The content of the package will be displayed in the Studio and the LMS after you click "Save".

Advanced configuration
----------------------

Asset url
~~~~~~~~~

By default, SCORM modules will be accessible at "/scorm/" urls and static assets will be stored in "scorm" media folders -- either on S3 or in the local storage, depending on your platform configuration. To change this behaviour, modify the xblock-specific ``LOCATION`` setting::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "LOCATION": "alternatevalue",
    }

Custom storage backends
~~~~~~~~~~~~~~~~~~~~~~~

By default, static assets are stored in the default Django storage backend. To override this behaviour, you should define a custom storage function. This function must take the xblock instance as its first and only argument. For instance, you can store assets in different directories depending on the XBlock organisation with::

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

Configuration for SCORM XBlock for AWS S3 storage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to configure the SCORM XBlock for AWS S3 storage use case, you'll need to modify the ``XBLOCK_SETTINGS`` in both the `lms/envs/private.py` and `cms/envs/private.py` files.

Add the following lines to these files::

    # XBlock settings for ScormXBlock
    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": "openedxscorm.storage.s3"
    }

This configuration is specifically for when using an S3 bucket to store SCORM assets.

* ``STORAGE_FUNC`` should be set to "openedxscorm.storage.s3"
* ``S3_BUCKET_NAME`` should be replaced with your specific S3 bucket name. If you do not set ``S3_BUCKET_NAME``, the default bucket used will be ``AWS_STORAGE_BUCKET_NAME`` from your project's settings.
* ``S3_QUERY_AUTH`` is a boolean flag that indicates whether or not to use query string authentication for your S3 URLs. If your bucket is public, you should set this value to False. If it is private, no need to set it.
* ``S3_EXPIRES_IN`` sets the time duration (in seconds) for the presigned URLs to stay valid. The default value here is 604800 which corresponds to one week. If this is not set, the default value will be used.
Once you've made these changes, save both files and restart your LMS and Studio instances for the changes to take effect.

Development
-----------

Run unit tests with::

    $ NO_PREREQ_INSTALL=1 paver test_system -s lms -t openedxscorm

Troubleshooting
---------------

This XBlock is maintained by Régis Behmo from `Overhang.IO <https://overhang.io>`__. Community support is available from the official `Open edX forum <https://discuss.openedx.org>`__. Do you need help with this plugin? See the `troubleshooting <https://docs.tutor.overhang.io/troubleshooting.html>`__ section from the Tutor documentation.

License
-------

This work is licensed under the terms of the `GNU Affero General Public License (AGPL) <https://github.com/overhangio/openedx-scorm-xblock/blob/master/LICENSE.txt>`_.
