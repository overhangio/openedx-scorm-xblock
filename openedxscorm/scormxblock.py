import json
import hashlib
import os
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
import mimetypes
import urllib

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Q
from django.template import Context, Template
from django.utils import timezone
from django.utils.module_loading import import_string
from webob import Response
from six import string_types
from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.completable import CompletableXBlockMixin
from xblock.exceptions import JsonHandlerError
from xblock.fields import Scope, String, Float, Boolean, Dict, DateTime, Integer

try:
    # Older Open edX releases (Redwood and earlier) install a backported version of
    # importlib.resources: https://pypi.org/project/importlib-resources/
    import importlib_resources
except ModuleNotFoundError:
    # Starting with Sumac, Open edX drops importlib-resources in favor of the standard library:
    # https://docs.python.org/3/library/importlib.resources.html#module-importlib.resources
    from importlib import resources as importlib_resources

try:
    try:
        from common.djangoapps.student.models import CourseEnrollment
    except RuntimeError:
        # Older Open edX releases have a different import path
        from student.models import CourseEnrollment
    from lms.djangoapps.courseware.models import StudentModule
except ImportError:
    CourseEnrollment = None
    StudentModule = None


# Make '_' a no-op so we can scrape strings
def _(text):
    return text


logger = logging.getLogger(__name__)
OS_PATH_ALT_SEP = '\\'


