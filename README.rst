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

* Optional auto-fullscreen
* Integrated grading, compatible with rescoring
* Compatibility with `Django storages <https://django-storages.readthedocs.io/>`__, customizable storage backend
* Works with Lilac, the latest Open edX release (use v11 for Koa, v10 for Juniper and v9 for Ironwood)

Installation
------------

This XBlock was designed to work out of the box with `Tutor <https://docs.tutor.overhang.io>`__ (Ironwood release). It comes bundled by default in the official Tutor releases, such that there is no need to install it manually.

For non-Tutor platforms, you should install the `Python package from Pypi <https://pypi.org/project/openedx-scorm-xblock/>`__::

    pip install openedx-scorm-xblock

Usage
-----

In the Studio, go to the advanced settings of your course ("Settings" 🡒 "Advanced Settings"). In the "Advanced Module List" add "scorm". Then hit "Save changes".

Go back to your course content. In the "Add New Component" section, click "Advanced", and then "Scorm module". Click "Edit" on the newly-created module: this is where you will upload your content package. It should be a ``.zip`` file containing an ``imsmanifest.xml`` file at the root. The content of the package will be displayed in the Studio and the LMS after you click "Save".

The people at `Appsembler <https://appsembler.com/>`__ have created a great video that showcases some of the features of this XBlock:

.. image:: https://github.com/overhangio/openedx-scorm-xblock/raw/master/screenshots/youtube.png
    :alt: Open edX Scorm XBlock video
    :target: https://www.youtube.com/watch?v=SnvIG7nqJLg&feature=youtu.be

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

This should be added both to the LMS and the CMS settings. Instead of a function, a string that points to an importable module may be passed::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "STORAGE_FUNC": "my.custom.storage.module.get_scorm_storage_function",
    }

Development
-----------

Run unit tests with::

    $ NO_PREREQ_INSTALL=1 paver test_system -s lms -t openedxscorm

License
-------

This work is licensed under the terms of the `GNU Affero General Public License (AGPL) <https://github.com/overhangio/openedx-scorm-xblock/blob/master/LICENSE.txt>`_.
