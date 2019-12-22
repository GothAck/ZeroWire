#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    List,
    TextIO,
)
import logging
from time import sleep

from pyroute2 import IPDB
import netifaces

from .args import Args
from .config import Config
from .wgzero import WGInterface
from .wg import WGProc

FORMAT = '[%(levelname)s] %(message)s'

logger = logging.getLogger(__name__)

def main() -> None:
    args = Args.from_docopt()

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
