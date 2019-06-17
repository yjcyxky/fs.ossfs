# -*- coding: utf-8 -*-
"""
    fs_ossfs.opener
    ~~~~~~~~~~~~~~~

    Defines the OSSFSpener.

    :copyright: © 2019 by the Choppy team.
    :license: AGPL, see LICENSE.md for more details.
"""

# Python Future
from __future__ import absolute_import, print_function, unicode_literals

# Third Party
from fs.opener import Opener
from fs.opener.errors import OpenerError

# Local Folder
from .ossfs import OSSFS

__all__ = ['OSSFSOpener']


class OSSFSOpener(Opener):
    protocols = ['oss']

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        bucket_name, _, dir_path = parse_result.resource.partition('/')
        if not bucket_name:
            raise OpenerError(
                "invalid bucket name in '{}'".format(fs_url)
            )
        strict = (
            parse_result.params['strict'] == '1'
            if 'strict' in parse_result.params
            else True
        )
        ossfs = OSSFS(
            bucket_name,
            dir_path=dir_path or '/',
            oss_access_key_id=parse_result.username or None,
            oss_secret_access_key=parse_result.password or None,
            endpoint_url=parse_result.params.get('endpoint_url', None),
            acl=parse_result.params.get('acl', None),
            cache_control=parse_result.params.get('cache_control', None),
            strict=strict
        )
        return ossfs
