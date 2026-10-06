# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import unittest


from ddt import ddt, data
from freezegun import freeze_time
import mock
from xblock.field_data import DictFieldData

from .scormxblock import ScormError, ScormXBlock


@ddt
class ScormXBlockTests(unittest.TestCase):
    @staticmethod
    def make_one(**kw):
        """
        Creates a ScormXBlock for testing purpose.
        """
        field_data = DictFieldData(kw)
        block = ScormXBlock(mock.Mock(), field_data, mock.Mock())
        block.location = mock.Mock(
            block_id="block_id", org="org", course="course", block_type="block_type"
        )
        return block

    @staticmethod
    def make_storage_with_file(content=b"content"):
        storage = mock.Mock()
        opened_file = mock.MagicMock()
        opened_file.__enter__.return_value.read.return_value = content
        storage.open.return_value = opened_file
        return storage

    def test_fields_xblock(self):
        block = self.make_one()
        self.assertEqual(block.display_name, "Scorm")
        self.assertEqual(block.index_page_url, "")
        self.assertEqual(block.package_meta, {})
        self.assertEqual(block.scorm_version, "SCORM_12")
        self.assertEqual(block.lesson_status, "not attempted")
        self.assertEqual(block.success_status, "unknown")
        self.assertEqual(block.scorm_data, {})
        self.assertEqual(block.lesson_score, 0)
        self.assertEqual(block.weight, 1)
        self.assertEqual(block.has_score, False)
        self.assertEqual(block.icon_class, "video")
        self.assertEqual(block.width, None)
        self.assertEqual(block.height, 450)

    def test_save_settings_scorm(self):
        block = self.make_one()

        fields = {
            "display_name": "Test Block",
            "has_score": "True",
            "file": None,
            "width": 800,
            "height": 450,
        }

        block.studio_submit(mock.Mock(method="POST", params=fields))
        self.assertEqual(block.display_name, fields["display_name"])
        self.assertEqual(block.has_score, fields["has_score"])
        self.assertEqual(block.icon_class, "problem")
        self.assertEqual(block.width, 800)
        self.assertEqual(block.height, 450)

    @freeze_time("2018-05-01")
    @mock.patch("openedxscorm.ScormXBlock.update_package_fields")
    @mock.patch("openedxscorm.scormxblock.os")
    @mock.patch("openedxscorm.scormxblock.zipfile")
    @mock.patch("openedxscorm.scormxblock.File", return_value="call_file")
    @mock.patch("openedxscorm.scormxblock.default_storage")
    @mock.patch(
        "openedxscorm.ScormXBlock._file_storage_path", return_value="file_storage_path"
    )
    @mock.patch("openedxscorm.ScormXBlock.get_sha1", return_value="sha1")
    def test_save_scorm_zipfile(
        self,
        get_sha1,
        file_storage_path,
        default_storage,
        mock_file,
        zipfile,
        mock_os,
        update_package_fields,
    ):
        block = self.make_one()
        mock_file_object = mock.Mock()
        mock_file_object.configure_mock(name="scorm_file_name")
        default_storage.configure_mock(size=mock.Mock(return_value="1234"))
        mock_os.configure_mock(path=mock.Mock(join=mock.Mock(return_value="path_join")))

        fields = {
            "display_name": "Test Block",
            "has_score": "True",
            "file": mock.Mock(file=mock_file_object),
            "width": None,
            "height": 450,
        }

        block.studio_submit(mock.Mock(method="POST", params=fields))

        expected_package_meta = {
            "path": "file_storage_path",
            "sha1": "sha1",
            "name": "scorm_file_name",
            "last_updated": "2018-05-01T00:00:00.000000",
            "size": "1234",
        }

        get_sha1.assert_called_once_with(mock_file_object)
        file_storage_path.assert_called_once_with()
        default_storage.exists.assert_called_once_with("file_storage_path")
        default_storage.delete.assert_called_once_with("file_storage_path")
        default_storage.save.assert_called_once_with("file_storage_path", "call_file")
        mock_file.assert_called_once_with(mock_file_object)

        self.assertEqual(block.package_meta, expected_package_meta)

        zipfile.ZipFile.assert_called_once_with(mock_file_object, "r")
        update_package_fields.assert_called_once_with()

    def test_build_file_storage_path(self):
        block = self.make_one(
            package_meta={"sha1": "sha1", "name": "scorm_file_name.html"}
        )

        file_storage_path = block.package_path

        self.assertEqual(file_storage_path, "org/course/block_type/block_id/sha1.html")

    @mock.patch.object(
        ScormXBlock, "extract_folder_path", new_callable=mock.PropertyMock
    )
    def test_assets_proxy_serves_exact_requested_path(self, extract_folder_path):
        block = self.make_one()
        storage = self.make_storage_with_file(b"exact asset")
        storage.exists.return_value = True
        block._storage = storage
        block.find_file_path = mock.Mock(return_value="scorm/block/sha1/other/app.js")
        extract_folder_path.return_value = "scorm/block/sha1"

        response = block.assets_proxy(mock.Mock(), "assets/app.js")

        storage.exists.assert_called_once_with("scorm/block/sha1/assets/app.js")
        block.find_file_path.assert_not_called()
        storage.open.assert_called_once_with("scorm/block/sha1/assets/app.js")
        self.assertEqual(response.body, b"exact asset")

    @mock.patch.object(
        ScormXBlock, "extract_folder_path", new_callable=mock.PropertyMock
    )
    def test_assets_proxy_fallback_uses_cleaned_basename(self, extract_folder_path):
        block = self.make_one()
        storage = self.make_storage_with_file()
        storage.exists.return_value = False
        block._storage = storage
        block.find_file_path = mock.Mock(return_value="scorm/block/sha1/fallback/app.js")
        extract_folder_path.return_value = "scorm/block/sha1"

        block.assets_proxy(mock.Mock(), "assets/app.js?v=1")

        storage.exists.assert_called_once_with("scorm/block/sha1/assets/app.js")
        block.find_file_path.assert_called_once_with("app.js")
        storage.open.assert_called_once_with("scorm/block/sha1/fallback/app.js")

    @data(
        "",
        "?v=1",
        ".",
        "/app.js",
        "%2Fapp.js",
        "%5Capp.js",
        r"C:\app.js",
        "C%3A/app.js",
        "../app.js",
        "%2E%2E/app.js",
        "assets/",
        "assets/..",
        "assets/%2E%2E/app.js",
        "assets/../../app.js",
        "assets/%2E%2E/%2E%2E/app.js",
        r"assets\..\app.js",
        "assets/%00/app.js",
    )
    def test_assets_proxy_rejects_invalid_requested_paths(self, suffix):
        block = self.make_one()

        response = block.assets_proxy(mock.Mock(), suffix)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, "text/plain")
        self.assertEqual(response.body, b"Invalid asset path")

    @data(
        "",
        "?v=1",
        ".",
        "/app.js",
        "%2Fapp.js",
        "%5Capp.js",
        r"C:\app.js",
        "C%3A/app.js",
        "../app.js",
        "%2E%2E/app.js",
        "assets/",
        "assets/..",
        "assets/%2E%2E/app.js",
        "assets/../../app.js",
        "assets/%2E%2E/%2E%2E/app.js",
        r"assets\..\app.js",
        "assets/%00/app.js",
    )
    def test_clean_asset_path_rejects_invalid_requested_paths(self, suffix):
        block = self.make_one()

        with self.assertRaises(ScormError):
            block.clean_asset_path(suffix)

    @mock.patch(
        "openedxscorm.ScormXBlock._file_storage_path", return_value="file_storage_path"
    )
    @mock.patch("openedxscorm.scormxblock.default_storage")
    def test_student_view_data(self, default_storage, file_storage_path):
        block = self.make_one(package_meta={"last_updated": "2018-05-01", "size": 1234})
        default_storage.configure_mock(url=mock.Mock(return_value="url_zip_file"))

        student_view_data = block.student_view_data()

        file_storage_path.assert_called_once_with()
        default_storage.url.assert_called_once_with("file_storage_path")
        self.assertEqual(
            student_view_data,
            {"last_modified": "2018-05-01", "scorm_data": "url_zip_file", "size": 1234},
        )

    @mock.patch(
        "openedxscorm.ScormXBlock.get_completion_status",
        return_value="completion_status",
    )
    @mock.patch("openedxscorm.ScormXBlock.publish_grade")
    @data(
        {"name": "cmi.core.lesson_status", "value": "completed"},
        {"name": "cmi.completion_status", "value": "failed"},
        {"name": "cmi.success_status", "value": "unknown"},
    )
    def test_set_status(self, value, publish_grade, get_completion_status):
        block = self.make_one(has_score=True)

        response = block.scorm_set_value(
            mock.Mock(method="POST", body=json.dumps(value))
        )

        publish_grade.assert_called_once_with()
        get_completion_status.assert_called_once_with()

        if value["name"] == "cmi.success_status":
            self.assertEqual(block.success_status, value["value"])
        else:
            self.assertEqual(block.lesson_status, value["value"])

        self.assertEqual(
            response.json,
            {
                "completion_status": "completion_status",
                "lesson_score": 0,
                "result": "success",
            },
        )

    @mock.patch(
        "openedxscorm.ScormXBlock.get_completion_status",
        return_value="completion_status",
    )
    @data(
        {"name": "cmi.core.score.raw", "value": "20"},
        {"name": "cmi.score.raw", "value": "20"},
    )
    def test_set_lesson_score(self, value, get_completion_status):
        block = self.make_one(has_score=True)

        response = block.scorm_set_value(
            mock.Mock(method="POST", body=json.dumps(value))
        )

        get_completion_status.assert_called_once_with()

        self.assertEqual(block.lesson_score, 0.2)

        self.assertEqual(
            response.json,
            {
                "completion_status": "completion_status",
                "lesson_score": 0.2,
                "result": "success",
            },
        )

    @mock.patch(
        "openedxscorm.ScormXBlock.get_completion_status",
        return_value="completion_status",
    )
    @data(
        {"name": "cmi.core.lesson_location", "value": 1},
        {"name": "cmi.location", "value": 2},
        {"name": "cmi.suspend_data", "value": [1, 2]},
    )
    def test_set_other_scorm_values(self, value, get_completion_status):
        block = self.make_one(has_score=True)

        response = block.scorm_set_value(
            mock.Mock(method="POST", body=json.dumps(value))
        )

        get_completion_status.assert_called_once_with()

        self.assertEqual(block.scorm_data[value["name"]], value["value"])

        self.assertEqual(
            response.json,
            {"completion_status": "completion_status", "result": "success"},
        )

    @data(
        {"name": "cmi.core.lesson_status"},
        {"name": "cmi.completion_status"},
        {"name": "cmi.success_status"},
    )
    def test_scorm_get_status(self, value):
        block = self.make_one(lesson_status="status", success_status="status")

        response = block.scorm_get_value(
            mock.Mock(method="POST", body=json.dumps(value))
        )

        self.assertEqual(response.json, {"value": "status"})

    @data(
        {"name": "cmi.core.score.raw"},
        {"name": "cmi.score.raw"},
    )
    def test_scorm_get_lesson_score(self, value):
        block = self.make_one(lesson_score=0.2)

        response = block.scorm_get_value(
            mock.Mock(method="POST", body=json.dumps(value))
        )

        self.assertEqual(response.json, {"value": 20})

    def test_scorm_data_has_user_info_in_student_view(self):
        block = self.make_one()

        block.student_view()
        student_info_keys = [
            "cmi.core.student_id",
            "cmi.learner_id",
            "cmi.learner_name",
            "cmi.core.student_name",
        ]
        self.assertTrue(key in block.scorm_data for key in student_info_keys)



