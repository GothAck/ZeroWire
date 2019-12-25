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
import ipaddress
import asyncio

from .args import Args
from .config import Config, HOSTNAME
from .wgzero import WGInterface
from .wg import WGProc
from .dns import LocalDNSServer

FORMAT = '[%(levelname)s] %(message)s'

logger = logging.getLogger(__name__)

async def main() -> None:
    args = Args.from_docopt()

    logging.basicConfig(format=FORMAT, level=args.level)
    config: Config = Config.load(args.config)
    logger.debug('Config %s', config.__dict__)

    dns = LocalDNSServer(ipaddress.ip_address('127.122.119.53'), 53)
    await dns.start()

    interfaces: List[WGInterface] = []

    for wg_ifname in config:
        wg_ifconfig = config[wg_ifname]
        logger.info('Setting up %s', wg_ifname)
        logger.info('My Address %s, my prefix %s', wg_ifconfig.addr, wg_ifconfig.prefix)

        wg_ifconfig.configure()
        logger.info('Interfaces %r', netifaces.interfaces())
        iface = WGInterface(wg_ifname, wg_ifconfig, dns)
        await iface.start()
        interfaces.append(iface)
    try:
        while True:
            await asyncio.sleep(60)
    finally:
        for wgiface in interfaces:
            wgiface.close()

if __name__.endswith("__main__"):
    asyncio.run(main())
