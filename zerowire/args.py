'''
Usage:
  zerowire [options]

Options:
  -h --help                      Show this help.
  --version                      Show version.
  -c <config> --config=<config>  Set config location. [default: /etc/security/zerowire.conf].
  -l <level> --level=<level>     Set logging level. [default: info].
'''
from __future__ import annotations
from typing import (
    TextIO,
)
import logging
from enum import IntEnum
from dataclasses import dataclass
from docopt import docopt
from . import __version__

VERSION = f'ZeroWire Zeroconf WireGuard v{__version__}'
__doc__ = f'{VERSION}\n{__doc__}'


class LogLevels(IntEnum):
    critical = logging.CRITICAL
    error = logging.ERROR
    warning = logging.WARNING
    info = logging.INFO
    debug = logging.DEBUG


@dataclass(frozen=True)
class Args:
    config: TextIO
    help: bool
    version: bool
    level: LogLevels

    @classmethod
    def from_docopt(Cls) -> Args:
        args = docopt(__doc__, version=VERSION)
        return Cls(
            open(args['--config']),
            args['--help'],
            args['--version'],
            LogLevels[args['--level']],
        )
