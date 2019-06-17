from __future__ import unicode_literals

import unittest

from nose.plugins.attrib import attr

from fs.test import FSTestCases

from fs_ossfs import OSSFS

import boto3


class TestOSSFS(FSTestCases, unittest.TestCase):
    """Test OSSFS implementation from dir_path."""
    bucket_name = 'fsexample'
    oss = boto3.resource('s3')
    client = boto3.client('s3')

    def make_fs(self):
        self._delete_bucket_contents()
        return OSSFS(self.bucket_name)

    def _delete_bucket_contents(self):
        response = self.client.list_objects(
            Bucket=self.bucket_name
        )
        contents = response.get("Contents", ())
        for obj in contents:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=obj["Key"]
            )


@attr('slow')
class TestOSSFSSubDir(FSTestCases, unittest.TestCase):
    """Test OSSFS implementation from dir_path."""
    bucket_name = 'fsexample'
    oss = boto3.resource('s3')
    client = boto3.client('s3')

    def make_fs(self):
        self._delete_bucket_contents()
        self.oss.Object(self.bucket_name, 'subdirectory').put()
        return OSSFS(self.bucket_name, dir_path='subdirectory')

    def _delete_bucket_contents(self):
        response = self.client.list_objects(
            Bucket=self.bucket_name
        )
        contents = response.get("Contents", ())
        for obj in contents:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=obj["Key"]
            )


class TestOSSFSHelpers(unittest.TestCase):

    def test_path_to_key(self):
        oss = OSSFS('foo')
        self.assertEqual(oss._path_to_key('foo.bar'), 'foo.bar')
        self.assertEqual(oss._path_to_key('foo/bar'), 'foo/bar')

    def test_path_to_key_subdir(self):
        oss = OSSFS('foo', '/dir')
        self.assertEqual(oss._path_to_key('foo.bar'), 'dir/foo.bar')
        self.assertEqual(oss._path_to_key('foo/bar'), 'dir/foo/bar')

    def test_upload_args(self):
        oss = OSSFS('foo', acl='acl', cache_control='cc')
        self.assertDictEqual(oss._get_upload_args('test.jpg'),
                             {'ACL': 'acl', 'CacheControl': 'cc', 'ContentType': 'image/jpeg'})
        self.assertDictEqual(oss._get_upload_args('test.mp3'),
                             {'ACL': 'acl', 'CacheControl': 'cc', 'ContentType': 'audio/mpeg'})
        self.assertDictEqual(oss._get_upload_args('test.json'),
                             {'ACL': 'acl', 'CacheControl': 'cc', 'ContentType': 'application/json'})
        self.assertDictEqual(oss._get_upload_args('unknown.unknown'),
                             {'ACL': 'acl', 'CacheControl': 'cc', 'ContentType': 'binary/octet-stream'})
