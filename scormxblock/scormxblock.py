import json
import os
import pkg_resources
import zipfile
import shutil

from django.conf import settings
from webob import Response

from xblock.core import XBlock
from xblock.fields import Scope, Integer, String, Float
from xblock.fragment import Fragment

# Make '_' a no-op so we can scrape strings
_ = lambda text: text


class ScormXBlock(XBlock):

    has_score = True

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

    lesson_status = String(
        scope=Scope.user_state,
        default='not attempted'
    )
    lesson_score = Float(
        scope=Scope.user_state,
        default=0
    )

    weight = Float(
        default=1,
        scope=Scope.settings
    )

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self, context=None):
        scheme = 'https' if settings.HTTPS == 'on' else 'http'
        scorm_file = '{}://{}{}'.format(scheme, settings.ENV_TOKENS.get('LMS_BASE'), self.scorm_file)
        html = self.resource_string("static/html/scormxblock.html")
        frag = Fragment(html.format(scorm_file=scorm_file, self=self))
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/scormxblock.js"))
        frag.initialize_js('ScormXBlock')
        return frag

    def studio_view(self, context=None):
        html = self.resource_string("static/html/studio.html")
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/studio.js"))
        frag.initialize_js('ScormStudioXBlock')
        return frag

    @XBlock.handler
    def studio_submit(self, request, suffix=''):
        self.display_name = request.params['display_name']
        if hasattr(request.params['file'], 'file'):
            file = request.params['file'].file
            zip_file = zipfile.ZipFile(file, 'r')
            path_to_file = os.path.join(settings.PROFILE_IMAGE_BACKEND['options']['location'], self.location.block_id)
            if os.path.exists(path_to_file):
                shutil.rmtree(path_to_file)
            zip_file.extractall(path_to_file)
            self.scorm_file = os.path.join(settings.PROFILE_IMAGE_BACKEND['options']['base_url'],
                                           '{}/index.html'.format(self.location.block_id))

        return Response(json.dumps({'result': 'success'}), content_type='application/json')

    @XBlock.json_handler
    def scorm_get_value(self, data, suffix=''):
        name = data.get('name')
        if name == 'cmi.core.lesson_status':
            return {'value': self.lesson_status}
        return {'value': ''}

    @XBlock.json_handler
    def scorm_set_value(self, data, suffix=''):
        context = {'result': 'success'}
        name = data.get('name')
        if name == 'cmi.core.lesson_status' and data.get('value') != 'completed':
            self.lesson_status = data.get('value')
            self.publish_grade()
            context.update({"lesson_score": self.lesson_score})
        if name == 'cmi.core.score.raw':
            self.lesson_score = int(data.get('value', 0))/100.0
        return context

    def publish_grade(self):
        if self.lesson_status == 'passed':
            self.runtime.publish(
                self,
                'grade',
                {
                    'value': self.lesson_score,
                    'max_value': self.weight,
                })
        if self.lesson_status == 'failed':
            self.runtime.publish(
                self,
                'grade',
                {
                    'value': 0,
                    'max_value': self.weight,
                })
            self.lesson_score = 0

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
