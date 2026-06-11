i# Changelog

This file includes a history of past releases. Changes that were not yet added to a release are in the [changelog.d/](./changelog.d) folder.

<!--
⚠️ DO NOT ADD YOUR CHANGES TO THIS FILE! (unless you want to modify existing changelog entries in this file)
Changelog entries are managed by scriv. After you have made some changes to this plugin, create a changelog entry with:
    scriv create
Edit and commit the newly-created file in changelog.d.
If you need to create a new release, create a separate commit just for that. It is important to respect these
instructions, because git commits are used to generate release notes:
  - Modify the version number in `__about__.py`.
  - Collect changelog entries with `scriv collect`
  - The title of the commit should be the same as the new version: "vX.Y.Z".
-->

<!-- scriv-insert-here -->

<a id='changelog-19.0.4'></a>
## v19.0.4 (2026-06-11)

- [Bugfix] SCORM blocks now survive OLX export/import and course rerun. Export bundles the package zip into the OLX tarball; import re-extracts it under the target course's storage path; rerun and previously broken blocks self-heal on first render by locating a sibling storage bucket with the same SHA1. (by @Syed-Ali-Abbas-568)

- 💥[Improvement] Decouple the XBlock version from the Open edX/Tutor release version. The package now follows an independent `MAJOR.MINOR.PATCH` scheme; `19` is retained as the major version to avoid downgrading already-published releases, and subsequent versions no longer correspond to Open edX/Tutor versions. (by @Syed-Ali-Abbas-568)

<a id='changelog-19.0.3'></a>
## v19.0.3 (2025-10-27)

- [Bugfix] Set completion_status to completed when lesson_status is passed to ensure course completion status in SCORM 1.2. (by @so-jd)

- [Bugfix] Don't show navigation menu and change scorm content width from 70% to 100% when navigation menu is disabled in new pop-up window. (by @Faraz32123)

<a id='changelog-19.0.2'></a>
## v19.0.2 (2025-03-11)

- [Bugfix] Make scorm panel and navigation menu cover the entire height of the display in fullscreen. (by @Danyal-Faheem)

- [Improvement] Provide an option to use the default storage backend url to access scorm assets directly from storage. (by @Danyal-Faheem)

<a id='changelog-18.0.2'></a>
## v18.0.2 (2024-07-01)

- [Bugfix] Scorm file upload error which zip is compressed with Windows OS. (by @talhaaslam01)

- [Bugfix] Fix a bug where the scorm block would fail to load with an error message `No module named 'importlib_resources'` (by @kdmccormick)

<a id='changelog-18.0.1'></a>
## v18.0.2 (2024-06-21)

- [Bugfix] Make addition of block usage key in scorm path backward compatible. (by @ziafazal)

<a id='changelog-18.0.0'></a>
## v18.0.0 (2024-05-29)

- [Improvement] Add a scriv-compliant changelog. (by @Danyal-Faheem)

- [Bugfix] Prevent overwriting of exported course scorm data by imported course. (by @Danyal-Faheem)
  - Use usage_key instead of block_id as the location identifier for scorm data as it is unique across course imports.
  - This change will not take effect for previously created scorm modules.

- [Improvement] Removed student information and other scorm data from get value func and sends it as part of
`scorm_data` in student view. (By @ahmed-arb)
 - Added `cmi.score.scaled` to uncached_values,
 - Removed old test cases.
