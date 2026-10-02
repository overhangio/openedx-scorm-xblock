"""Exact asset paths and grades for packages with no score elements."""
import hashlib
import io
import unittest
from unittest.mock import Mock

from webob import Request
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds

from .scormxblock import ScormXBlock


class ScormCompatibilityTests(unittest.TestCase):
    @staticmethod
    def block(**fields):
        runtime = Mock()
        runtime.service.return_value = None
        block = ScormXBlock(runtime, DictFieldData(fields), ScopeIds('learner', 'scorm', 'definition', 'usage'))
        block.location = Mock(block_id='legacy-block')
        block.emit_completion = Mock()
        return block

    def test_scoreless_explicit_success_earns_full_credit(self):
        for name, value in (('cmi.core.lesson_status', 'passed'), ('cmi.core.lesson_status', 'completed'),
                            ('cmi.completion_status', 'completed'), ('cmi.success_status', 'passed')):
            with self.subTest(name=name, value=value):
                block = self.block(has_score=True, weight=3)
                result = block.set_value({'name': name, 'value': value})
                self.assertEqual(result.get('grade'), 3)
                self.assertEqual(block.lesson_score, 1)
                self.assertEqual(block.get_grade(), 3)
                grade_events = [call.args[2] for call in block.runtime.publish.call_args_list
                                if call.args[1] == 'grade']
                self.assertEqual(grade_events, [{'value': 3, 'max_value': 3}])

    def test_reported_zero_or_real_score_retains_precedence(self):
        for name, score in (('cmi.core.score.raw', '0'), ('cmi.score.raw', '40'), ('cmi.score.scaled', '0.6')):
            with self.subTest(name=name, score=score):
                block = self.block(has_score=True, weight=2)
                block.set_value({'name': name, 'value': score})
                earned = block.get_grade()
                result = block.set_value({'name': 'cmi.completion_status', 'value': 'completed'})
                self.assertEqual(block.get_grade(), earned)
                self.assertNotIn('grade', result)

    def test_later_actual_score_overwrites_completion_credit(self):
        block = self.block(has_score=True, weight=2)
        block.set_value({'name': 'cmi.core.lesson_status', 'value': 'passed'})
        result = block.set_value({'name': 'cmi.core.score.raw', 'value': '25'})
        self.assertEqual(result['grade'], 0.5)
        self.assertEqual(block.get_grade(), 0.5)

    def test_later_zero_and_nonzero_scores_replace_published_fallback(self):
        for status, terminal in (('cmi.core.lesson_status', 'passed'),
                                 ('cmi.core.lesson_status', 'completed'),
                                 ('cmi.completion_status', 'completed'),
                                 ('cmi.success_status', 'passed')):
            for name in ('cmi.core.score.raw', 'cmi.score.raw', 'cmi.score.scaled'):
                for value in ('0', '0.25'):
                    with self.subTest(status=status, terminal=terminal, score=name, value=value):
                        block = self.block(has_score=True, weight=2)
                        block.set_value({'name': status, 'value': terminal})
                        result = block.set_value({'name': name, 'value': value})
                        publications = [call.args[2] for call in block.runtime.publish.call_args_list
                                        if call.args[1] == 'grade']
                        self.assertEqual(publications[0]['value'], 2)
                        self.assertEqual(len(publications), 2)
                        self.assertEqual(publications[-1]['value'], block.get_grade())
                        self.assertEqual(result['grade'], block.get_grade())

    def test_incomplete_failed_and_ungraded_packages_get_no_fallback_credit(self):
        for fields, name, value in (({'has_score': True}, 'cmi.core.lesson_status', 'incomplete'),
                                    ({'has_score': True}, 'cmi.success_status', 'failed'),
                                    ({'has_score': True, 'success_status': 'failed'}, 'cmi.completion_status', 'completed'),
                                    ({'has_score': False}, 'cmi.completion_status', 'completed')):
            with self.subTest(fields=fields, name=name, value=value):
                block = self.block(**fields)
                result = block.set_value({'name': name, 'value': value})
                self.assertNotIn('grade', result)
                self.assertEqual(block.lesson_score, 0)

    def roots(self):
        block = self.block(package_meta={'sha1': 'package'})
        usage_hash = hashlib.sha1(b'usage', usedforsecurity=False).hexdigest()
        return block, [f'scorm/{usage_hash}/package', 'scorm/legacy-block/package',
                       f'scorm/{usage_hash}', 'scorm/legacy-block']

    @staticmethod
    def storage_with_asset(selected):
        storage = Mock()
        def listing(path):
            prefix = path.rstrip('/') + '/'
            if not selected.startswith(prefix):
                return ([], [])
            relative = selected[len(prefix):]
            if '/' in relative:
                return ([relative.split('/')[0]], [])
            return ([], [relative])
        storage.listdir.side_effect = listing
        storage.exists.side_effect = lambda path: path == selected
        storage.size.return_value = 5
        storage.open.side_effect = lambda path, mode='rb': io.BytesIO(b'exact')
        return storage

    def test_exact_path_reads_each_current_or_legacy_layout_without_listing(self):
        for index in range(4):
            with self.subTest(layout=index):
                block, roots = self.roots()
                selected = roots[index] + '/assets/app.js'
                storage = self.storage_with_asset(selected)
                block._storage = storage
                response = block.assets_proxy(Request.blank('/'), 'assets/app.js?v=1')
                self.assertEqual(response.status_int, 200)
                self.assertEqual(response.body, b'exact')
                self.assertEqual(response.content_length, 5)
                storage.open.assert_called_once_with(selected, 'rb')
                storage.listdir.assert_not_called()

    def test_missing_relative_path_never_falls_back_to_another_basename(self):
        block, roots = self.roots()
        block._storage = Mock()
        block._storage.exists.return_value = False
        block._storage.listdir.return_value = ([], [])
        block._storage.open.side_effect = lambda path, mode='rb': io.BytesIO(b'other')
        block.find_file_path = Mock(return_value=roots[0] + '/other/app.js')
        response = block.assets_proxy(Request.blank('/'), 'missing/app.js')
        self.assertEqual(response.status_int, 404)
        block.find_file_path.assert_not_called()
        block._storage.open.assert_not_called()
        block._storage.listdir.assert_not_called()

    def test_invalid_or_ambiguous_asset_paths_refuse_before_storage(self):
        for path in ('../app.js', '/app.js', 'C:/app.js', 'assets//app.js', 'assets/./app.js',
                     'assets%2fapp.js', 'assets%5capp.js', 'assets/%252e%252e/app.js', 'bad%',
                     'bad%ff', 'assets\\app.js', ''):
            with self.subTest(path=path):
                block, _ = self.roots()
                block._storage = Mock()
                block._storage.listdir.return_value = ([], [])
                block._storage.exists.return_value = False
                block._storage.open.side_effect = lambda path, mode='rb': io.BytesIO(b'other')
                block.find_file_path = Mock(return_value='scorm/other/app.js')
                response = block.assets_proxy(Request.blank('/'), path)
                self.assertEqual(response.status_int, 400)
                block._storage.exists.assert_not_called()
                block._storage.open.assert_not_called()
