"""
Storage backend for scorm metadata export.
"""
import os

from django.core.files.storage import get_storage_class
from storages.backends.s3boto3 import S3Boto3Storage


class S3ScormStorage(S3Boto3Storage):
    """
    S3 backend for scorm metadata export
    """
    def __init__(self, xblock, bucket, querystring_auth, querystring_expire):
        self.xblock = xblock
        super().__init__(bucket=bucket, querystring_auth=querystring_auth,
                         querystring_expire=querystring_expire)

    def url(self, name, parameters=None, expire=None):
        """
        Override url method of S3Boto3Storage
        """
        if not self.querystring_auth:
            return self.generate_url(name, parameters, expire)

        if name.startswith(self.xblock.extract_folder_path):
            handler_url = self.xblock.runtime.handler_url(self.xblock, 'assets_proxy')

            # remove trailing '?' if it's present
            if handler_url.endswith('?'):
                handler_url = handler_url[:-1]
            # add '/' if not present at the end
            elif not handler_url.endswith('/'):
                handler_url += '/'

            # construct the URL for proxy function
            return f'{handler_url}{self.xblock.index_page_path}'

        return self.generate_url(os.path.join(self.xblock.extract_folder_path, name), parameters, expire)

    def generate_url(self, name, parameters, expire):
        """
        Generate a URL either with or without querystring authentication
        """
        # Preserve the trailing slash after normalizing the path.
        name = self._normalize_name(self._clean_name(name))
        if expire is None:
            expire = self.querystring_expire

        params = parameters.copy() if parameters else {}
        params['Bucket'] = self.bucket.name
        params['Key'] = self._encode_name(name)
        url = self.bucket.meta.client.generate_presigned_url('get_object', Params=params,
                                                             ExpiresIn=expire)
        if self.querystring_auth:
            return url
        return self._strip_signing_parameters(url)


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
    bucket = xblock.xblock_settings.get('SCORM_S3_BUCKET_NAME', "DEFAULT_S3_BUCKET_NAME")
    querystring_auth = xblock.xblock_settings.get('SCORM_S3_QUERY_AUTH', True)
    querystring_expire = xblock.xblock_settings.get('SCORM_S3_EXPIRES_IN', 604800)
    storage_class = get_storage_class('openedxscorm.storage.S3ScormStorage')
    return storage_class(xblock=xblock, bucket=bucket,
                         querystring_auth=querystring_auth,
                         querystring_expire=querystring_expire)
