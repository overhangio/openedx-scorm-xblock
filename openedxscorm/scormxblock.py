from functools import partial
import json
import hashlib
import os
import logging
import re
import xml.etree.ElementTree as ET
import zipfile

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template
from django.utils import timezone
from webob import Response
import pkg_resources

from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.fields import Scope, String, Float, Boolean, Dict, DateTime, Integer


# Make '_' a no-op so we can scrape strings
def _(text):
    return text


logger = logging.getLogger(__name__)


@XBlock.wants("settings")
class ScormXBlock(XBlock):
    """
    When a user uploads a Scorm package, the zip file is stored in:

        media/{org}/{course}/{block_type}/{block_id}/{sha1}{ext}

    This zip file is then extracted to the media/{scorm_location}/{block_id}.

    The scorm location is defined by the LOCATION xblock setting. If undefined, this is
    "scorm". This setting can be set e.g:

        XBLOCK_SETTINGS["ScormXBlock"] = {
            "LOCATION": "alternatevalue",
        }

    Note that neither the folder the folder nor the package file are deleted when the
    xblock is removed.
    """

    display_name = String(
        display_name=_("Display Name"),
        help=_("Display name for this module"),
        default="Scorm module",
        scope=Scope.settings,
    )
    index_page_path = String(
        display_name=_("Path to the index page in scorm file"), scope=Scope.settings
    )
    package_meta = Dict(scope=Scope.content)
    scorm_version = String(default="SCORM_12", scope=Scope.settings)

    # save completion_status for SCORM_2004
    lesson_status = String(scope=Scope.user_state, default="not attempted")
    success_status = String(scope=Scope.user_state, default="unknown")
    lesson_score = Float(scope=Scope.user_state, default=0)
    weight = Float(default=1, scope=Scope.settings)
    has_score = Boolean(
        display_name=_("Scored"),
        help=_(
            "Select False if this component will not receive a numerical score from the Scorm"
        ),
        default=True,
        scope=Scope.settings,
    )

    # See the Scorm data model:
    # https://scorm.com/scorm-explained/technical-scorm/run-time/
    scorm_data = Dict(scope=Scope.user_state, default={})

    icon_class = String(default="video", scope=Scope.settings)
    width = Integer(
        display_name=_("Display width (px)"),
        help=_("Width of iframe (default: 100%)"),
        scope=Scope.settings,
    )
    height = Integer(
        display_name=_("Display height (px)"),
        help=_("Height of iframe"),
        default=450,
        scope=Scope.settings,
    )

    has_author_view = True

    def render_template(self, template_path, context):
        template_str = self.resource_string(template_path)
        template = Template(template_str)
        return template.render(Context(context))

    @staticmethod
    def resource_string(path):
        """Handy helper for getting static resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def author_view(self, context=None):
        context = context or {}
        if not self.index_page_path:
            context[
                "message"
            ] = "Click 'Edit' to modify this module and upload a new SCORM package."
        return self.student_view(context=context)

    def student_view(self, context=None):
        student_context = self.get_context_student()
        student_context.update(context or {})
        template = self.render_template("static/html/scormxblock.html", student_context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/scormxblock.js"))
        frag.initialize_js(
            "ScormXBlock", json_args={"scorm_version": self.scorm_version}
        )
        return frag

    def studio_view(self, context=None):
        # Note that we could make this xblock editable so that we wouldn't need to
        # create a manual studio view.
        context = self.get_context_studio()
        template = self.render_template("static/html/studio.html", context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/studio.js"))
        frag.initialize_js("ScormStudioXBlock")
        return frag

    @staticmethod
    def json_response(data):
        return Response(json.dumps(data), content_type="application/json")

    @XBlock.handler
    def studio_submit(self, request, _suffix):
        self.display_name = request.params["display_name"]
        self.width = request.params["width"]
        self.height = request.params["height"]
        self.has_score = request.params["has_score"]
        self.icon_class = "problem" if self.has_score == "True" else "video"

        response = {"result": "success", "errors": []}
        if not hasattr(request.params["file"], "file"):
            # File not uploaded
            return self.json_response(response)

        package_file = request.params["file"].file
        self.update_package_meta(package_file)

        # First, save scorm file in the storage for mobile clients
        if default_storage.exists(self.package_path):
            logger.info('Removing previously uploaded "%s"', self.package_path)
            default_storage.delete(self.package_path)
        default_storage.save(self.package_path, File(package_file))
        logger.info('Scorm "%s" file stored at "%s"', package_file, self.package_path)

        # Then, extract zip file
        if default_storage.exists(self.extract_folder_base_path):
            logger.info(
                'Removing previously unzipped "%s"', self.extract_folder_base_path
            )
            recursive_delete(self.extract_folder_base_path)
        with zipfile.ZipFile(package_file, "r") as scorm_zipfile:
            for zipinfo in scorm_zipfile.infolist():
                default_storage.save(
                    os.path.join(self.extract_folder_path, zipinfo.filename),
                    scorm_zipfile.open(zipinfo.filename),
                )

        try:
            self.update_package_fields()
        except ScormError as e:
            response["errors"].append(e.args[0])

        return self.json_response(response)

    @property
    def index_page_url(self):
        if not self.package_meta or not self.index_page_path:
            return ""
        folder = self.extract_folder_path
        if default_storage.exists(
            os.path.join(self.extract_folder_base_path, self.index_page_path)
        ):
            # For backward-compatibility, we must handle the case when the xblock data
            # is stored in the base folder.
            folder = self.extract_folder_base_path
            logger.warning("Serving SCORM content from old-style path: %s", folder)
        return default_storage.url(os.path.join(folder, self.index_page_path))

    @property
    def package_path(self):
        """
        Get file path of storage.
        """
        return (
            "{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}/{sha1}{ext}"
        ).format(
            loc=self.location,
            sha1=self.package_meta["sha1"],
            ext=os.path.splitext(self.package_meta["name"])[1],
        )
        
    @property
    def extract_folder_path(self):
        """
        This path needs to depend on the content of the scorm package. Otherwise,
        served media files might become stale when the package is update.
        """
        return os.path.join(self.extract_folder_base_path, self.package_meta["sha1"])

    @property
    def extract_folder_base_path(self):
        """
        Path to the folder where packages will be extracted.
        """
        return os.path.join(self.scorm_location(), self.location.block_id)

    @XBlock.json_handler
    def scorm_get_value(self, data, _suffix):
        name = data.get("name")
        if name in ["cmi.core.lesson_status", "cmi.completion_status"]:
            return {"value": self.lesson_status}
        if name == "cmi.success_status":
            return {"value": self.success_status}
        if name in ["cmi.core.score.raw", "cmi.score.raw"]:
            return {"value": self.lesson_score * 100}
        return {"value": self.scorm_data.get(name, "")}

    @XBlock.json_handler
    def scorm_set_value(self, data, _suffix):
        context = {"result": "success"}
        name = data.get("name")

        if name in ["cmi.core.lesson_status", "cmi.completion_status"]:
            self.lesson_status = data.get("value")
            if self.has_score and data.get("value") in [
                "completed",
                "failed",
                "passed",
            ]:
                self.publish_grade()
                context.update({"lesson_score": self.lesson_score})
        elif name == "cmi.success_status":
            self.success_status = data.get("value")
            if self.has_score:
                if self.success_status == "unknown":
                    self.lesson_score = 0
                self.publish_grade()
                context.update({"lesson_score": self.lesson_score})
        elif name in ["cmi.core.score.raw", "cmi.score.raw"] and self.has_score:
            self.lesson_score = int(data.get("value", 0)) / 100.0
            self.publish_grade()
            context.update({"lesson_score": self.lesson_score})
        else:
            self.scorm_data[name] = data.get("value", "")

        context.update({"completion_status": self.get_completion_status()})
        return context

    def publish_grade(self):
        if self.lesson_status == "failed" or (
            self.scorm_version == "SCORM_2004"
            and self.success_status in ["failed", "unknown"]
        ):
            self.runtime.publish(self, "grade", {"value": 0, "max_value": self.weight})
        else:
            self.runtime.publish(
                self, "grade", {"value": self.lesson_score, "max_value": self.weight}
            )

    def max_score(self):
        """
        Return the maximum score possible.
        """
        return self.weight if self.has_score else None

    def get_context_studio(self):
        return {
            "field_display_name": self.fields["display_name"],
            "field_has_score": self.fields["has_score"],
            "field_width": self.fields["width"],
            "field_height": self.fields["height"],
            "scorm_xblock": self,
        }

    def get_context_student(self):
        return {
            "index_page_url": self.index_page_url,
            "completion_status": self.get_completion_status(),
            "scorm_xblock": self,
        }

    def update_package_meta(self, package_file):
        self.package_meta["sha1"] = self.get_sha1(package_file)
        self.package_meta["name"] = package_file.name
        self.package_meta["last_updated"] = timezone.now().strftime(
            DateTime.DATETIME_FORMAT
        )
        self.package_meta["size"] = package_file.seek(0, 2)
        package_file.seek(0)

    def update_package_fields(self):
        """
        Update version and index page path fields.
        """
        self.index_page_path = ""
        imsmanifest_path = os.path.join(self.extract_folder_path, "imsmanifest.xml")
        try:
            imsmanifest_file = default_storage.open(imsmanifest_path)
        except IOError:
            raise ScormError(
                "Invalid package: could not find 'imsmanifest.xml' file at the root of the zip file"
            )
        else:
            tree = ET.parse(imsmanifest_file)
            imsmanifest_file.seek(0)
            self.index_page_path = "index.html"
            namespace = ""
            for _, node in ET.iterparse(imsmanifest_file, events=["start-ns"]):
                if node[0] == "":
                    namespace = node[1]
                    break
            root = tree.getroot()

            if namespace:
                resource = root.find(
                    "{{{0}}}resources/{{{0}}}resource".format(namespace)
                )
                schemaversion = root.find(
                    "{{{0}}}metadata/{{{0}}}schemaversion".format(namespace)
                )
            else:
                resource = root.find("resources/resource")
                schemaversion = root.find("metadata/schemaversion")

            if resource:
                self.index_page_path = resource.get("href")
            if (schemaversion is not None) and (
                re.match("^1.2$", schemaversion.text) is None
            ):
                self.scorm_version = "SCORM_2004"
            else:
                self.scorm_version = "SCORM_12"

    def get_completion_status(self):
        completion_status = self.lesson_status
        if self.scorm_version == "SCORM_2004" and self.success_status != "unknown":
            completion_status = self.success_status
        return completion_status

    def scorm_location(self):
        """
        Unzipped files will be stored in a media folder with this name, and thus
        accessible at a url with that also includes this name.
        """
        default_scorm_location = "scorm"
        settings_service = self.runtime.service(self, "settings")
        if not settings_service:
            return default_scorm_location
        xblock_settings = settings_service.get_settings_bucket(self)
        return xblock_settings.get("LOCATION", default_scorm_location)

    
    @staticmethod
    def get_sha1(file_descriptor):
        """
        Get file hex digest (fingerprint).
        """
        block_size = 8 * 1024
        sha1 = hashlib.sha1()
        for block in iter(partial(file_descriptor.read, block_size), ""):
            sha1.update(block)
        file_descriptor.seek(0)
        return sha1.hexdigest()

    def student_view_data(self):
        """
        Inform REST api clients about original file location and it's "freshness".
        Make sure to include `student_view_data=openedxscorm` to URL params in the request.
        """
        if self.index_page_url:
            return {
                "last_modified": self.package_meta.get("last_updated", ""),
                "scorm_data": default_storage.url(self.package_path),
                "size": self.package_meta.get("size", 0),
                "index_page": self.index_page_path,
            }
        return {}

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            (
                "ScormXBlock",
                """<vertical_demo>
                <openedxscorm/>
                </vertical_demo>
             """,
            ),
        ]


def recursive_delete(root):
    """
    Recursively delete the contents of a directory in the Django default storage.
    Unfortunately, this will not delete empty folders, as the default FileSystemStorage
    implementation does not allow it.
    """
    directories, files = default_storage.listdir(root)
    for directory in directories:
        recursive_delete(os.path.join(root, directory))
    for f in files:
        default_storage.delete(os.path.join(root, f))


class ScormError(Exception):
    pass
