import io
import os
import re
from setuptools import setup


def get_version(*file_paths):
    """
    Extract the version string from the file at the given relative path fragments.
    """
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    with open(filename, encoding='utf-8') as opened_file:
        version_file = opened_file.read()
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                                  version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


VERSION = get_version("openedxscorm", "__about__.py")

def package_data(pkg, roots):
    """Generic function to find package_data.

    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.

    """
    data = []
    for root in roots:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


here = os.path.abspath(os.path.dirname(__file__))

with io.open(os.path.join(here, "README.rst"), "rt", encoding="utf8") as f:
    readme = f.read()

setup(
    name="openedx-scorm-xblock",
    version=VERSION,
    description="Scorm XBlock for Open edX",
    long_description=readme,
    long_description_content_type="text/x-rst",
    author="Overhang.IO",
    author_email="contact@overhang.io",
    maintainer="Edly",
    maintainer_email="zia.fazal@edly.io",
    project_urls={
        "Documentation": "https://github.com/overhangio/openedx-scorm-xblock",
        "Code": "https://github.com/overhangio/openedx-scorm-xblock",
        "Issue tracker": "https://github.com/overhangio/openedx-scorm-xblock/issues",
        "Community": "https://discuss.openedx.com",
    },
    packages=["openedxscorm"],
    python_requires=">=3.8",
    install_requires=["xblock", "web-fragments"],
    entry_points={"xblock.v1": ["scorm = openedxscorm:ScormXBlock"]},
    package_data=package_data("openedxscorm", ["static", "public", "locale"]),
    license="AGPLv3",
    classifiers=["License :: OSI Approved :: GNU Affero General Public License v3"],
)
