from __future__ import annotations
from typing import (
    Any,
    List,
    Dict,
    Tuple,
    Optional,
    TextIO,
    Iterator,
    get_type_hints,
)
from dataclasses import dataclass
from typeguard import check_type
import yaml
import socket
import ipaddress
import logging
from pyroute2 import IPDB
from .types import TAddress, TNetwork
from .wg import WGProc

logger = logging.getLogger(__name__)

HOSTNAME = socket.gethostname()
with open('/etc/machine-id', 'rb') as f:
    MACHINE_ID = f.read().decode('utf-8').strip()

@dataclass(frozen=True)
class ServiceConfig:
    type: str
    name: str
    port: int
    properties: Optional[Tuple[Tuple[str, str], ...]]


@dataclass(frozen=True)
class IfaceConfig:
    name: str
    addr: TAddress
    privkey: str
    pubkey: str
    psk: str
    port: Optional[int]
    services: Optional[List[ServiceConfig]] = None

    @property
    def prefix(self) -> TNetwork:
        return ipaddress.ip_network(self.addr, False) # type: ignore

    def configure(self) -> None:
        # Recreate iface
        with IPDB() as ipdb:
            if self.name in ipdb.interfaces:
                ipdb.interfaces[self.name].remove().commit()
            with ipdb.create(kind='wireguard', ifname=self.name) as i:
                i.add_ip(f'{self.addr}')
                i.up()

        (WGProc('set', self.name)
            .args(
                [] if self.port is None else ['listen-port', str(self.port)],
                'private-key', '/dev/stdin'
            )
            .input(self.privkey)
            .run())


@dataclass(init=False)
class Config:
    configs: Dict[str, IfaceConfig]
    def __init__(self, **kwargs: Dict[str, Any]):
        self.configs = {}
        for iface_name, iface_dict in kwargs.items():
            hints = get_type_hints(IfaceConfig)
            iface_dict['addr'] = ipaddress.ip_interface(iface_dict['addr'])
            for key, value in iface_dict.items():
                check_type(f'{iface_name}.{key}', value, hints[key])

            iface_name = f'wg-{iface_name}'
            iface_dict['name'] = iface_name
            self.configs[iface_name] = IfaceConfig(**iface_dict)

    @classmethod
    def load(Cls, file: TextIO) -> Config:
        config = yaml.safe_load(file.read())
        if isinstance(config, dict):
            return Cls(**config)
        return Cls()

    def __getitem__(self, key: str) -> IfaceConfig:
        return self.configs[key]

    def __iter__(self) -> Iterator[str]:
        return self.configs.__iter__()
