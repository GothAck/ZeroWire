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
    Dict,
    TextIO,
    NamedTuple,
    no_type_check,
)
from dataclasses import dataclass
from typeguard import check_type
from enum import IntEnum
import sys
import os
import socket
import ipaddress
from base64 import b64encode
import logging

from docopt import docopt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pyroute2 import IPDB
import netifaces
import yaml
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo

from .config import Config, IfaceConfig, MACHINE_ID
from .wgzero import WGInterface
from .wg import wg_proc, WGProc

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


# @no_type_check
def create_iface(name: str, config: Config) -> None:
    with IPDB() as ipdb:
        if name in ipdb.interfaces:
            ipdb.interfaces[name].remove().commit()
        with ipdb.create(kind='wireguard', ifname=name) as i:
            addr = config[name].addr
            i.add_ip(f'{addr}')
            i.up()


def main() -> None:
    args: Args = Args(**{ key[2:]: value for key, value in docopt(__doc__).items()})

    logging.basicConfig(format=FORMAT, level=args.level)
    config: Config = Config.load(args.config)
    logger.debug('Config %s', config.__dict__)

    interfaces: List[WGInterface] = []

    for wg_ifname in config:
        wg_ifconfig = config[wg_ifname]
        logger.info('My Address %s, my prefix %s', wg_ifconfig.addr, wg_ifconfig.prefix)

        # IFACE_index = None

        create_iface(wg_ifname, config)

        # wg.set_interface(IFACE, config.privkey, PORT, replace_peers=True)
        port = wg_ifconfig.port
        (WGProc('set', wg_ifname)
            .args(
                ['listen-port', str(port)] if isinstance(port, int) else [],
                'private-key', '/dev/stdin'
            )
            .input(wg_ifconfig.privkey)
            .run())
        interfaces.extend(
            WGInterface(name, config, wg_ifname)
            for name in netifaces.interfaces()
            if name != 'lo' and not name.startswith('wg')
        )

    try:
        input("Press enter to exit...\n\n")
    finally:
        for wgiface in interfaces:
            wgiface.close()

if __name__.endswith("__main__"):
    main()
