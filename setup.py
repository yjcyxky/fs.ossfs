#!/usr/bin/env python

from setuptools import setup, find_packages

with open("fs_ossfs/version.py") as f:
    __version__ = None
    exec(f.read())

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3.3",
    "Programming Language :: Python :: 3.4",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Topic :: System :: Filesystems",
]

with open("README.rst", "rt") as f:
    DESCRIPTION = f.read()

REQUIREMENTS = ["boto3~=1.7", "awscli~=1.16.144", "fs~=2.2", "six~=1.10"]

setup(
    name="fs-ossfs",
    author="Jingcheng Yang",
    author_email="yjcyxky@163.com",
    classifiers=CLASSIFIERS,
    description="AliCloud OSS filesystem for PyFilesystem2",
    install_requires=REQUIREMENTS,
    license="MIT",
    long_description=DESCRIPTION,
    packages=find_packages(),
    keywords=["pyfilesystem", "AliCloud", "oss"],
    platforms=["any"],
    test_suite="nose.collector",
    url="http://choppy.3steps.cn/go-choppy/ossfs",
    version=__version__,
    entry_points={
        "fs.opener": ["oss = fs_ossfs.opener:OSSFSOpener"]
    },
)
