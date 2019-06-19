# OSSFS

OSSFS is a [PyFilesystem](https://www.pyfilesystem.org/) interface to
AliCloud OSS cloud storage.

As a PyFilesystem concrete class, [OSSFS](http://fs-ossfs.readthedocs.io/en/latest/) allows you to work with OSS in the
same way as any other supported filesystem.

## Installing

You can install OSSFS from pip as follows:

```
pip install fs-ossfs
```

## Opening a OSSFS

Open an OSSFS by explicitly using the constructor:

```python
from fs_ossfs import OSSFS
ossfs = OSSFS('mybucket')
```

Or with a FS URL:

```python
  from fs import open_fs
  ossfs = open_fs('oss://mybucket')
```

## Downloading Files

To _download_ files from an OSS bucket, open a file on the OSS
filesystem for reading, then write the data to a file on the local
filesystem. Here's an example that copies a file `example.mov` from
OSS to your HD:

```python
from fs.tools import copy_file_data
with ossfs.open('example.mov', 'rb') as remote_file:
    with open('example.mov', 'wb') as local_file:
        copy_file_data(remote_file, local_file)
```

Although it is preferable to use the higher-level functionality in the
`fs.copy` module. Here's an example:

```python
from fs.copy import copy_file
copy_file(ossfs, 'example.mov', './', 'example.mov')
```

## Uploading Files

You can _upload_ files in the same way. Simply copy a file from a
source filesystem to the OSS filesystem.
See [Moving and Copying](https://docs.pyfilesystem.org/en/latest/guide.html#moving-and-copying)
for more information.

## ExtraArgs

OSS objects have additional properties, beyond a traditional
filesystem. These options can be set using the `upload_args`
and `download_args` properties. which are handed to upload
and download methods, as appropriate, for the lifetime of the
filesystem instance.

For example, to set the `cache-control` header of all objects
uploaded to a bucket:

```python
import fs, fs.mirror
ossfs = OSSFS('example', upload_args={"CacheControl": "max-age=2592000", "ACL": "public-read"})
fs.mirror.mirror('/path/to/mirror', ossfs)
```

see [the Boto3 docs](https://boto3.readthedocs.io/en/latest/reference/customizations/s3.html#boto3.s3.transfer.S3Transfer.ALLOWED_UPLOAD_ARGS)
for more information.

`acl` and `cache_control` are exposed explicitly for convenience, and can be used in URLs.
It is important to URL-Escape the `cache_control` value in a URL, as it may contain special characters.

```python
import fs, fs.mirror
with open fs.open_fs('oss://example?acl=public-read&cache_control=max-age%3D2592000%2Cpublic') as ossfs
    fs.mirror.mirror('/path/to/mirror', ossfs)
```

## OSS URLs

You can get a public URL to a file on a OSS bucket as follows:

```python
movie_url = ossfs.geturl('example.mov')
```

## Documentation

- [PyFilesystem Wiki](https://www.pyfilesystem.org)
- [OSSFS Reference](http://fs-ossfs.readthedocs.io/en/latest/)
- [PyFilesystem Reference](https://docs.pyfilesystem.org/en/latest/reference/base.html)
