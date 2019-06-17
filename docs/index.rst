.. OSSFS documentation master file, created by sphinx-quickstart.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

OSSFS
=====

OSSFS is a `PyFilesystem interface
<https://docs.pyfilesystem.org/en/latest/reference/base.html>`_ to
AliCloud OSS cloud storage.

As a PyFilesystem concrete class, OSSFS allows you to work with OSS in the
same as any other supported filesystem.

Installing
==========

OSSFS may be installed from pip with the following command::

    pip install fs-ossfs

This will install the most recent stable version.

Alternatively, if you want the cutting edge code, you can check out
the GitHub repos at https://github.com/go-choppy/fs.ossfs


Opening an OSS Filesystem
=========================

There are two options for constructing a ossfs instance. The simplest way
is with an *opener*, which is a simple URL like syntax. Here is an example::

    from fs import open_fs
    ossfs = open_fs('oss://mybucket/')

For more granular control, you may import the OSSFS class and construct
it explicitly::

    from fs_ossfs import OSSFS
    ossfs = OSSFS('mybucket')

OSSFS Constructor
-----------------

.. autoclass:: fs_ossfs.OSSFS
    :members:


Limitations
===========

AliCloud OSS isn't strictly speaking a *filesystem*, in that it contains
files, but doesn't offer true *directories*. OSSFS follows the convention
of simulating directories by creating an object that ends in a forward
slash. For instance, if you create a file called `"foo/bar"`, OSSFS will
create an OSS object for the file called `"foo/bar"` *and* an
empty object called `"foo/"` which stores that fact that the `"foo"`
directory exists.

If you create all your files and directories with OSSFS, then you can
forget about how things are stored under the hood. Everything will work
as you expect. You *may* run in to problems if your data has been
uploaded without the use of OSSFS. For instance, if you create a
`"foo/bar"` object without a `"foo/"` object. If this occurs, then OSSFS
may give errors about directories not existing, where you would expect
them to be. The solution is to create an empty object for all
directories and subdirectories. Fortunately most tools will do this for
you, and it is probably only required of you upload your files manually.


Authentication
==============

If you don't supply any credentials, then OSSFS will use the access key
and secret key configured on your system. You may also specify when
creating the filesystem instance. Here's how you would do that with an
opener::

    ossfs = open_fs('oss://<access key>:<secret key>@mybucket')

Here's how you specify credentials with the constructor::

    ossfs = OSSFS(
        'mybucket'
        oss_access_key_id=<access key>,
        oss_secret_access_key=<secret key>
    )

.. note::

    AliCloud recommends against specifying credentials explicitly like
    this in production.


OSS Info
========

You can retrieve OSS info via the ``oss`` namespace. Here's an example:

    >>> info = s.getinfo('foo', namespaces=['oss'])
    >>> info.raw['oss']
    {'metadata': {}, 'delete_marker': None, 'version_id': None, 'parts_count': None, 'accept_ranges': 'bytes', 'last_modified': 1501935315, 'content_length': 3, 'content_encoding': None, 'request_charged': None, 'replication_status': None, 'server_side_encryption': None, 'expires': None, 'restore': None, 'content_type': 'binary/octet-stream', 'sse_customer_key_md5': None, 'content_disposition': None, 'storage_class': None, 'expiration': None, 'missing_meta': None, 'content_language': None, 'ssekms_key_id': None, 'sse_customer_algorithm': None, 'e_tag': '"37b51d194a7513e45b56f6524f2d51f2"', 'website_redirect_location': None, 'cache_control': None}


URLs
====

You can use the ``geturl`` method to generate an externally accessible
URL from an OSS object. Here's an example:

>>> ossfs.geturl('foo')



More Information
================

See the `PyFilesystem Docs <https://docs.pyfilesystem.org>`_ for documentation on the rest of the PyFilesystem interface.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
