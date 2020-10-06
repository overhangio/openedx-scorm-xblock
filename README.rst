`SCORM <https://en.wikipedia.org/wiki/Scorm>`__ XBlock for `Open edX <https://openedx.org>`__
=============================================================================================

This is an XBlock to display SCORM content within the Open edX LMS and Studio. It will save student state and report scores to the progress tab of the course.
Currently supports SCORM 1.2 and SCORM 2004 standard.

.. image:: https://github.com/overhangio/openedx-scorm-xblock/raw/master/screenshots/studio.png
    :alt: Studio view

.. image:: https://github.com/overhangio/openedx-scorm-xblock/raw/master/screenshots/lms-fullscreen.png
    :alt: Student fullscreen view

This XBlock was initially developed by `Raccoon Gang <https://raccoongang.com/>`__ and published as `edx_xblock_scorm <https://github.com/raccoongang/edx_xblock_scorm>`__. It was later improved, published on Pypi and relicensed as AGPLv3 thanks to the support of `Compliplus Ltd <https://compliplus.com/>`__.

This XBlock is not compatible with its `ancestor <https://github.com/raccoongang/edx_xblock_scorm>`__: older xblocks cannot be simply migrated to the newer one. However, this xblock can be installed next to the other one and run on the same platform for easier transition.

Installation
------------

This XBlock was designed to work out of the box with `Tutor <https://docs.tutor.overhang.io>`__ (Ironwood release). But in this fork it has been made compatible with juniper release. It comes bundled by default in the official Tutor releases, such that there is no need to install it manually.

For non-Tutor platforms, you can install it using following command::

    pip install git+https://github.com/edly-io/openedx-scorm-xblock.git@master#egg=openedx-scorm-xblock

Usage
-----

In the Studio, go to the advanced settings of your course ("Settings" 🡒 "Advanced Settings"). In the "Advanced Module List" add "scorm". Then hit "Save changes".

Go back to your course content. In the "Add New Component" section, click "Advanced", and then "Scorm module". Click "Edit" on the newly-created module: this is where you will upload your content package. It should be a ``.zip`` file containing an ``imsmanifest.xml`` file at the root. The content of the package will be displayed in the Studio and the LMS after you click "Save".

Advanced configuration
----------------------

By default, SCORM modules will be accessible at "/scorm/" urls and static assets will be stored in "scorm" media folders -- either on S3 or in the local storage, depending on your platform configuration. To change this behaviour, modify the xblock-specific ``LOCATION`` setting::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "LOCATION": "alternatevalue",
        "SCORM_FILE_STORAGE_TYPE": "openedx.features.clearesult_features.backend_storage.ScormXblockS3Storage"
    }

If you are using this xblock locally, there is a configuration variable whose value you will have to set empty string::

    XBLOCK_SETTINGS["ScormXBlock"] = {
        "SCORM_MEDIA_BASE_URL": ""
    }

You can face x-frame-options restrictions. For that, you can use any workaround. Like for local you can install any extension on chrome which will disable x-frame-restrictions.
For example: `Ignore X-Frame headers <https://chrome.google.com/webstore/detail/ignore-x-frame-headers/gleekbfjekiniecknbkamfmkohkpodhe>`_ Google Chrome extension.


Development
-----------

Run unit tests with::

    $ NO_PREREQ_INSTALL=1 paver test_system -s lms -t openedxscorm
Nginx settings (for non-local environments) if you are using s3-buckets
------
In ``/etc/nginx/sites-enabled/lms`` and ``/etc/nginx/sites-enabled/cms`` put these rules::

    location /scorm/ {
        rewrite ^/scorm/(.*) /$1 break;
        try_files $uri @s3;
      }
    location @s3 {
        proxy_pass <YOUR S3 BUCKET BASE PATH>;
      }

**For exmaple** Your s3 bucket base path can be
https://c90081bas2001edx.s3.amazonaws.com
We are doing this because in openedx, we will retrieve content from s3-bucket and display it in an iframe. But because of x-frame-options restrictions we will be blocked. So, to overcome that hurdle we have just replaced the base s3-bucket url with our platform base url in our xblock. Let's understand it from an exmaple. Let's say one of your url for scorm asset available on s3-bucket is
https://c90081bas2001edx.s3.amazonaws.com/scorm/503a49b7ed1d4a2caa22af84df87fa8c/f792c4c021da74aac780e072bf16aa0ed4987767/shared/launchpage.html
But openedx will be unable to open it in an iframe. So what we have done is that we have replaced the base url of this url with the base url of openedx so the source url for the iframe will be
https://dev.learn.clearesult.com/scorm/503a49b7ed1d4a2caa22af84df87fa8c/f792c4c021da74aac780e072bf16aa0ed4987767/shared/launchpage.html
In this way we overcome the x-frame-options restrictions. Now the other problem is that our scorm asset is not available on this url. It is available on s3-bucket. This is where the nginx rules come handy. When any hit will be made for
https://dev.learn.clearesult.com/scorm/503a49b7ed1d4a2caa22af84df87fa8c/f792c4c021da74aac780e072bf16aa0ed4987767/shared/launchpage.html
It will go to nginx where we have already written a rule that for all those requests whose urls start with `/scorm/`, we will replace the base url with s3-bucket base-url. So, in this way the final request will be made to the actual url i.e.
https://c90081bas2001edx.s3.amazonaws.com/scorm/503a49b7ed1d4a2caa22af84df87fa8c/f792c4c021da74aac780e072bf16aa0ed4987767/shared/launchpage.html


License
-------

This work is licensed under the terms of the `GNU Affero General Public License (AGPL) <https://github.com/overhangio/openedx-scorm-xblock/blob/master/LICENSE.txt>`_.
