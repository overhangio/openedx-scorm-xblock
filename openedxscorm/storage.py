"""
Storage backend for scorm metadata export.
"""

import os
from django.conf import settings

from storages.backends.s3boto3 import S3Boto3Storage


class S3ScormStorage(S3Boto3Storage):
    """
    S3 backend for scorm metadata export
    """

    def __init__(
        self, xblock, bucket_name=None, querystring_auth=None, querystring_expire=None
    ):
        self.xblock = xblock
        # No need to serve assets from a custom domain.
        self.custom_domain = None
        super().__init__(
            bucket_name=bucket_name,
            querystring_auth=querystring_auth,
            querystring_expire=querystring_expire,
        )


def s3(xblock):
    """
    Creates and returns an instance of the S3ScormStorage class.

    This function takes an xblock instance as its argument and returns an instance
    of the S3ScormStorage class. The S3ScormStorage class is defined in the
    'openedxscorm.storage' module and provides storage functionality specific to
    SCORM XBlock.

    Args:
        xblock (XBlock): An instance of the SCORM XBlock.

    Returns:
        S3ScormStorage: An instance of the S3ScormStorage class.
    """
    bucket_name = xblock.xblock_settings.get(
        "S3_BUCKET_NAME", settings.AWS_STORAGE_BUCKET_NAME
    )
    querystring_auth = xblock.xblock_settings.get("S3_QUERY_AUTH", True)
    querystring_expire = xblock.xblock_settings.get("S3_EXPIRES_IN", 604800)
    return S3ScormStorage(
        xblock=xblock,
        bucket_name=bucket_name,
        querystring_auth=querystring_auth,
        querystring_expire=querystring_expire,
    )
