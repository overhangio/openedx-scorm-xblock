"""
Storage backend for scorm metadata export.
"""
from django.core.files.storage import get_storage_class
from storages.backends.s3boto3 import S3Boto3Storage


class S3ScormStorage(S3Boto3Storage):
    """
    S3 backend for scorm metadata export
    """
    def __init__(self, bucket, querystring_auth, querystring_expire):
        super().__init__(bucket=bucket, querystring_auth=querystring_auth,
                         querystring_expire=querystring_expire)


def scorm_storage(xblock):
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
    bucket = xblock.xblock_settings.get('SCORM_S3_BUCKET_NAME', None)
    querystring_auth = xblock.xblock_settings.get('SCORM_S3_QUERY_AUTH', None)
    querystring_expire = xblock.xblock_settings.get('SCORM_S3_EXPIRES_IN', 604800)
    storage_class = get_storage_class('openedxscorm.storage.S3ScormStorage')
    return storage_class(bucket=bucket, querystring_auth=querystring_auth,
                         querystring_expire=querystring_expire)
