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
from typing_extensions import TypedDict
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

from .config import Config, MACHINE_ID
from .wgzero import WGInterface, IFACE, PORT
from .wg import wg_proc

FORMAT = '[%(levelname)s] %(message)s'

logger = logging.getLogger(__name__)

class LogLevels(IntEnum):
    critical = logging.CRITICAL
    error = logging.ERROR
    warning = logging.WARNING
    info = logging.INFO
    debug = logging.DEBUG

class Args(NamedTuple):
    config: TextIO
    help: bool
    version: bool
    level: LogLevels

    @staticmethod
    def new(config: str, help: bool, version: bool, level: str) -> Args:
        return Args(
            config=open(config),
            help=help,
            version=version,
            level=LogLevels[level],
        )


@no_type_check
def create_iface(config: Config):
    with IPDB() as ipdb:
        if IFACE in ipdb.interfaces:
            ipdb.interfaces[IFACE].remove().commit()

        with ipdb.create(kind='wireguard', ifname=IFACE) as i:
            i.add_ip(f'{config.my_address()}/{config.my_prefix().prefixlen}')
            i.up()
            IFACE_index = i.index


def main() -> None:
    args: Args = Args.new(**{ key[2:]: value for key, value in docopt(__doc__).items()})

    logging.basicConfig(format=FORMAT, level=args.level)
    config: Config = Config.load(args.config)

    logger.debug('Config %s', config.__dict__)

    logger.info('My Address %s, my prefix %s', config.my_address(), config.my_prefix())

    IFACE_index = None

    create_iface(config)

    # wg.set_interface(IFACE, config.privkey, PORT, replace_peers=True)
    wg_proc(['set', IFACE, 'listen-port', str(PORT), 'private-key', '/dev/stdin'], input=config.privkey)

    interfaces = [
        WGInterface(name, config)
        for name in netifaces.interfaces()
        if name != 'lo' and not name.startswith('wg')
    ]

    try:
        input("Press enter to exit...\n\n")
    finally:
        for iface in interfaces:
            iface.close()

if __name__.endswith("__main__"):
    main()
