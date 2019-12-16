from __future__ import annotations
from typing import (
    Any,
    Type,
    List,
    Dict,
    Optional,
    Union,
    TextIO
)

import yaml
import random
import socket
import subprocess
import ipaddress
from zeroconf import Zeroconf, ServiceInfo
from .wg import wg_proc
from .types import TAddress

DEFAULT_CONF = '/etc/security/zerowire.conf'

MACHINE_ID: str = ''
HOSTNAME = socket.gethostname()


with open('/etc/machine-id', 'rb') as f:
    MACHINE_ID = f.read().decode('utf-8').strip()


class ServiceConfig:
    def __init__(self, config: Config, type: str, name: str, port: int, address: TAddress, properties: Optional[Dict[str, str]] = None):
        self.config = config
        self.type = type
        self.name = name
        self.port = port
        self.properties = properties or {}

        self.serviceinfo = ServiceInfo(
            type,
            f"{name}.{MACHINE_ID}.{type}",
            port=port,
            addresses=[address.packed],
            properties={
                b'hostname': HOSTNAME.encode('utf-8'),
                b'pubkey': self.config.pubkey.encode('utf-8'),
                b'addr': self.config.my_address().compressed.encode('utf-8')
            })

    @staticmethod
    def encode_props() -> None:
        pass


class Config:
    prefix: str
    addr: str
    subnet: str
    privkey: str
    pubkey: str
    psk: str
    services: List[ServiceConfig]

    def __init__(
        self,
        prefix: Optional[str] = None,
        addr: Optional[str] = None,
        subnet: Optional[str] = None,
        privkey: Optional[str] = None,
        pubkey: Optional[str] = None,
        psk: Optional[str] = None,
        port: Optional[int] = None,
        services: Optional[List[Any]] = None,
    ):
        self.__dirty = False
        self.prefix = prefix or self.__default_prefix()
        self.addr = addr or self.__default_addr()
        self.subnet = subnet or '0000'
        self.privkey = privkey or self.__default_privkey()
        self.pubkey = pubkey or self.__default_pubkey()
        self.psk = psk or self.__default_psk()
        self.port = port
        self.services = []
        if services is not None:
            for service in services:
                service['address'] = self.my_address
                self.services.append(ServiceConfig(**service))
        print (self.__dict__)

    @classmethod
    def load(Cls: Type[Config], file: TextIO) -> Config:
        config = yaml.safe_load(file.read())
        if isinstance(config, dict):
            return Cls(**config)
        return Cls()

    def my_address(self) -> ipaddress.IPv6Address:
        raw_address = self.raw_address()
        return ipaddress.IPv6Address(':'.join(
            raw_address[i:i + 4]
            for i in range(0, len(raw_address), 4)
        ))

    def my_prefix(self) -> ipaddress.IPv6Network:
        return ipaddress.IPv6Network(self.my_address().compressed + '/64', False)

    def raw_address(self) -> str:
        return 'fd' + self.prefix + self.subnet + self.addr

    def __default_prefix(self) -> str:
        self.__dirty = True
        return ''.join(
            f'{random.randint(0, 255):02x}'
            for _ in range(5)
        )

    def __default_addr(self) -> str:
        self.__dirty = True
        return MACHINE_ID[16:]

    def __default_privkey(self) -> str:
        self.__dirty = True
        out: str = wg_proc(['genkey'])
        return out

    def __default_pubkey(self) -> str:
        self.__dirty = True
        out: str = wg_proc(['pubkey'], input=self.privkey)
        return out

    def __default_psk(self) -> str:
        self.__dirty = True
        out: str = wg_proc(['genpsk'])
        return out
