# -*- coding: utf-8 -*-
import io
import json
import unittest
import zipfile


from ddt import ddt, data
from freezegun import freeze_time
import mock
from xblock.field_data import DictFieldData

from .scormxblock import (
    MAX_SCANNED_SIZE,
    PACKAGE_WARNING_MESSAGES,
    WARNING_NO_COMPLETION_STATUS,
    PackageScan,
    ScormError,
    ScormXBlock,
)


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

    @staticmethod
    def make_package_zip(files):
        """
        Creates an in-memory SCORM package containing the given
        {file name: contents} mapping.
        """
        package_file = io.BytesIO()
        with zipfile.ZipFile(package_file, "w") as package_zipfile:
            for file_name, content in files.items():
                package_zipfile.writestr(file_name, content)
        package_file.seek(0)
        return package_file

    @data(
        "cmi.core.lesson_status",  # Scorm 1.2
        "cmi.completion_status",  # Scorm 2004
        "lesson_status",  # minified driver assembling the "cmi." prefix
    )
    @mock.patch.object(
        ScormXBlock,
        "extract_folder_path",
        new_callable=mock.PropertyMock,
        return_value="scorm/block/sha1",
    )
    def test_extract_package_of_package_reporting_completion(
        self, element, _extract_folder_path
    ):
        block = self.make_one()
        block._storage = mock.Mock()

        block.extract_package(
            self.make_package_zip(
                {
                    "imsmanifest.xml": "<manifest/>",
                    "js/driver.js": f"function report() {{ SetValue('{element}', 'completed'); }}",
                }
            )
        )

        self.assertEqual(block.package_warnings, [])

    @mock.patch.object(
        ScormXBlock,
        "extract_folder_path",
        new_callable=mock.PropertyMock,
        return_value="scorm/block/sha1",
    )
    def test_extract_package_of_package_not_reporting_completion(
        self, _extract_folder_path
    ):
        block = self.make_one()
        block._storage = mock.Mock()

        block.extract_package(
            self.make_package_zip(
                {
                    "imsmanifest.xml": "<manifest/>",
                    "index.html": "<html><script src='js/driver.js'></script></html>",
                    "js/driver.js": "function report() { SetValue('cmi.score.raw', 42); }",
                }
            )
        )

        self.assertEqual(block.package_warnings, [WARNING_NO_COMPLETION_STATUS])
        # The package must still be extracted in full
        self.assertEqual(block._storage.save.call_count, 3)

    @mock.patch.object(
        ScormXBlock,
        "extract_folder_path",
        new_callable=mock.PropertyMock,
        return_value="scorm/block/sha1",
    )
    def test_extract_package_does_not_scan_media_files(self, _extract_folder_path):
        block = self.make_one()
        block._storage = mock.Mock()

        block.extract_package(
            self.make_package_zip(
                {
                    "imsmanifest.xml": "<manifest/>",
                    "lesson_status.mp4": "cmi.core.lesson_status",
                }
            )
        )

        self.assertEqual(block.package_warnings, [WARNING_NO_COMPLETION_STATUS])

    @mock.patch.object(
        ScormXBlock,
        "extract_folder_path",
        new_callable=mock.PropertyMock,
        return_value="scorm/block/sha1",
    )
    def test_scan_extracted_package_of_package_reporting_completion(
        self, _extract_folder_path
    ):
        block = self.make_one()
        block._storage = self.make_storage_with_file(
            b"LMSSetValue('cmi.core.lesson_status', 'completed');"
        )
        block._storage.listdir.return_value = (["js"], ["driver.js"])

        self.assertEqual(block.scan_extracted_package(), [])
        block._storage.open.assert_called_once_with("scorm/block/sha1/driver.js", "rb")

    @mock.patch.object(
        ScormXBlock,
        "extract_folder_path",
        new_callable=mock.PropertyMock,
        return_value="scorm/block/sha1",
    )
    def test_scan_extracted_package_of_package_not_reporting_completion(
        self, _extract_folder_path
    ):
        block = self.make_one()
        block._storage = self.make_storage_with_file(b"LMSSetValue('cmi.score.raw', 42);")
        block._storage.listdir.side_effect = [
            (["js"], ["index.html"]),
            ([], ["driver.js"]),
        ]

        self.assertEqual(
            block.scan_extracted_package(), [WARNING_NO_COMPLETION_STATUS]
        )
        self.assertEqual(block._storage.open.call_count, 2)

    @mock.patch.object(
        ScormXBlock,
        "extract_folder_path",
        new_callable=mock.PropertyMock,
        return_value="scorm/block/sha1",
    )
    def test_scan_extracted_package_of_missing_package(self, _extract_folder_path):
        block = self.make_one()
        block._storage = mock.Mock()
        block._storage.listdir.side_effect = FileNotFoundError

        # A package we could not read tells us nothing, so it must not be
        # reported as a package that does not report completion.
        self.assertEqual(block.scan_extracted_package(), [])

    def test_get_package_warning_messages_without_package(self):
        block = self.make_one()

        self.assertEqual(block.get_package_warning_messages(), [])

    def test_get_package_warning_messages_of_validated_package(self):
        block = self.make_one(
            package_meta={"sha1": "sha1"},
            index_page_path="index.html",
            package_warnings=[WARNING_NO_COMPLETION_STATUS],
        )

        self.assertEqual(
            block.get_package_warning_messages(),
            [PACKAGE_WARNING_MESSAGES[WARNING_NO_COMPLETION_STATUS]],
        )

    def test_get_package_warning_messages_of_valid_package(self):
        block = self.make_one(
            package_meta={"sha1": "sha1"},
            index_page_path="index.html",
            package_warnings=[],
        )

        self.assertEqual(block.get_package_warning_messages(), [])

    @staticmethod
    def patch_cache(cached_value=None):
        """
        Patches the Django cache with the returned mock. Note that the cache
        cannot be patched by the usual `mock.patch(...)` decorator: creating the
        replacement mock makes it inspect the real cache object, which fails
        outside of a configured Django project.
        """
        cache = mock.Mock()
        cache.get.return_value = cached_value
        return mock.patch("openedxscorm.scormxblock.cache", cache), cache

    def test_get_package_warning_messages_scans_unvalidated_package(self):
        block = self.make_one(
            package_meta={"sha1": "sha1"}, index_page_path="index.html"
        )
        block.scan_extracted_package = mock.Mock(
            return_value=[WARNING_NO_COMPLETION_STATUS]
        )
        patched_cache, cache = self.patch_cache()

        with patched_cache:
            messages = block.get_package_warning_messages()

        block.scan_extracted_package.assert_called_once_with()
        cache.set.assert_called_once_with(
            mock.ANY, [WARNING_NO_COMPLETION_STATUS], timeout=None
        )
        self.assertEqual(
            messages, [PACKAGE_WARNING_MESSAGES[WARNING_NO_COMPLETION_STATUS]]
        )

    def test_get_package_warning_messages_of_cached_scan(self):
        block = self.make_one(
            package_meta={"sha1": "sha1"}, index_page_path="index.html"
        )
        block.scan_extracted_package = mock.Mock()
        patched_cache, cache = self.patch_cache([WARNING_NO_COMPLETION_STATUS])

        with patched_cache:
            messages = block.get_package_warning_messages()

        block.scan_extracted_package.assert_not_called()
        cache.set.assert_not_called()
        self.assertEqual(
            messages, [PACKAGE_WARNING_MESSAGES[WARNING_NO_COMPLETION_STATUS]]
        )

    def test_get_package_warning_messages_of_failed_scan(self):
        block = self.make_one(
            package_meta={"sha1": "sha1"}, index_page_path="index.html"
        )
        block.scan_extracted_package = mock.Mock(side_effect=OSError)
        patched_cache, cache = self.patch_cache()

        with patched_cache:
            self.assertEqual(block.get_package_warning_messages(), [])

        cache.set.assert_not_called()

    @data("driver.js", "index.html", "index.htm", "page.xhtml", "a.xml", "a.json", "a.txt")
    def test_package_scan_wants_files_that_may_hold_scorm_api_calls(self, file_name):
        self.assertTrue(PackageScan().wants(file_name))

    @data("movie.mp4", "logo.png", "font.woff2", "style.css", "driver.js.map", "README")
    def test_package_scan_skips_files_that_hold_no_scorm_api_calls(self, file_name):
        self.assertFalse(PackageScan().wants(file_name))

    def test_package_scan_of_empty_package_is_inconclusive(self):
        scan = PackageScan()

        self.assertFalse(scan.is_conclusive)
        self.assertEqual(scan.warnings, [])

    def test_package_scan_of_oversized_package_is_inconclusive(self):
        scan = PackageScan()

        scan.feed(b"x" * MAX_SCANNED_SIZE)

        self.assertTrue(scan.is_done)
        self.assertFalse(scan.wants("driver.js"))
        self.assertEqual(scan.warnings, [])

    def test_package_scan_keeps_a_match_found_in_an_earlier_file(self):
        scan = PackageScan()

        scan.feed(b"LMSSetValue('cmi.core.lesson_status', 'completed');")
        scan.feed(b"LMSSetValue('cmi.core.score.raw', 42);")

        self.assertEqual(scan.warnings, [])

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
