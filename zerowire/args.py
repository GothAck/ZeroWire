'''
ZeroWire Zeroconf WireGuard

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

    def __init__(self, config: str, help: bool, version: bool, level: str):
        object.__setattr__(self, 'config', open(config))
        object.__setattr__(self, 'help', help)
        object.__setattr__(self, 'version', version)
        object.__setattr__(self, 'level', LogLevels[level])

    @classmethod
    def from_docopt(Cls) -> Args:
        return Cls(**{
            key[2:]: value
            for key, value
            in docopt(__doc__).items()
        })
