#!/usr/bin/env python3

from distutils.core import setup
from zerowire import (
    __version__,
    __author__,
    __authoremail__,
    __url__,
    __license__,
    __description__,
)

with open('README.md') as f:
    long_description = f.read()

setup(
    name='ZeroWire',
    version=__version__,
    description=__description__,
    long_description=long_description,
    author=__author__,
    author_email=__authoremail__,
    url=__url__,
    license=__license__,
    packages=['zerowire'],
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
