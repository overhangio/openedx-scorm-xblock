import json
import hashlib
import re
import os
import logging
import pkg_resources
import zipfile
import shutil
import xml.etree.ElementTree as ET

from functools import partial
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template
from django.utils import timezone
from webob import Response
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

from xblock.core import XBlock
from xblock.fields import Scope, String, Float, Boolean, Dict, DateTime, Integer
from xblock.fragment import Fragment


# Make '_' a no-op so we can scrape strings
_ = lambda text: text

log = logging.getLogger(__name__)

SCORM_ROOT = os.path.join(settings.MEDIA_ROOT, 'scorm')
SCORM_URL = os.path.join(settings.MEDIA_URL, 'scorm')


class ScormXBlock(XBlock):

    display_name = String(
        display_name=_("Display Name"),
        help=_("Display name for this module"),
        default="Scorm",
        scope=Scope.settings,
    )
    scorm_file = String(
        display_name=_("Upload scorm file"),
        scope=Scope.settings,
    )
    scorm_file_meta = Dict(
        scope=Scope.content
    )
    version_scorm = String(
        default="SCORM_12",
        scope=Scope.settings,
    )
    # save completion_status for SCORM_2004
    lesson_status = String(
        scope=Scope.user_state,
        default='not attempted'
    )
    success_status = String(
        scope=Scope.user_state,
        default='unknown'
    )
    data_scorm = Dict(
        scope=Scope.user_state,
        default={}
    )
    lesson_score = Float(
        scope=Scope.user_state,
        default=0
    )
    weight = Float(
        default=1,
        scope=Scope.settings
    )
    has_score = Boolean(
        display_name=_("Scored"),
        help=_("Select True if this component will receive a numerical score from the Scorm"),
        default=False,
        scope=Scope.settings
    )
    icon_class = String(
        default="video",
        scope=Scope.settings,
    )
    width = Integer(
        display_name=_("Display Width (px)"),
        help=_('Width of iframe, if empty, the default 100%'),
        scope=Scope.settings
    )
    height = Integer(
        display_name=_("Display Height (px)"),
        help=_('Height of iframe'),
        default=450,
        scope=Scope.settings
    )

    has_author_view = True

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self, context=None):
        context_html = self.get_context_student()
        template = self.render_template('static/html/scormxblock.html', context_html)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/scormxblock.js"))
        settings = {
            'version_scorm': self.version_scorm
        }
        frag.initialize_js('ScormXBlock', json_args=settings)
        return frag

    def studio_view(self, context=None):
        context_html = self.get_context_studio()
        template = self.render_template('static/html/studio.html', context_html)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/studio.js"))
        frag.initialize_js('ScormStudioXBlock')
        return frag

    def author_view(self, context):
        html = self.resource_string("static/html/author_view.html")
        frag = Fragment(html)
        return frag

    @XBlock.handler
    def studio_submit(self, request, suffix=''):
        self.display_name = request.params['display_name']
        self.width = request.params['width']
        self.height = request.params['height']
        self.has_score = request.params['has_score']
        self.icon_class = 'problem' if self.has_score == 'True' else 'video'

        if hasattr(request.params['file'], 'file'):
            scorm_file = request.params['file'].file

            # First, save scorm file in the storage for mobile clients
            self.scorm_file_meta['sha1'] = self.get_sha1(scorm_file)
            self.scorm_file_meta['name'] = scorm_file.name
            self.scorm_file_meta['path'] = path = self._file_storage_path()
            self.scorm_file_meta['last_updated'] = timezone.now().strftime(DateTime.DATETIME_FORMAT)

            if default_storage.exists(path):
                log.info('Removing previously uploaded "{}"'.format(path))
                default_storage.delete(path)

            default_storage.save(path, File(scorm_file))
            self.scorm_file_meta['size'] = default_storage.size(path)
            log.info('"{}" file stored at "{}"'.format(scorm_file, path))

            # Now unpack it into SCORM_ROOT to serve to students later
            zip_file = zipfile.ZipFile(scorm_file, 'r')
            path_to_file = os.path.join(SCORM_ROOT, self.location.block_id)

            if os.path.exists(path_to_file):
                shutil.rmtree(path_to_file)

            zip_file.extractall(path_to_file)
            self.set_fields_xblock(path_to_file)

        return Response(json.dumps({'result': 'success'}), content_type='application/json')

    @XBlock.json_handler
    def scorm_get_value(self, data, suffix=''):
        name = data.get('name')
        if name in ['cmi.core.lesson_status', 'cmi.completion_status']:
            return {'value': self.lesson_status}
        elif name == 'cmi.success_status':
            return {'value': self.success_status}
        elif name in ['cmi.core.score.raw', 'cmi.score.raw']:
            return {'value': self.lesson_score * 100}
        else:
            return {'value': self.data_scorm.get(name, '')}

    @XBlock.json_handler
    def scorm_set_value(self, data, suffix=''):
        context = {'result': 'success'}
        name = data.get('name')

        if name in ['cmi.core.lesson_status', 'cmi.completion_status']:
            self.lesson_status = data.get('value')
            if self.has_score and data.get('value') in ['completed', 'failed', 'passed']:
                self.publish_grade()
                context.update({"lesson_score": self.lesson_score})

        elif name == 'cmi.success_status':
            self.success_status = data.get('value')
            if self.has_score:
                if self.success_status == 'unknown':
                    self.lesson_score = 0
                self.publish_grade()
                context.update({"lesson_score": self.lesson_score})

        elif name in ['cmi.core.score.raw', 'cmi.score.raw'] and self.has_score:
            self.lesson_score = int(data.get('value', 0))/100.0
            context.update({"lesson_score": self.lesson_score})
        else:
            self.data_scorm[name] = data.get('value', '')

        context.update({"completion_status": self.get_completion_status()})
        return context

    def publish_grade(self):
        if self.lesson_status == 'failed' or (self.version_scorm == 'SCORM_2004'
                                              and self.success_status in ['failed', 'unknown']):
            self.runtime.publish(
                self,
                'grade',
                {
                    'value': 0,
                    'max_value': self.weight,
                })
        else:
            self.runtime.publish(
                self,
                'grade',
                {
                    'value': self.lesson_score,
                    'max_value': self.weight,
                })

    def max_score(self):
        """
        Return the maximum score possible.
        """
        return self.weight if self.has_score else None

    def get_context_studio(self):
        return {
            'field_display_name': self.fields['display_name'],
            'field_scorm_file': self.fields['scorm_file'],
            'field_has_score': self.fields['has_score'],
            'field_width': self.fields['width'],
            'field_height': self.fields['height'],
            'scorm_xblock': self
        }

    def get_context_student(self):
        scorm_file_path = ''
        if self.scorm_file:
            scheme = 'https' if settings.HTTPS == 'on' else 'http'
            scorm_file_path = '{}://{}{}'.format(
                scheme,
                configuration_helpers.get_value('site_domain', settings.ENV_TOKENS.get('LMS_BASE')),
                self.scorm_file
            )

        return {
            'scorm_file_path': scorm_file_path,
            'completion_status': self.get_completion_status(),
            'scorm_xblock': self
        }

    def render_template(self, template_path, context):
        template_str = self.resource_string(template_path)
        template = Template(template_str)
        return template.render(Context(context))

    def set_fields_xblock(self, path_to_file):
        path_index_page = 'index.html'
        try:
            tree = ET.parse('{}/imsmanifest.xml'.format(path_to_file))
        except IOError:
            pass
        else:
            namespace = ''
            for node in [node for _, node in ET.iterparse('{}/imsmanifest.xml'.format(path_to_file), events=['start-ns'])]:
                if node[0] == '':
                    namespace = node[1]
                    break
            root = tree.getroot()

            if namespace:
                resource = root.find('{{{0}}}resources/{{{0}}}resource'.format(namespace))
                schemaversion = root.find('{{{0}}}metadata/{{{0}}}schemaversion'.format(namespace))
            else:
                resource = root.find('resources/resource')
                schemaversion = root.find('metadata/schemaversion')

            if resource:
                path_index_page = resource.get('href')
            if (schemaversion is not None) and (re.match('^1.2$', schemaversion.text) is None):
                self.version_scorm = 'SCORM_2004'
            else:
                self.version_scorm = 'SCORM_12'

        self.scorm_file = os.path.join(SCORM_URL, '{}/{}'.format(self.location.block_id, path_index_page))

    def get_completion_status(self):
        completion_status = self.lesson_status
        if self.version_scorm == 'SCORM_2004' and self.success_status != 'unknown':
            completion_status = self.success_status
        return completion_status

    def _file_storage_path(self):
        """
        Get file path of storage.
        """
        path = (
            '{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}'
            '/{sha1}{ext}'.format(
                loc=self.location,
                sha1=self.scorm_file_meta['sha1'],
                ext=os.path.splitext(self.scorm_file_meta['name'])[1]
            )
        )
        return path

    def get_sha1(self, file_descriptor):
        """
        Get file hex digest (fingerprint).
        """
        block_size = 8 * 1024
        sha1 = hashlib.sha1()
        for block in iter(partial(file_descriptor.read, block_size), ''):
            sha1.update(block)
        file_descriptor.seek(0)
        return sha1.hexdigest()

    def student_view_data(self):
        """
        Inform REST api clients about original file location and it's "freshness".
        Make sure to include `student_view_data=scormxblock` to URL params in the request.
        """
        if self.scorm_file and self.scorm_file_meta:
            return {'last_modified': self.scorm_file_meta.get('last_updated', ''),
                    'scorm_data': default_storage.url(self._file_storage_path()),
                    'size': self.scorm_file_meta.get('size', 0)}
        return {}

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("ScormXBlock",
             """<vertical_demo>
                <scormxblock/>
                </vertical_demo>
             """),
        ]