@ddt
class ScormXBlockTrackingTests(unittest.TestCase):
    """
    Tests of the tracking events emitted by the XBlock.
    """

    # `interacted` is opt-in, so most of these tests have to enable it.
    TRACK_INTERACTIONS = {"TRACKING_EVENTS": {"interacted": True}}

    def make_one(self, settings=None, **kw):
        """
        Create a ScormXBlock with the given XBlock settings.
        """
        block = ScormXBlockTests.make_one(**kw)
        patcher = mock.patch.object(
            ScormXBlock, "xblock_settings", new_callable=mock.PropertyMock
        )
        xblock_settings = patcher.start()
        self.addCleanup(patcher.stop)
        xblock_settings.return_value = settings or {}
        return block

    @staticmethod
    def published_events(block):
        """
        Return the (name, data) of the SCORM events published by the block.
        """
        return [
            (call[0][1], call[0][2])
            for call in block.runtime.publish.call_args_list
            if str(call[0][1]).startswith("openedx.xblock.scorm.")
        ]

    def test_set_value_emits_completion_and_score(self):
        block = self.make_one(has_score=True, weight=10)

        block.set_value({"name": "cmi.core.score.raw", "value": "80"})
        block.set_value({"name": "cmi.core.lesson_status", "value": "completed"})

        events = dict(self.published_events(block))
        self.assertIn("openedx.xblock.scorm.scored", events)
        self.assertIn("openedx.xblock.scorm.completed", events)
        self.assertEqual(events["openedx.xblock.scorm.scored"]["scaled_score"], 0.8)
        self.assertEqual(events["openedx.xblock.scorm.scored"]["weighted_score"], 8)
        self.assertEqual(events["openedx.xblock.scorm.scored"]["max_score"], 10)
        self.assertEqual(
            events["openedx.xblock.scorm.completed"]["completion_status"], "completed"
        )

    def test_set_value_emits_success_status(self):
        block = self.make_one(has_score=True)

        block.set_value({"name": "cmi.success_status", "value": "failed"})

        events = dict(self.published_events(block))
        self.assertIn("openedx.xblock.scorm.failed", events)
        self.assertNotIn("openedx.xblock.scorm.passed", events)

    def test_ungraded_blocks_report_no_score(self):
        block = self.make_one(has_score=False)

        block.set_value({"name": "cmi.core.score.raw", "value": "80"})
        block.set_value({"name": "cmi.core.lesson_status", "value": "completed"})

        events = dict(self.published_events(block))
        self.assertNotIn("openedx.xblock.scorm.scored", events)
        self.assertNotIn("scaled_score", events["openedx.xblock.scorm.completed"])

    def test_interactions_are_not_tracked_by_default(self):
        block = self.make_one()

        block.set_value({"name": "cmi.core.lesson_location", "value": "slide_3"})

        self.assertEqual(self.published_events(block), [])

    @data("cmi.core.lesson_location", "cmi.location", "cmi.interactions.0.learner_response")
    def test_learner_interactions_are_tracked(self, cmi_element):
        block = self.make_one(settings=self.TRACK_INTERACTIONS)

        block.set_value({"name": cmi_element, "value": "slide_3"})

        events = dict(self.published_events(block))
        self.assertEqual(
            events["openedx.xblock.scorm.interacted"],
            {
                "block_id": str(block.scope_ids.usage_id),
                "scorm_version": "SCORM_12",
                "cmi_element": cmi_element,
                "value": "slide_3",
            },
        )

    @data("cmi.suspend_data", "cmi.core.total_time", "cmi.interactions.0.id")
    def test_other_elements_are_not_tracked_as_interactions(self, cmi_element):
        block = self.make_one(settings=self.TRACK_INTERACTIONS)

        block.set_value({"name": cmi_element, "value": "some value"})

        self.assertEqual(self.published_events(block), [])

    def test_interaction_elements_are_configurable(self):
        block = self.make_one(
            settings={
                "TRACKING_EVENTS": {"interacted": True},
                "TRACKING_INTERACTION_ELEMENTS": ["cmi.*"],
            }
        )

        block.set_value({"name": "cmi.suspend_data", "value": "state"})

        events = dict(self.published_events(block))
        self.assertIn("openedx.xblock.scorm.interacted", events)

    def test_long_values_are_truncated(self):
        block = self.make_one(
            settings={
                "TRACKING_EVENTS": {"interacted": True},
                "TRACKING_INTERACTION_ELEMENTS": ["cmi.*"],
            }
        )

        block.set_value({"name": "cmi.suspend_data", "value": "x" * 1000})

        events = dict(self.published_events(block))
        self.assertEqual(len(events["openedx.xblock.scorm.interacted"]["value"]), 255)

    def test_tracking_can_be_disabled(self):
        block = self.make_one(
            settings={"TRACKING_EVENTS_ENABLED": False}, has_score=True
        )

        block.set_value({"name": "cmi.core.lesson_status", "value": "completed"})

        self.assertEqual(self.published_events(block), [])

    def test_single_events_can_be_disabled(self):
        block = self.make_one(
            settings={"TRACKING_EVENTS": {"interacted": True, "completed": False}}
        )

        block.set_value({"name": "cmi.core.lesson_location", "value": "slide_3"})
        block.set_value({"name": "cmi.core.lesson_status", "value": "completed"})

        events = dict(self.published_events(block))
        self.assertIn("openedx.xblock.scorm.interacted", events)
        self.assertNotIn("openedx.xblock.scorm.completed", events)

    def test_a_single_state_event_is_emitted_per_batch(self):
        block = self.make_one(settings=self.TRACK_INTERACTIONS, has_score=True)

        block.scorm_set_values(
            mock.Mock(
                method="POST",
                body=json.dumps(
                    [
                        {"name": "cmi.core.score.raw", "value": "50"},
                        {"name": "cmi.score.scaled", "value": "0.8"},
                        {"name": "cmi.core.lesson_location", "value": "slide_1"},
                        {"name": "cmi.location", "value": "slide_2"},
                    ]
                ).encode(),
            )
        )

        events = self.published_events(block)
        scored = [data for name, data in events if name.endswith(".scored")]
        interacted = [data for name, data in events if name.endswith(".interacted")]
        # The score was set twice in the same batch, but only its last value is tracked
        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0]["scaled_score"], 0.8)
        # Every learner interaction of the batch is tracked
        self.assertEqual(len(interacted), 2)

    def test_session_start_and_end_are_tracked(self):
        block = self.make_one()

        block.scorm_initialize(mock.Mock(method="POST", body=json.dumps({}).encode()))
        block.scorm_terminate(mock.Mock(method="POST", body=json.dumps({}).encode()))

        events = dict(self.published_events(block))
        self.assertIn("openedx.xblock.scorm.initialized", events)
        self.assertGreaterEqual(
            events["openedx.xblock.scorm.terminated"]["duration"], 0
        )
        self.assertEqual(block.session_started_at, 0)

    def test_session_duration_is_not_tracked_without_a_session_start(self):
        block = self.make_one()

        block.scorm_terminate(mock.Mock(method="POST", body=json.dumps({}).encode()))

        events = dict(self.published_events(block))
        self.assertNotIn("duration", events["openedx.xblock.scorm.terminated"])

    def test_disabled_tracking_does_not_record_the_session(self):
        block = self.make_one(settings={"TRACKING_EVENTS_ENABLED": False})

        block.scorm_initialize(mock.Mock(method="POST", body=json.dumps({}).encode()))
        block.scorm_terminate(mock.Mock(method="POST", body=json.dumps({}).encode()))

        self.assertEqual(self.published_events(block), [])
        self.assertEqual(block.session_started_at, 0)


class SettingsImportTests(unittest.TestCase):
    """
    Operators import `openedxscorm.tracking` from their Django settings to declare
    the tracking events of this XBlock to event-routing-backends. That happens
    before the app registry is ready, so it must not drag in the XBlock, which
    imports the models of the platform.
    """

    def test_tracking_can_be_imported_without_the_xblock(self):
        # A subprocess, because both modules are already imported in this one.
        subprocess.check_call(
            [
                sys.executable,
                "-c",
                "import sys; import openedxscorm.tracking;"
                " assert 'openedxscorm.scormxblock' not in sys.modules,"
                " 'importing openedxscorm.tracking imported the XBlock'",
            ]
        )
