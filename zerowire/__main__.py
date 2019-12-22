#!/usr/bin/env python3
from __future__ import annotations
from typing import (
    List,
    TextIO,
)

import sys
import logging
from time import sleep

from pyroute2 import IPDB
import netifaces

import asyncio

from .args import Args
from .config import Config
from .wgzero import WGInterface
from .wg import WGProc
from .dns import SimpleDNSServer

FORMAT = '[%(levelname)s] %(message)s'

logger = logging.getLogger(__name__)

def main() -> None:
    args = Args.from_docopt()

    logging.basicConfig(format=FORMAT, level=args.level)
    config: Config = Config.load(args.config)
    logger.debug('Config %s', config.__dict__)

    dns = SimpleDNSServer('127.122.119.53', 53)

    interfaces: List[WGInterface] = []

    for wg_ifname in config:
        wg_ifconfig = config[wg_ifname]
        logger.info('Setting up %s', wg_ifname)
        logger.info('My Address %s, my prefix %s', wg_ifconfig.addr, wg_ifconfig.prefix)

        wg_ifconfig.configure()
        logger.info('Interfaces %r', netifaces.interfaces())
        interfaces.extend(
            WGInterface(name, config, wg_ifname, dns)
            for name in netifaces.interfaces()
            if name != 'lo' and not name.startswith('wg')
        )
    loop = asyncio.get_event_loop()
    transport, _ = loop.run_until_complete(dns.start())
    try:
        loop.run_forever()
    finally:
        for wgiface in interfaces:
            wgiface.close()

if __name__.endswith("__main__"):
    main()