@XBlock.wants("settings")
@XBlock.wants("user")
class ScormXBlock(XBlock, CompletableXBlockMixin):

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

    # lesson_status is for SCORM 1.2 and can take the following values:
    # "passed", "completed", "failed", "incomplete", "browsed", "not attempted"
    # In SCORM_2004, status is broken down in two elements:
    # - cmi.completion_status: "completed" vs "incomplete"
    # - cmi.success_status: "passed" vs "failed"
    # We denormalize these two elements by storing the completion status in self.lesson_status.
    lesson_status = String(scope=Scope.user_state, default="not attempted")
    success_status = String(scope=Scope.user_state, default="unknown")

    lesson_score = Float(scope=Scope.user_state, default=0)
    weight = Float(
        default=1,
        display_name=_("Weight"),
        help=_("Weight/Maximum grade"),
        scope=Scope.settings,
    )
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
    popup_on_launch = Boolean(
        display_name=_("Launch in pop-up window"),
        help=_(
            "Launch in pop-up window instead of embedding the SCORM content in "
            "an iframe. Enable this for older packages that need to be run in "
            "separate window."
        ),
        default=False,
        scope=Scope.settings,
    )
    enable_navigation_menu = Boolean(
        display_name=_("Display navigation menu"),
        help=_(
            "Select True to display a navigation menu on the left side to display table of contents"
        ),
        default=False,
        scope=Scope.settings,
    )
    enable_fullscreen_button = Boolean(
        display_name=_("Show Fullscreen Button"),
        help=_("Select True to show fullscreen button in the SCORM content"),
        default=True,
        scope=Scope.settings,
    )

    navigation_menu = String(scope=Scope.settings, default="")

    navigation_menu_width = Integer(
        display_name=_("Display width of navigation menu(px)"),
        help=_(
            "Width of navigation menu. This assumes that Navigation Menu is enabled. (default: 30%)"
        ),
        scope=Scope.settings,
    )

    has_author_view = True

    def render_template(self, template_path, context):
        template_str = self.resource_string(template_path)
        template = Template(template_str)
        return template.render(Context(context))

    def get_current_user_attr(self, attr: str):
        return self.get_current_user().opt_attrs.get(attr)

    def get_current_user(self):
        return self.runtime.service(self, "user").get_current_user()

    def initialize_student_info(self):
        user_id = self.get_current_user_attr("edx-platform.user_id")
        username = self.get_current_user_attr("edx-platform.username")
        
        self.scorm_data["cmi.core.student_id"] = user_id
        self.scorm_data["cmi.learner_id"] = user_id
        self.scorm_data["cmi.learner_name"] = username
        self.scorm_data["cmi.core.student_name"] = username

    @staticmethod
    def resource_string(path):
        """Handy helper for getting static resources from our kit."""
        try:
            data = importlib_resources.files(__name__).joinpath(path).read_bytes()
        except TypeError:
            data = importlib_resources.files(__package__).joinpath(path).read_bytes()
        return data.decode("utf8")

    def author_view(self, context=None):
        context = context or {}
        if not self.index_page_path:
            context["message"] = "Click 'Edit' to modify this module and upload a new SCORM package."
        context["can_view_student_reports"] = True
        return self.student_view(context=context)

    def student_view(self, context=None):
        student_context = {
            "index_page_url": urllib.parse.unquote(self.index_page_url),
            "completion_status": self.lesson_status,
            "grade": self.get_grade(),
            "can_view_student_reports": self.can_view_student_reports,
            "scorm_xblock": self,
            "navigation_menu": self.navigation_menu,
            "popup_on_launch": self.popup_on_launch,
        }
        student_context.update(context or {})
        self.initialize_student_info()
        template = self.render_template("static/html/scormxblock.html", student_context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/scorm.js"))
        frag.add_javascript(self.resource_string("static/js/src/scormxblock.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/renderjson.js"))
        frag.initialize_js(
            "ScormXBlock",
            json_args={
                "scorm_version": self.scorm_version,
                "popup_on_launch": self.popup_on_launch,
                "popup_width": self.width or 800,
                "popup_height": self.height or 800,
                "scorm_data": self.scorm_data,
                "block_height": self.height or 450,
            },
        )
        return frag

    @XBlock.handler
    def assets_proxy(self, request, suffix):
        """
        Proxy view for serving assets. It receives a request with the path to the asset to serve
        and returns the asset's file contents.

        Parameters:
        ----------
        request : django.http.request.HttpRequest
            HTTP request object containing the path to the asset to serve.
        suffix : str
            The part of the URL after 'assets_proxy/', i.e., the path to the asset to serve.

        Returns:
        -------
        Response object containing the content of the requested file with the appropriate content type.
        """
        try:
            clean_suffix = self.clean_asset_path(suffix)
        except ScormError:
            logger.error("Invalid asset path: %r", suffix)
            return Response("Invalid asset path", status=400, content_type="text/plain")
        file_name = os.path.basename(clean_suffix)
        requested_path = os.path.join(self.extract_folder_path, clean_suffix)
        if self.storage.exists(requested_path):
            file_path = requested_path
        else:
            # Preserve legacy basename lookup for packages or callers that do
            # not request the extracted relative path. Exact-path lookup above
            # avoids this fallback for normal requests with duplicate basenames.
            file_path = self.find_file_path(file_name)
        file_type, _ = mimetypes.guess_type(file_name)
        with self.storage.open(file_path) as response:
            file_content = response.read()


        return Response(file_content, content_type=file_type)

    def studio_view(self, context=None):
        # Note that we cannot use xblockutils's StudioEditableXBlockMixin because we
        # need to support package file uploads.
        studio_context = {
            "field_display_name": self.fields["display_name"],
            "field_has_score": self.fields["has_score"],
            "field_weight": self.fields["weight"],
            "field_width": self.fields["width"],
            "field_height": self.fields["height"],
            "field_popup_on_launch": self.fields["popup_on_launch"],
            "field_enable_navigation_menu": self.fields["enable_navigation_menu"],
            "field_enable_fullscreen_button": self.fields["enable_fullscreen_button"],
            "field_navigation_menu_width": self.fields["navigation_menu_width"],
            "popup_on_launch": self.fields["popup_on_launch"],
            "scorm_xblock": self,
        }
        studio_context.update(context or {})
        template = self.render_template("static/html/studio.html", studio_context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/scormxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/studio.js"))
        frag.initialize_js("ScormStudioXBlock")
        return frag

    @staticmethod
    def json_response(data):
        return Response(
            json.dumps(data), content_type="application/json", charset="utf8"
        )

    @XBlock.handler
    def studio_submit(self, request, _suffix):
        self.display_name = request.params["display_name"]
        self.width = parse_int(request.params["width"], None)
        self.height = parse_int(request.params["height"], None)
        self.has_score = request.params["has_score"] == "1"
        self.enable_navigation_menu = request.params["enable_navigation_menu"] == "1"
        self.enable_fullscreen_button = request.params["enable_fullscreen_button"] == "1"
        self.navigation_menu_width = parse_int(
            request.params["navigation_menu_width"], None
        )
        self.weight = parse_float(request.params["weight"], 1)
        self.popup_on_launch = request.params["popup_on_launch"] == "1"
        self.icon_class = "problem" if self.has_score else "video"

        response = {"result": "success", "errors": []}
        if not hasattr(request.params["file"], "file"):
            # File not uploaded
            return self.json_response(response)

        package_file = request.params["file"].file
        self.update_package_meta(package_file)

        # Clean storage folder, if it already exists
        self.clean_storage()

        # Extract zip file
        try:
            self.extract_package(package_file)
            self.update_package_fields()
        except ScormError as e:
            response["errors"].append(e.args[0])

        return self.json_response(response)

    @XBlock.handler
    def popup_window(self, request, _suffix):
        """
        Standalone popup window
        """
        rendered = self.render_template(
            "static/html/popup.html",
            {
                "index_page_url": self.index_page_url,
                "width": self.width or 800,
                "height": self.height or 800,
                "navigation_menu": self.navigation_menu,
                "navigation_menu_width": self.navigation_menu_width,
                "enable_navigation_menu": self.enable_navigation_menu,
                "enable_fullscreen_button": self.enable_fullscreen_button,
                "popup_on_launch": self.popup_on_launch,
            },
        )
        return Response(body=rendered)

    def clean_storage(self):
        if self.path_exists(self.extract_folder_base_path):
            logger.info(
                'Removing previously unzipped "%s"', self.extract_folder_base_path
            )
            self.recursive_delete(self.extract_folder_base_path)

    def recursive_delete(self, root):
        """
        Recursively delete the contents of a directory in the Django default storage.
        Unfortunately, this will not delete empty folders, as the default FileSystemStorage
        implementation does not allow it.
        """
        directories, files = self.storage.listdir(root)
        for directory in directories:
            self.recursive_delete(os.path.join(root, directory))
        for f in files:
            self.storage.delete(os.path.join(root, f))

    def extract_package(self, package_file):
        with zipfile.ZipFile(package_file, "r") as scorm_zipfile:
            zipinfos = scorm_zipfile.infolist()
            root_path = None
            root_depth = -1
            # Find root folder which contains imsmanifest.xml
            for zipinfo in zipinfos:
                if os.path.basename(zipinfo.filename) == "imsmanifest.xml":
                    depth = len(os.path.split(zipinfo.filename))
                    if depth < root_depth or root_depth < 0:
                        root_path = os.path.dirname(zipinfo.filename)
                        root_depth = depth

            if root_path is None:
                raise ScormError(
                    "Could not find 'imsmanifest.xml' file in the scorm package"
                )

            for zipinfo in zipinfos:
                # Extract only files that are below the root
                if zipinfo.filename.startswith(root_path):
                    # Do not unzip folders, only files. In Python 3.6 we will have access to
                    # the is_dir() method to verify whether a ZipInfo object points to a
                    # directory.
                    # https://docs.python.org/3.6/library/zipfile.html#zipfile.ZipInfo.is_dir
                    # TODO: remove backported 'is_dir' method once upgraded to 
                    # python 3.12.3 or greater. 
                    if not is_dir(zipinfo):
                        dest_path = os.path.join(
                            self.extract_folder_path,
                            os.path.relpath(zipinfo.filename, root_path),
                        )
                        self.storage.save(
                            dest_path,
                            ContentFile(scorm_zipfile.read(zipinfo.filename)),
                        )

    def add_xml_to_node(self, node):
        """
        Export hook. The platform sets ``runtime.export_fs`` to the OLX
        export filesystem before calling this. We re-zip the extracted
        package out of ``default_storage`` into that filesystem so the
        block roundtrips through OLX export/import. Outside an export
        context ``export_fs`` is None and this is a pass-through.
        """
        super().add_xml_to_node(node)

        export_fs = getattr(self.runtime, "export_fs", None)
        if export_fs is None:
            return
        if not self.package_meta or "sha1" not in self.package_meta:
            return
        if not self.path_exists(self.extract_folder_path):
            return

        zip_relpath = f"scorm/{self.url_name}/package.zip"
        try:
            export_fs.makedirs(os.path.dirname(zip_relpath), recreate=True)
            with export_fs.open(zip_relpath, "wb") as out:
                self._rezip_extracted_package(out)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to bundle SCORM package into OLX export")
            return

        node.set("scorm_package_path", zip_relpath)

    @classmethod
    def parse_xml(cls, node, runtime, keys):
        """
        Import hook. After the base class restores fields from XML
        attributes (so ``package_meta`` and therefore ``extract_folder_path``
        are populated), look for the package zip the exporter wrote into
        the OLX tarball and re-extract it into ``default_storage``.
        """
        block = super().parse_xml(node, runtime, keys)

        zip_relpath = node.get("scorm_package_path")
        resources_fs = getattr(runtime, "resources_fs", None)
        if not zip_relpath or resources_fs is None:
            return block
        if not resources_fs.exists(zip_relpath):
            return block

        # During OLX import the block's ``scope_ids.usage_id`` is keyed to
        # the source course (the one being imported FROM). The block is
        # then persisted under the target course's keys.
        # ``extract_folder_base_path`` hashes ``scope_ids.usage_id`` to
        # locate files on disk, so extracting under the source key lands
        # files where the rendered block (keyed to the target course)
        # cannot find them. Re-key the block in place for the duration
        # of extraction so files end up where they will be looked up.
        target_usage_id = cls._target_usage_id_for_import(node, runtime)
        original_scope_ids = block.scope_ids
        if target_usage_id is not None and target_usage_id != original_scope_ids.usage_id:
            block.scope_ids = original_scope_ids._replace(usage_id=target_usage_id)

        try:
            with resources_fs.open(zip_relpath, "rb") as zip_file:
                block.extract_package(zip_file)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to rehydrate SCORM package from OLX import")
        finally:
            if block.scope_ids is not original_scope_ids:
                block.scope_ids = original_scope_ids

        return block

    @classmethod
    def _target_usage_id_for_import(cls, node, runtime):
        """
        During OLX import, ``runtime.id_generator`` is a
        ``CourseImportLocationManager`` that carries ``target_course_id``
        — the course the block will be persisted under. Combine it with
        the preserved ``url_name`` (which becomes ``block_id``) to get
        the usage_id the rendered block will eventually see. Returns
        ``None`` for runtimes that don't expose this (no-op fallback).
        """
        id_generator = getattr(runtime, "id_generator", None)
        target_course_id = getattr(id_generator, "target_course_id", None)
        if target_course_id is None:
            return None
        url_name = node.get("url_name")
        if not url_name:
            return None
        try:
            return target_course_id.make_usage_key(node.tag, url_name)
        except Exception:  # pylint: disable=broad-except
            return None

    def _rezip_extracted_package(self, out_file):
        """
        Stream a fresh zip of the extracted SCORM tree into ``out_file``.
        Files are read from ``self.storage`` and written through ``zf.open``
        in chunks so the whole archive is never held in memory at once.
        """
        root = self.extract_folder_path
        with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            stack = [root]
            while stack:
                cur = stack.pop()
                try:
                    dirs, files = self.storage.listdir(cur)
                except FileNotFoundError:
                    continue
                for d in dirs:
                    stack.append(os.path.join(cur, d))
                for f in files:
                    src_path = os.path.join(cur, f)
                    arcname = os.path.relpath(src_path, root)
                    with self.storage.open(src_path, "rb") as fh:
                        with zf.open(arcname, "w", force_zip64=True) as zout:
                            for chunk in iter(lambda fh=fh: fh.read(1024 * 1024), b""):
                                zout.write(chunk)

    def _rehydrate_extract_folder_if_missing(self):
        """
        Self-healing: if our extract folder is empty but we know our sha1,
        search ``scorm_location()`` for another bucket containing the
        same sha1 directory and copy its tree into our extract folder.

        This covers operations that duplicate block metadata without
        touching storage — notably course rerun, which clones blocks at
        the modulestore level and never invokes ``parse_xml``.

        Idempotency is enforced via Django's cache, keyed by
        ``scope_ids.usage_id``. Course rerun and OLX import both mint a
        new ``usage_id``, so the cache key naturally misses and a fresh
        verification fires once on first render of the new block. On
        success the key is set and subsequent renders short-circuit
        without listing storage.
        """
        cache_key = f"scorm_xblock:extract_verified:{self.scope_ids.usage_id}"
        if cache.get(cache_key):
            return

        if not self.package_meta or "sha1" not in self.package_meta:
            return

        if self.path_exists(self.extract_folder_path):
            cache.set(cache_key, True, timeout=None)
            return

        sha1 = self.package_meta["sha1"]
        scorm_root = self.scorm_location()

        try:
            bucket_dirs, _ = self.storage.listdir(scorm_root)
        except FileNotFoundError:
            return

        own_bucket = os.path.basename(self.extract_folder_base_path)
        for bucket in bucket_dirs:
            if bucket == own_bucket:
                continue
            candidate = os.path.join(scorm_root, bucket, sha1)
            if not self.path_exists(candidate):
                continue
            try:
                self._copy_storage_tree(candidate, self.extract_folder_path)
                logger.info(
                    "Rehydrated SCORM extract folder for %s from %s",
                    self.scope_ids.usage_id, candidate,
                )
                cache.set(cache_key, True, timeout=None)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Failed to rehydrate SCORM extract folder for %s from %s",
                    self.scope_ids.usage_id, candidate,
                )
            return

    def _copy_storage_tree(self, src_root, dst_root):
        """
        Recursively copy every file under ``src_root`` to ``dst_root``
        using the Django storage API. Both paths are storage-relative —
        we never touch the local filesystem directly, so this works on
        S3 and filesystem backends alike.
        """
        stack = [src_root]
        while stack:
            cur = stack.pop()
            try:
                dirs, files = self.storage.listdir(cur)
            except FileNotFoundError:
                continue
            for d in dirs:
                stack.append(os.path.join(cur, d))
            for f in files:
                src_path = os.path.join(cur, f)
                relpath = os.path.relpath(src_path, src_root)
                dst_path = os.path.join(dst_root, relpath)
                with self.storage.open(src_path, "rb") as src_fh:
                    self.storage.save(dst_path, ContentFile(src_fh.read()))

    @property
    def index_page_url(self):
        if not self.package_meta or not self.index_page_path:
            return ""

        self._rehydrate_extract_folder_if_missing()
        
        # Serve assets by proxying them through the LMS by default
        if self.xblock_settings.get("PROXY_ASSETS_LMS", True):
            return f"{self.proxy_base_url}/{self.index_page_path}"
        
        folder = self.extract_folder_path
        if self.storage.exists(
            os.path.join(self.extract_folder_base_path, self.clean_path(self.index_page_path))
        ):
            # For backward-compatibility, we must handle the case when the xblock data
            # is stored in the base folder.
            folder = self.extract_folder_base_path
            logger.warning("Serving SCORM content from old-style path: %s", folder)

        return self.storage.url(os.path.join(folder, self.index_page_path))

    @property
    def proxy_base_url(self):
        return self.runtime.handler_url(
                self, "assets_proxy"
            ).rstrip("?/")

    @property
    def extract_folder_path(self):
        """
        This path needs to depend on the content of the scorm package. Otherwise,
        served media files might become stale when the package is update.
        """
        return os.path.join(self.extract_folder_base_path, self.package_meta["sha1"])

    def clean_path(self, path):
        """
        Removes query string from a path
        """
        return path.split('?')[0] if path else path

    def clean_asset_path(self, path):
        """
        Clean and validate an asset path requested through the proxy.
        Asset paths must be relative paths that stay within the extracted
        package folder. Absolute paths, drive-letter paths, parent-directory
        traversal, and null bytes are rejected.
        """
        cleaned = urllib.parse.unquote(self.clean_path(path))
        if not cleaned:
            raise ScormError(f"Invalid asset path (empty): {path!r}")
        if "\x00" in cleaned:
            raise ScormError(f"Invalid asset path (null byte): {path!r}")
        if cleaned.endswith(("/", OS_PATH_ALT_SEP)):
            raise ScormError(f"Invalid asset path (directory, not a file): {path!r}")

        normalized_separators_path = cleaned.replace(OS_PATH_ALT_SEP, os.path.sep)
        path_parts = normalized_separators_path.split(os.path.sep)
        cleaned = os.path.normpath(normalized_separators_path)

        if os.path.isabs(cleaned) or re.match(r"^[A-Za-z]:", cleaned):
            raise ScormError(f"Invalid asset path (must be relative): {path!r}")
        if cleaned == os.curdir or os.pardir in path_parts:
            raise ScormError(f"Invalid asset path (path traversal): {path!r}")

        return cleaned
    
    def path_exists(self, path):
        """
        Returs True if given path exists in storage otherwise returns False
        """
        try:
            dirs, files = self.storage.listdir(path)
            return True if dirs or files else False
        except FileNotFoundError:
            return False

    @property
    def extract_folder_base_path(self):
        """
        Path to the folder where packages will be extracted.
        Compute hash of the unique block usage_id and use that as our directory name.
        """
        # For backwards compatibility, we return the old path if the directory exists
        if self.path_exists(self.extract_old_folder_base_path):
            return self.extract_old_folder_base_path
        sha1 = hashlib.sha1()
        sha1.update(str(self.scope_ids.usage_id).encode())
        hashed_usage_id = sha1.hexdigest()
        return os.path.join(self.scorm_location(), hashed_usage_id)
    
    @property
    def extract_old_folder_base_path(self):
        """
        Deprecated Path to the folder where packages will be extracted.
        Deprecated as the block_id was shared by courses when exporting and importing
        them, thus causing storage conflicts.
        Only keeping this here for backwards compatibility.
        """
        return os.path.join(self.scorm_location(), self.location.block_id)

    def get_mode(self, data):
        if "preview" in data["url"]:
            return "review"
        return "normal"

    @XBlock.json_handler
    def scorm_get_value(self, data, _suffix):
        """
        Here we get only the get_value events that were not filtered by the LMSGetValue js function.
        """
        name = data.get("name")
        if name in ["cmi.core.lesson_mode", "cmi.mode"]:
            return {"value": self.get_mode(data)}
        if name in ["cmi.core.lesson_status", "cmi.completion_status"]:
            return {"value": self.lesson_status}
        if name == "cmi.success_status":
            return {"value": self.success_status}
        if name in ["cmi.core.score.raw", "cmi.score.raw"]:
            return {"value": self.lesson_score * 100}
        if name == "cmi.score.scaled":
            return {"value": self.lesson_score}
        if name in ["cmi.core.student_id", "cmi.learner_id"]:
            return {"value": self.get_current_user_attr("edx-platform.user_id")}
        if name in ["cmi.core.student_name", "cmi.learner_name"]:
            return {"value": self.get_current_user_attr("edx-platform.username")}
        return {"value": self.scorm_data.get(name, "")}

    @XBlock.json_handler
    def scorm_set_values(self, data_list, _suffix):
        return [self.set_value(data) for data in data_list]

    @XBlock.json_handler
    def scorm_set_value(self, data, _suffix):
        try:
            return self.set_value(data)
        except ValueError as e:
            return JsonHandlerError(400, e.args[0]).get_response()

    def set_value(self, data):
        name = data.get("name")
        value = data.get("value")
        completion_percent = None
        success_status = None
        completion_status = None
        lesson_score = None

        is_completed = self.lesson_status == "completed"

        self.scorm_data[name] = value
        if name == "cmi.core.lesson_status":
            lesson_status = value
            if lesson_status in ["passed", "failed"]:
                success_status = lesson_status
                if lesson_status == "passed":
                    completion_status = "completed"
            elif lesson_status in ["completed", "incomplete"]:
                completion_status = lesson_status
        elif name == "cmi.success_status":
            success_status = value
        elif name == "cmi.completion_status":
            completion_status = value
        elif name in ["cmi.core.score.raw", "cmi.score.raw"] and self.has_score:
            lesson_score = parse_validate_positive_float(value, name) / 100.0
        elif name == "cmi.score.scaled" and self.has_score:
            lesson_score = parse_validate_positive_float(value, name)
        elif name == "cmi.progress_measure":
            completion_percent = parse_validate_positive_float(value, name)

        context = {"result": "success"}
        if lesson_score is not None:
            self.lesson_score = lesson_score
            context.update({"grade": self.get_grade()})
        if completion_percent is not None:
            self.emit_completion(completion_percent)
        if completion_status:
            self.lesson_status = completion_status
            context.update({"completion_status": completion_status})
        if success_status:
            self.success_status = success_status
        if completion_status == "completed":
            self.emit_completion(1)
        if (
            success_status
            or completion_status == "completed"
            or (is_completed and lesson_score)
        ):
            if self.has_score:
                self.publish_grade()

        return context

    def publish_grade(self):
        self.runtime.publish(
            self,
            "grade",
            {"value": self.get_grade(), "max_value": self.weight},
        )

    def get_grade(self):
        lesson_score = 0 if self.is_failed else self.lesson_score
        return lesson_score * self.weight

    @property
    def is_failed(self):
        return self.success_status == "failed"

    def set_score(self, score):
        """
        Utility method used to rescore a problem.
        """
        if self.has_score:
            self.lesson_score = score.raw_earned
            self.publish_grade()
            self.emit_completion(1)

    def max_score(self):
        """
        Return the maximum score possible.
        """
        return self.weight if self.has_score else None

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
        imsmanifest_path = self.find_file_path("imsmanifest.xml")
        imsmanifest_file = self.storage.open(imsmanifest_path)
        tree = ET.parse(imsmanifest_file)
        imsmanifest_file.seek(0)
        namespace = ""
        for _, node in ET.iterparse(imsmanifest_file, events=["start-ns"]):
            if node[0] == "":
                namespace = node[1]
                break
        root = tree.getroot()

        prefix = "{" + namespace + "}" if namespace else ""
        resource = root.find(
            f"{prefix}resources/{prefix}resource[@href]"
        )
        schemaversion = root.find(
            f"{prefix}metadata/{prefix}schemaversion"
        )

        self.extract_navigation_titles(root, prefix)

        if resource is not None:
            self.index_page_path = resource.get("href")
        else:
            self.index_page_path = self.find_relative_file_path("index.html")
        if (schemaversion is not None) and (
            re.match("^1.2$", schemaversion.text) is None
        ):
            self.scorm_version = "SCORM_2004"
        else:
            self.scorm_version = "SCORM_12"

    def extract_navigation_titles(self, root, prefix):
        """Extracts all the titles of items to build a navigation menu from the imsmanifest.xml file

        Args:
            root (XMLTag): root of the imsmanifest.xml file
            prefix (string): namespace to match with in the xml file
        """
        organizations = root.findall(
            f"{prefix}organizations/{prefix}organization"
        )
        navigation_menu_titles = []
        # Get data for all organizations
        for organization in organizations:
            navigation_menu_titles.append(
                self.find_titles_recursively(organization, prefix, root)
            )
        self.navigation_menu = self.recursive_unorderedlist(navigation_menu_titles)

    def sanitize_input(self, input_str):
        """Removes script tags from string"""
        sanitized_str = re.sub(
            r"<script\b[^>]*>(.*?)</script>", "", input_str, flags=re.IGNORECASE
        )
        return sanitized_str

    def find_titles_recursively(self, item, prefix, root):
        """Recursively iterate through the organization tags and extract the title and resources

        Args:
            item (XMLTag): The current node to iterate on
            prefix (string): namespace to match with in the xml file
            root (XMLTag): root of the imsmanifest.xml file

        Returns:
            List: Nested list of all the title tags and their resources
        """
        children = item.findall(f"{prefix}item")
        item_title = item.find(f"{prefix}title").text
        # Sanitizing every title tag to protect against XSS attacks
        sanitized_title = self.sanitize_input(item_title)
        item_identifier = item.get("identifierref")
        # If item does not have a resource, we don't need to make it into a link
        if not item_identifier:
            resource_link = "#"
        else:
            resource = root.find(
                f"{prefix}resources/{prefix}resource[@identifier='{item_identifier}']"
            )
            # Attach the storage path with the file path
            resource_link = f"{self.proxy_base_url}/{resource.get('href')}"
        if not children:
            return [(sanitized_title, resource_link)]
        child_titles = []
        for child in children:
            if "isvisible" in child.attrib and child.attrib["isvisible"] == "true":
                child_titles.extend(self.find_titles_recursively(child, prefix, root))
        return [(sanitized_title, resource_link), child_titles]

    def recursive_unorderedlist(self, value):
        """Create an HTML unordered list recursively to display navigation menu

        Args:
            value (list): The nested list to create the unordered list
        """

        def has_children(item):
            return len(item) == 2 and (type(item[0]) is tuple and type(item[1]) is list)

        def format(items, tabs=1):
            """Iterate through the nested list and return a formatted unordered list"""
            indent = "\t" * tabs
            # If leaf node, return the li tag
            if type(items) is tuple:
                title, resource_url = items[0], items[1]
                if resource_url != "#":
                    return f"{indent}<li href='{resource_url}' class='navigation-title'>{title}</li>"

                return f"{indent}<li class='navigation-title-header'>{title}</li>"

            output = []
            # If parent node, create another nested unordered list and return
            if has_children(items):
                parent, children = items[0], items[1]
                title, resource_url = parent[0], parent[1]
                for child in children:
                    output.append(format(child, tabs + 1))
                if resource_url != "#":
                    return "\n{indent}<ul>\n{indent}<li href='{resource_url}' class='navigation-title'>{title}</li>\n{indent}<ul>\n{indent}\n{output}</ul>\n{indent}</ul>".format(
                        indent=indent,
                        resource_url=resource_url,
                        title=title,
                        output="\n".join(output),
                    )
                return "\n{indent}<ul>\n{indent}<li class='navigation-title-header'>{title}</li>\n{indent}<ul>\n{indent}\n{output}</ul>\n{indent}</ul>".format(
                    indent=indent,
                    resource_url=resource_url,
                    title=title,
                    output="\n".join(output),
                )
            else:
                for item in items:
                    output.append(format(item, tabs + 1))
                return "{indent}\n{indent}<ul>\n{output}\n{indent}</ul>".format(
                    indent=indent, output="\n".join(output)
                )

        unordered_lists = []
        # Append navigation menus for all organizations in course
        for organization in value:
            unordered_lists.append(format(organization))

        return "\n".join(unordered_lists)

    def find_relative_file_path(self, filename):
        return os.path.relpath(self.find_file_path(filename), self.extract_folder_path)

    def find_file_path(self, filename):
        """
        Search recursively in the extracted folder for a given file. Path of the first
        found file will be returned. Raise a ScormError if file cannot be found.
        """
        path = self.get_file_path(filename, self.extract_folder_path) or self.get_file_path(filename, self.extract_folder_base_path)
        if path is None:
            raise ScormError(f"Invalid package: could not find '{filename}' file")
        return path

    def get_file_path(self, filename, root):
        """
        Same as `find_file_path`, but don't raise error on file not found.
        """
        subfolders, files = self.storage.listdir(root)
        for f in files:
            if f == filename:
                return os.path.join(root, filename)
        for subfolder in subfolders:
            path = self.get_file_path(filename, os.path.join(root, subfolder))
            if path is not None:
                return path
        return None

    def scorm_location(self):
        """
        Unzipped files will be stored in a media folder with this name, and thus
        accessible at a url with that also includes this name.
        """
        default_scorm_location = "scorm"
        return self.xblock_settings.get("LOCATION", default_scorm_location)

    @staticmethod
    def get_sha1(file_descriptor):
        """
        Get file hex digest (fingerprint).
        """
        block_size = 8 * 1024
        sha1 = hashlib.sha1()
        while True:
            block = file_descriptor.read(block_size)
            if not block:
                break
            sha1.update(block)
        file_descriptor.seek(0)
        return sha1.hexdigest()

    def student_view_data(self):
        """
        Inform REST api clients about original file location and it's "freshness".
        Make sure to include `student_view_data=openedxscorm` to URL params in the request.

        Note: we are not sure what this view is for and it might be removed in the future.
        """
        if self.index_page_url:
            return {
                "last_modified": self.package_meta.get("last_updated", ""),
                "size": self.package_meta.get("size", 0),
                "index_page": self.index_page_path,
            }
        return {}

    @XBlock.handler
    def scorm_search_students(self, data, _suffix):
        """
        Search enrolled students by username/email.
        """
        if not self.can_view_student_reports:
            return Response(status=403)
        query = data.params.get("id", "")
        enrollments = (
            CourseEnrollment.objects.filter(
                is_active=True,
                course=self.runtime.course_id,
            )
            .select_related("user")
            .order_by("user__username")
        )
        if query:
            enrollments = enrollments.filter(
                Q(user__username__startswith=query) | Q(user__email__startswith=query)
            )
        # The format of each result is dictated by the autocomplete js library:
        # https://github.com/dyve/jquery-autocomplete/blob/master/doc/jquery.autocomplete.txt
        return self.json_response(
            [
                {
                    "data": {"student_id": enrollment.user.id},
                    "value": f"{enrollment.user.username} ({enrollment.user.email})"
                }
                for enrollment in enrollments[:20]
            ]
        )

    @XBlock.handler
    def scorm_get_student_state(self, data, _suffix):
        if not self.can_view_student_reports:
            return Response(status=403)
        user_id = data.params.get("id")
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return Response(
                body=f"Invalid 'id' parameter {user_id}", status=400
            )
        try:
            module = StudentModule.objects.filter(
                course_id=self.runtime.course_id,
                module_state_key=self.scope_ids.usage_id,
                student__id=user_id,
            ).get()
        except StudentModule.DoesNotExist:
            return Response(
                body=f"No data found for student id={user_id}",
                status=404,
            )
        except StudentModule.MultipleObjectsReturned:
            logger.error(
                "Multiple StudentModule objects found for Scorm xblock: "
                "course_id=%s module_state_key=%s student__id=%s",
                self.runtime.course_id,
                self.scope_ids.usage_id,
                user_id,
            )
            raise
        module_state = json.loads(module.state)
        scorm_data = module_state.get("scorm_data", {})
        return self.json_response(scorm_data)

    @property
    def can_view_student_reports(self):
        if StudentModule is None:
            return False
        return getattr(self.runtime, "user_is_staff", False)

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

    @property
    def storage(self):
        """
        Return the storage backend used to store the assets of this xblock. This is a cached property.
        """
        if not getattr(self, "_storage", None):

            def get_default_storage(_xblock):
                return default_storage

            storage_func = self.xblock_settings.get("STORAGE_FUNC", get_default_storage)
            if isinstance(storage_func, string_types):
                storage_func = import_string(storage_func)
            self._storage = storage_func(self)

        return self._storage

    @property
    def xblock_settings(self):
        """
        Return a dict of settings associated to this XBlock.
        """
        settings_service = self.runtime.service(self, "settings") or {}
        if not settings_service:
            return {}
        return settings_service.get_settings_bucket(self)


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_validate_positive_float(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Could not parse value of '{name}' (must be float): {value}"
        )
    if parsed < 0:
        raise ValueError(f"Value of '{name}' must not be negative: {value}")
    return parsed


def is_dir(zipinfo):
    """Return True if this archive member is a directory."""
    if zipinfo.filename.endswith('/'):
        return True
    elif zipinfo.filename.endswith((os.path.sep, OS_PATH_ALT_SEP)):
        # The ZIP format specification requires to use forward slashes
        # as the directory separator, but in practice some ZIP files
        # created on Windows can use backward slashes.  For compatibility
        # with the extraction code which already handles this:
        return True
    return False 


class ScormError(Exception):
    pass
