#!/usr/bin/env python3

from setuptools import setup
from zerowire import (
    __version__,
    __author__,
    __authoremail__,
    __url__,
    __license__,
    __description__,
)

setup(
    name='ZeroWire',
    version=__version__,
    description=__description__,
    long_description='file:README.md',
    author=__author__,
    author_email=__authoremail__,
    url=__url__,
    license=__license__,
    packages=['zerowire'],
    platforms=['linux'],
    scripts=['scripts/zerowire'],
    requires=[
        'typing_extensions',
        'zeroconf',
        'pyroute2',
        'typeguard',
        'pyyaml',
        'docopt',
        'dnslib',
        'dbus_python',
    ],
)
