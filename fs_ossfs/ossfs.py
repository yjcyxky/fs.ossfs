# -*- coding: utf-8 -*-
"""
    fs_ossfs.ossfs
    ~~~~~~~~~~~~~~

    AliCloud OSS filesystem for PyFilesystem2(Based on https://github.com/PyFilesystem/s3fs).

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

# Python Future
from __future__ import absolute_import, print_function, unicode_literals

# Standard Library
import contextlib
import io
import itertools
import logging
import mimetypes
import os
import tempfile
import threading
from datetime import datetime
from ssl import SSLError
from subprocess import check_output

# Third Party
import six
from botocore.exceptions import ClientError, EndpointConnectionError
from fs import ResourceType, errors
from fs.base import FS
from fs.info import Info
from fs.mode import Mode
from fs.path import basename, dirname, forcedir, join, normpath, relpath
from fs.subfs import SubFS
from fs.time import datetime_to_epoch
from six import text_type

__all__ = ["OSSFS"]


logger = logging.getLogger(__name__)


def exist_tool(name):
    # For more details: https://stackoverflow.com/a/34177358
    """Check whether `name` is on PATH and marked as executable."""

    from shutil import which
    return which(name) is not None


def _make_repr(class_name, *args, **kwargs):
    """Generate a repr string.

    Positional arguments should be the positional arguments used to
    construct the class. Keyword arguments should consist of tuples of
    the attribute value and default. If the value is the default, then
    it won't be rendered in the output.

    Examples::
        def __repr__(self):
            return make_repr('MyClass', 'foo', name=(self.name, None))

    The output of this would be something line ``MyClass('foo',
    name='Will')``.
    """
    arguments = [repr(arg) for arg in args]
    arguments.extend(
        "{}={!r}".format(name, value)
        for name, (value, default) in sorted(kwargs.items())
        if value != default
    )
    return "{}({})".format(class_name, ", ".join(arguments))


class OSSFile(io.IOBase):
    """Proxy for a OSS file."""

    @classmethod
    def factory(cls, filename, mode, on_close):
        """Create a OSSFile backed with a temporary file."""
        _temp_file = tempfile.TemporaryFile()
        proxy = cls(_temp_file, filename, mode, on_close=on_close)
        return proxy

    def __repr__(self):
        return _make_repr(
            self.__class__.__name__, self.__filename, text_type(self.__mode)
        )

    def __init__(self, f, filename, mode, on_close=None):
        self._f = f
        self.__filename = filename
        self.__mode = mode
        self._on_close = on_close

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @property
    def raw(self):
        return self._f

    def close(self):
        if self._on_close is not None:
            self._on_close(self)

    @property
    def closed(self):
        return self._f.closed

    def fileno(self):
        return self._f.fileno()

    def flush(self):
        return self._f.flush()

    def isatty(self):
        return self._f.asatty()

    def readable(self):
        return self.__mode.reading

    def readline(self, limit=-1):
        return self._f.readline(limit)

    def readlines(self, hint=-1):
        if hint == -1:
            return self._f.readlines(hint)
        else:
            size = 0
            lines = []

            for line in iter(self._f.readline, b""):
                lines.append(line)
                size += len(line)
                if size > hint:
                    break
            return lines

    def seek(self, offset, whence=os.SEEK_SET):
        if whence not in (os.SEEK_CUR, os.SEEK_END, os.SEEK_SET):
            raise ValueError("invalid value for 'whence'")

        self._f.seek(offset, whence)
        return self._f.tell()

    def seekable(self):
        return True

    def tell(self):
        return self._f.tell()

    def writable(self):
        return self.__mode.writing

    def writelines(self, lines):
        return self._f.writelines(lines)

    def read(self, n=-1):
        if not self.__mode.reading:
            raise IOError("not open for reading")

        return self._f.read(n)

    def readall(self):
        return self._f.readall()

    def readinto(self, b):
        return self._f.readinto()

    def write(self, b):
        if not self.__mode.writing:
            raise IOError("not open for reading")

        self._f.write(b)
        return len(b)

    def truncate(self, size=None):
        if size is None:
            size = self._f.tell()

        self._f.truncate(size)
        return size


@contextlib.contextmanager
def osserrors(path):
    """Translate OSS errors to FSErrors."""
    try:
        yield
    except ClientError as error:
        _error = error.response.get("Error", {})
        error_code = _error.get("Code", None)
        response_meta = error.response.get("ResponseMetadata", {})
        http_status = response_meta.get("HTTPStatusCode", 200)
        error_msg = _error.get("Message", None)

        if error_code == "NoSuchBucket":
            raise errors.ResourceError(path, exc=error, msg=error_msg)
        if http_status == 404:
            raise errors.ResourceNotFound(path)
        elif http_status == 403:
            raise errors.PermissionDenied(path=path, msg=error_msg)
        else:
            raise errors.OperationFailed(path=path, exc=error)
    except SSLError as error:
        raise errors.OperationFailed(path, exc=error)
    except EndpointConnectionError as error:
        raise errors.RemoteConnectionError(path, exc=error, msg="{}".format(error))


@six.python_2_unicode_compatible
class OSSFS(FS):
    """Construct an AliCloud OSS filesystem for `PyFilesystem <https://pyfilesystem.org>`_

    Arguments:
        bucket_name (str): The OSS bucket name.
        dir_path (str): The root directory within the OSS Bucket. \
            Defaults to ``"/"``
        aws_access_key_id (str): The access key, or ``None`` to read \
            the key from standard configuration files.
        aws_secret_access_key (str): The secret key, or ``None`` to \
            read the key from standard configuration files.
        endpoint_url (str): Alternative endpoint url (``None`` to use \
            default).
        aws_session_token (str):
        region (str): Optional OSS region.
        delimiter (str): The delimiter to separate folders, defaults to \
            a forward slash.
        strict (bool): When ``True`` (default) OSSFS will follow the \
            PyFilesystem specification exactly. Set to ``False`` to disable \
            validation of destination paths which may speed up uploads / \
            downloads.
        cache_control (str): Sets the 'Cache-Control' header for uploads.
        acl (str): Sets the Access Control List header for uploads.
        upload_args (dict): A dictionary for additional upload arguments. \
            See https://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Object.put \
            for details.
        download_args (dict): Dictionary of extra arguments passed to \
            the OSS client.
    """

    _meta = {
        "case_insensitive": False,
        "invalid_path_chars": "\0",
        "network": True,
        "read_only": False,
        "thread_safe": True,
        "unicode_paths": True,
        "virtual": False,
    }

    _object_attributes = [
        "accept_ranges",
        "cache_control",
        "content_disposition",
        "content_encoding",
        "content_language",
        "content_length",
        "content_type",
        "delete_marker",
        "e_tag",
        "expiration",
        "expires",
        "last_modified",
        "metadata",
        "missing_meta",
        "parts_count",
        "replication_status",
        "request_charged",
        "restore",
        "server_side_encryption",
        "sse_customer_algorithm",
        "sse_customer_key_md5",
        "ssekms_key_id",
        "storage_class",
        "version_id",
        "website_redirect_location",
    ]

    def __init__(
        self,
        bucket_name,
        dir_path="/",
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_session_token=None,
        endpoint_url=None,
        region=None,
        delimiter="/",
        strict=True,
        cache_control=None,
        acl=None,
        upload_args=None,
        download_args=None,
    ):
        self._init_aliyun()
        _creds = (aws_access_key_id, aws_secret_access_key)

        if any(_creds) and not all(_creds):
            raise ValueError(
                "aws_access_key_id and aws_secret_access_key "
                "must be set together if specified"
            )

        self._bucket_name = bucket_name
        self.dir_path = dir_path
        self._prefix = relpath(normpath(dir_path)).rstrip("/")
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token
        self.endpoint_url = endpoint_url
        self.region = region
        self.delimiter = delimiter
        self.strict = strict
        self._tlocal = threading.local()

        if cache_control or acl:
            upload_args = upload_args or {}
            if cache_control:
                upload_args["CacheControl"] = cache_control
            if acl:
                upload_args["ACL"] = acl

        self.upload_args = upload_args
        self.download_args = download_args
        super(OSSFS, self).__init__()

    def _init_aliyun(self):
        import tempfile

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.conf')
        temp_file.close()
        os.environ['AWS_CONFIG_FILE'] = temp_file.name

        if exist_tool('aws'):
            shell_cmd = ['aws', 'configure', 'set', 's3.addressing_style', 'virtual', '--p', 'aliyun']
            logger.debug('Initialize AliCloud OSS: %s' % ' '.join(shell_cmd))
            check_output(shell_cmd)
        else:
            logger.info('Please install awscli firstly. `pip install awscli`')
            raise Exception('Initialize AliCloud OSS Error: No awscli.')

    def __repr__(self):
        return _make_repr(
            self.__class__.__name__,
            self._bucket_name,
            dir_path=(self.dir_path, "/"),
            region=(self.region, None),
            delimiter=(self.delimiter, "/"),
        )

    def __str__(self):
        return "<ossfs '{}'>".format(join(self._bucket_name, relpath(self.dir_path)))

    def _path_to_key(self, path):
        """Converts an fs path to a oss key."""
        _path = relpath(normpath(path))
        _key = (
            "{}/{}".format(self._prefix, _path).lstrip("/").replace("/", self.delimiter)
        )
        return _key

    def _path_to_dir_key(self, path):
        """Converts an fs path to a oss key."""
        _path = relpath(normpath(path))
        _key = (
            forcedir("{}/{}".format(self._prefix, _path))
            .lstrip("/")
            .replace("/", self.delimiter)
        )
        return _key

    def _key_to_path(self, key):
        return key.replace(self.delimiter, "/")

    def _get_object(self, path, key):
        _key = key.rstrip(self.delimiter)

        try:
            with osserrors(path):
                obj = self.oss.Object(self._bucket_name, _key)
                obj.load()
        except errors.ResourceNotFound:
            with osserrors(path):
                obj = self.oss.Object(self._bucket_name, _key + self.delimiter)
                obj.load()
                return obj
        else:
            return obj

    def _get_upload_args(self, key):
        upload_args = self.upload_args.copy() if self.upload_args else {}

        if "ContentType" not in upload_args:
            mime_type, _encoding = mimetypes.guess_type(key)
            if six.PY2 and mime_type is not None:
                mime_type = mime_type.decode("utf-8", "replace")
            upload_args["ContentType"] = mime_type or "binary/octet-stream"

        return upload_args

    @property
    def session(self):
        if not hasattr(self._tlocal, "session"):
            from boto3.session import Session
            self._tlocal.session = Session(profile_name='aliyun',
                                           aws_access_key_id=self.aws_access_key_id,
                                           aws_secret_access_key=self.aws_secret_access_key,
                                           aws_session_token=self.aws_session_token,
                                           region_name=self.region)

        return self._tlocal.session

    @property
    def oss(self):
        if not hasattr(self._tlocal, "oss"):
            self._tlocal.oss = self.session.resource(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=self.aws_session_token,
                endpoint_url=self.endpoint_url,
            )

        return self._tlocal.oss

    @property
    def client(self):
        if not hasattr(self._tlocal, "client"):
            self._tlocal.client = self.session.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=self.aws_session_token,
                endpoint_url=self.endpoint_url,
            )

        return self._tlocal.client

    def _info_from_object(self, obj, namespaces):
        """Make an info dict from an oss Object."""
        key = obj.key
        path = self._key_to_path(key)
        name = basename(path.rstrip("/"))
        is_dir = key.endswith(self.delimiter)
        info = {"basic": {"name": name, "is_dir": is_dir}}

        if "details" in namespaces:
            _type = int(ResourceType.directory if is_dir else ResourceType.file)
            info["details"] = {
                "accessed": None,
                "modified": datetime_to_epoch(obj.last_modified),
                "size": obj.content_length,
                "type": _type,
            }

        if "oss" in namespaces:
            ossinfo = info["oss"] = {}
            for name in self._object_attributes:
                value = getattr(obj, name, None)
                if isinstance(value, datetime):
                    value = datetime_to_epoch(value)
                ossinfo[name] = value

        if "urls" in namespaces:
            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._bucket_name, "Key": key},
            )
            info["urls"] = {"download": url}

        return info

    def isdir(self, path):
        _path = self.validatepath(path)

        try:
            return self._getinfo(_path).is_dir
        except errors.ResourceNotFound:
            return False

    def getinfo(self, path, namespaces=None):
        self.check()
        namespaces = namespaces or ()
        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        try:
            dir_path = dirname(_path)
            if dir_path != "/":
                _dir_key = self._path_to_dir_key(dir_path)
                with osserrors(path):
                    obj = self.oss.Object(self._bucket_name, _dir_key)
                    obj.load()
        except errors.ResourceNotFound:
            raise errors.ResourceNotFound(path)

        if _path == "/":
            return Info(
                {
                    "basic": {"name": "", "is_dir": True},
                    "details": {"type": int(ResourceType.directory)},
                }
            )

        obj = self._get_object(path, _key)
        info = self._info_from_object(obj, namespaces)
        return Info(info)

    def _getinfo(self, path, namespaces=None):
        """Gets info without checking for parent dir."""
        namespaces = namespaces or ()
        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        if _path == "/":
            return Info(
                {
                    "basic": {"name": "", "is_dir": True},
                    "details": {"type": int(ResourceType.directory)},
                }
            )

        obj = self._get_object(path, _key)
        info = self._info_from_object(obj, namespaces)
        return Info(info)

    def listdir(self, path):
        _path = self.validatepath(path)
        _oss_key = self._path_to_dir_key(_path)
        prefix_len = len(_oss_key)

        paginator = self.client.get_paginator("list_objects")

        with osserrors(path):
            _paginate = paginator.paginate(
                Bucket=self._bucket_name, Prefix=_oss_key, Delimiter=self.delimiter
            )
            _directory = []

            for result in _paginate:
                common_prefixes = result.get("CommonPrefixes", ())

                for prefix in common_prefixes:
                    _prefix = prefix.get("Prefix")
                    _name = _prefix[prefix_len:]
                    if _name:
                        _directory.append(_name.rstrip(self.delimiter))

                for obj in result.get("Contents", ()):
                    name = obj["Key"][prefix_len:]
                    if name:
                        _directory.append(name)

        if not _directory:
            if not self.getinfo(_path).is_dir:
                raise errors.DirectoryExpected(path)

        return _directory

    def makedir(self, path, permissions=None, recreate=False):
        self.check()
        _path = self.validatepath(path)
        _key = self._path_to_dir_key(_path)

        if not self.isdir(dirname(_path)):
            raise errors.ResourceNotFound(path)

        try:
            self._getinfo(path)
        except errors.ResourceNotFound:
            pass
        else:
            if recreate:
                return self.opendir(_path)
            else:
                raise errors.DirectoryExists(path)

        with osserrors(path):
            _obj = self.oss.Object(self._bucket_name, _key)
            _obj.put(**self._get_upload_args(_key))

        return SubFS(self, path)

    def openbin(self, path, mode="r", buffering=-1, **options):
        _mode = Mode(mode)
        _mode.validate_bin()
        self.check()
        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        if _mode.create:
            def on_close_create(ossfile):
                """Called when the OSS file closes, to upload data."""
                try:
                    ossfile.raw.seek(0)
                    with osserrors(path):
                        self.client.upload_fileobj(
                            ossfile.raw,
                            self._bucket_name,
                            _key,
                            ExtraArgs=self._get_upload_args(_key),
                        )
                finally:
                    ossfile.raw.close()

            try:
                dir_path = dirname(_path)
                if dir_path != "/":
                    _dir_key = self._path_to_dir_key(dir_path)
                    self._get_object(dir_path, _dir_key)
            except errors.ResourceNotFound:
                raise errors.ResourceNotFound(path)

            try:
                info = self._getinfo(path)
            except errors.ResourceNotFound:
                pass
            else:
                if _mode.exclusive:
                    raise errors.FileExists(path)
                if info.is_dir:
                    raise errors.FileExpected(path)

            ossfile = OSSFile.factory(path, _mode, on_close=on_close_create)

            if _mode.appending:
                try:
                    with osserrors(path):
                        self.client.download_fileobj(
                            self._bucket_name,
                            _key,
                            ossfile.raw,
                            ExtraArgs=self.download_args,
                        )
                except errors.ResourceNotFound:
                    pass
                else:
                    ossfile.seek(0, os.SEEK_END)

            return ossfile

        if self.strict:
            info = self.getinfo(path)
            if info.is_dir:
                raise errors.FileExpected(path)

        def on_close(ossfile):
            """Called when the OSS file closes, to upload the data."""
            try:
                if _mode.writing:
                    ossfile.raw.seek(0, os.SEEK_SET)
                    with osserrors(path):
                        self.client.upload_fileobj(
                            ossfile.raw,
                            self._bucket_name,
                            _key,
                            ExtraArgs=self._get_upload_args(_key),
                        )
            finally:
                ossfile.raw.close()

        ossfile = OSSFile.factory(path, _mode, on_close=on_close)

        with osserrors(path):
            self.client.download_fileobj(
                self._bucket_name, _key, ossfile.raw, ExtraArgs=self.download_args
            )

        ossfile.seek(0, os.SEEK_SET)
        return ossfile

    def remove(self, path):
        self.check()
        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        if self.strict:
            info = self.getinfo(path)
            if info.is_dir:
                raise errors.FileExpected(path)

        self.client.delete_object(Bucket=self._bucket_name, Key=_key)

    def isempty(self, path):
        self.check()
        _path = self.validatepath(path)
        _key = self._path_to_dir_key(_path)
        response = self.client.list_objects(
            Bucket=self._bucket_name, Prefix=_key, MaxKeys=2
        )
        contents = response.get("Contents", ())

        for obj in contents:
            if obj["Key"] != _key:
                return False
        return True

    def removedir(self, path):
        self.check()
        _path = self.validatepath(path)

        if _path == "/":
            raise errors.RemoveRootError()

        info = self.getinfo(_path)

        if not info.is_dir:
            raise errors.DirectoryExpected(path)

        if not self.isempty(path):
            raise errors.DirectoryNotEmpty(path)

        _key = self._path_to_dir_key(_path)
        self.client.delete_object(Bucket=self._bucket_name, Key=_key)

    def setinfo(self, path, info):
        self.getinfo(path)

    def readbytes(self, path):
        self.check()

        if self.strict:
            info = self.getinfo(path)
            if not info.is_file:
                raise errors.FileExpected(path)

        _path = self.validatepath(path)
        _key = self._path_to_key(_path)
        bytes_file = io.BytesIO()

        with osserrors(path):
            self.client.download_fileobj(
                self._bucket_name, _key, bytes_file, ExtraArgs=self.download_args
            )

        return bytes_file.getvalue()

    def download(self, path, file, chunk_size=None, **options):
        self.check()

        if self.strict:
            info = self.getinfo(path)
            if not info.is_file:
                raise errors.FileExpected(path)

        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        with osserrors(path):
            self.client.download_fileobj(
                self._bucket_name, _key, file, ExtraArgs=self.download_args
            )

    def exists(self, path):
        self.check()
        _path = self.validatepath(path)

        if _path == "/":
            return True

        _key = self._path_to_dir_key(_path)

        try:
            self._get_object(path, _key)
        except errors.ResourceNotFound:
            return False
        else:
            return True

    def scandir(self, path, namespaces=None, page=None):
        _path = self.validatepath(path)
        namespaces = namespaces or ()
        _oss_key = self._path_to_dir_key(_path)
        prefix_len = len(_oss_key)

        info = self.getinfo(path)
        if not info.is_dir:
            raise errors.DirectoryExpected(path)

        paginator = self.client.get_paginator("list_objects")
        _paginate = paginator.paginate(
            Bucket=self._bucket_name, Prefix=_oss_key, Delimiter=self.delimiter
        )

        def gen_info():
            for result in _paginate:
                common_prefixes = result.get("CommonPrefixes", ())
                for prefix in common_prefixes:
                    _prefix = prefix.get("Prefix")
                    _name = _prefix[prefix_len:]
                    if _name:
                        info = {
                            "basic": {
                                "name": _name.rstrip(self.delimiter),
                                "is_dir": True,
                            }
                        }
                        yield Info(info)
                for _obj in result.get("Contents", ()):
                    name = _obj["Key"][prefix_len:]
                    if name:
                        with osserrors(path):
                            obj = self.oss.Object(self._bucket_name, _obj["Key"])
                        info = self._info_from_object(obj, namespaces)
                        yield Info(info)

        iter_info = iter(gen_info())
        if page is not None:
            start, end = page
            iter_info = itertools.islice(iter_info, start, end)

        for info in iter_info:
            yield info

    def writebytes(self, path, contents):
        if not isinstance(contents, bytes):
            raise TypeError("contents must be bytes")

        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        if self.strict:
            if not self.isdir(dirname(path)):
                raise errors.ResourceNotFound(path)
            try:
                info = self._getinfo(path)
                if info.is_dir:
                    raise errors.FileExpected(path)
            except errors.ResourceNotFound:
                pass

        bytes_file = io.BytesIO(contents)
        with osserrors(path):
            self.client.upload_fileobj(
                bytes_file,
                self._bucket_name,
                _key,
                ExtraArgs=self._get_upload_args(_key),
            )

    def upload(self, path, file, chunk_size=None, **options):
        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        if self.strict:
            if not self.isdir(dirname(path)):
                raise errors.ResourceNotFound(path)
            try:
                info = self._getinfo(path)
                if info.is_dir:
                    raise errors.FileExpected(path)
            except errors.ResourceNotFound:
                pass

        with osserrors(path):
            self.client.upload_fileobj(
                file, self._bucket_name, _key, ExtraArgs=self._get_upload_args(_key)
            )

    def copy(self, src_path, dst_path, overwrite=False):
        if not overwrite and self.exists(dst_path):
            raise errors.DestinationExists(dst_path)

        _src_path = self.validatepath(src_path)
        _dst_path = self.validatepath(dst_path)

        if self.strict:
            if not self.isdir(dirname(_dst_path)):
                raise errors.ResourceNotFound(dst_path)

        _src_key = self._path_to_key(_src_path)
        _dst_key = self._path_to_key(_dst_path)

        try:
            with osserrors(src_path):
                self.client.copy_object(
                    Bucket=self._bucket_name,
                    Key=_dst_key,
                    CopySource={"Bucket": self._bucket_name, "Key": _src_key},
                )
        except errors.ResourceNotFound:
            if self.exists(src_path):
                raise errors.FileExpected(src_path)
            raise

    def move(self, src_path, dst_path, overwrite=False):
        self.copy(src_path, dst_path, overwrite=overwrite)
        self.remove(src_path)

    def geturl(self, path, purpose="download"):
        _path = self.validatepath(path)
        _key = self._path_to_key(_path)

        if _path == "/":
            raise errors.NoURL(path, purpose)
        if purpose == "download":
            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._bucket_name, "Key": _key},
            )
            # Both are okay, AWS and OSS.
            # url = url.replace('AWS', 'OSS')
            return url
        else:
            raise errors.NoURL(path, purpose)
