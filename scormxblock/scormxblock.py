import json
import re
import os
import pkg_resources
import zipfile
import shutil
import xml.etree.ElementTree as ET

from django.conf import settings
from django.template import Context, Template
from webob import Response

from xblock.core import XBlock
from xblock.fields import Scope, String, Float, Boolean, Dict
from xblock.fragment import Fragment

# Make '_' a no-op so we can scrape strings
_ = lambda text: text


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
    lesson_location = String(
        scope=Scope.user_state,
        default=''
    )
    suspend_data = String(
        scope=Scope.user_state,
        default=''
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
        self.has_score = request.params['has_score']
        self.icon_class = 'problem' if self.has_score == 'True' else 'video'
        if hasattr(request.params['file'], 'file'):
            file = request.params['file'].file
            zip_file = zipfile.ZipFile(file, 'r')
            path_to_file = os.path.join(settings.PROFILE_IMAGE_BACKEND['options']['location'], self.location.block_id)
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
        elif name == 'cmi.core.lesson_location':
            return {'value': self.lesson_location}
        elif name == 'cmi.suspend_data':
            return {'value': self.suspend_data}
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

        elif name == 'cmi.core.lesson_location':
            self.lesson_location = data.get('value', '')

        elif name == 'cmi.suspend_data':
            self.suspend_data = data.get('value', '')
        else:
            self.data_scorm[name] = data.get('value', '')

        context.update({"completion_status": self.get_completion_status()})
        return context

    def publish_grade(self):
        if self.lesson_status == 'failed' or (self.version_scorm == 'SCORM_2004' and self.success_status in ['failed', 'unknown']):
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
            'display_name_value': self.display_name,
            'field_scorm_file': self.fields['scorm_file'],
            'field_has_score': self.fields['has_score'],
            'has_score_value': self.has_score
        }

    def get_context_student(self):
        scorm_file_path = ''
        if self.scorm_file:
            scheme = 'https' if settings.HTTPS == 'on' else 'http'
            scorm_file_path = '{}://{}{}'.format(scheme, settings.ENV_TOKENS.get('LMS_BASE'), self.scorm_file)

        return {
            'scorm_file_path': scorm_file_path,
            'lesson_score': self.lesson_score,
            'weight': self.weight,
            'has_score': self.has_score,
            'completion_status': self.get_completion_status()
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

            if (not schemaversion is None) and (re.match('^1.2$', schemaversion.text) is None):
                self.version_scorm = 'SCORM_2004'

        self.scorm_file = os.path.join(settings.PROFILE_IMAGE_BACKEND['options']['base_url'],
                                       '{}/{}'.format(self.location.block_id, path_index_page))

    def get_completion_status(self):
        completion_status = self.lesson_status
        if self.version_scorm == 'SCORM_2004' and self.success_status != 'unknown':
            completion_status = self.success_status
        return completion_status

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
