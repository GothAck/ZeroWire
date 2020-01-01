#!/usr/bin/env python3
from zerowire import (
    __version__,
    __author__,
    __authoremail__,
    __description__,
)

import re

linestart = re.compile(r'^', re.M)

with open('README.md', 'r') as f:
    readme = f.read()


print(f'''
Package: zerowire
Version: {__version__}
Section: base
Priority: optional
Architecture: all
Depends: python3, python3-dbus
Maintainer: {__author__} <{__authoremail__}>
Description: {__description__}
''')
