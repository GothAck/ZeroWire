#!/usr/bin/env python3
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
    List,
    TextIO,
)
from dataclasses import dataclass
from enum import IntEnum
import logging
from time import sleep

from docopt import docopt
from pyroute2 import IPDB
import netifaces

from .config import Config
from .wgzero import WGInterface
from .wg import WGProc

FORMAT = '[%(levelname)s] %(message)s'

logger = logging.getLogger(__name__)

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


def main() -> None:
    args: Args = Args(**{ key[2:]: value for key, value in docopt(__doc__).items()})

    logging.basicConfig(format=FORMAT, level=args.level)
    config: Config = Config.load(args.config)
    logger.debug('Config %s', config.__dict__)

    interfaces: List[WGInterface] = []

    for wg_ifname in config:
        wg_ifconfig = config[wg_ifname]
        logger.info('My Address %s, my prefix %s', wg_ifconfig.addr, wg_ifconfig.prefix)

        wg_ifconfig.configure()

        interfaces.extend(
            WGInterface(name, config, wg_ifname)
            for name in netifaces.interfaces()
            if name != 'lo' and not name.startswith('wg')
        )
    try:
        while True: sleep(60)
    finally:
        for wgiface in interfaces:
            wgiface.close()

if __name__.endswith("__main__"):
    main()
