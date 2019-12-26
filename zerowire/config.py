from __future__ import annotations
from typing import (
    Any,
    List,
    Dict,
    Optional,
    TextIO,
    Iterator,
    get_type_hints,
)
from dataclasses import dataclass
from abc import abstractmethod
import socket
import ipaddress
from typeguard import check_type
import yaml
from pyroute2 import IPDB
from .types import TIfaceAddress, TNetwork
from .wg import WGProc
from .classlogger import ClassLogger

HOSTNAME = socket.gethostname()
with open('/etc/machine-id', 'rb') as f:
    MACHINE_ID = f.read().decode('utf-8').strip()

TFromDict = Dict[str, Any]


class ConfigBase:
    @classmethod
    @abstractmethod
    def from_dict(Cls, from_dict: TFromDict) -> ConfigBase:
        pass


@dataclass
class ServiceHandlerConfig(ConfigBase):
    type: str
    script: str

    @classmethod
    def from_dict(Cls, from_dict: TFromDict) -> ServiceHandlerConfig:
        hints = get_type_hints(ServiceHandlerConfig)
        for key, hint in hints.items():
            value = from_dict.get(key)
            check_type(f'ServiceHandlerConfig.{key}', value, hint)
        return ServiceHandlerConfig(**from_dict)

@dataclass
class ServiceConfig(ConfigBase):
    type: str
    name: str
    port: int
    properties: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(Cls, from_dict: TFromDict) -> ServiceConfig:
        hints = get_type_hints(ServiceConfig)
        for key, hint in hints.items():
            value = from_dict.get(key)
            check_type(f'ServiceConfig.{key}', value, hint)
        return ServiceConfig(**from_dict)


@dataclass
class IfaceConfig(ConfigBase, ClassLogger):
    name: str
    addr: TIfaceAddress
    privkey: str
    pubkey: str
    psk: str
    port: Optional[int] = None
    services: Optional[List[ServiceConfig]] = None

    @classmethod
    def from_dict(Cls, from_dict: TFromDict) -> IfaceConfig:
        hints = get_type_hints(IfaceConfig)
        check_type('IfaceConfig.addr', from_dict['addr'], str)
        from_dict['addr'] = ipaddress.ip_interface(from_dict['addr'])
        if 'services' in from_dict:
            services = from_dict['services']
            if isinstance(services, list):
                for i, service in enumerate(services):
                    services[i] = ServiceConfig.from_dict(service)
        for key, hint in hints.items():
            value = from_dict.get(key)
            check_type(f'IfaceConfig.{key}', value, hint)
        return IfaceConfig(**from_dict)

    @property
    def prefix(self) -> TNetwork:
        return self.addr.network

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
        if self.port is None:
            port = int(WGProc('show', self.name, 'dump').run().split('\t')[2])
            self.logger.info('Dynamic port %d', port)
            self.port = port


@dataclass
class Config(ConfigBase):
    interfaces: Dict[str, IfaceConfig]
    service_handlers: Dict[str, ServiceHandlerConfig]

    @classmethod
    def load(Cls, file: TextIO) -> Config:
        config = yaml.safe_load(file.read())
        return Cls.from_dict(config)

    @classmethod
    def from_dict(Cls, from_dict: TFromDict) -> Config:
        interfaces = {}
        service_handlers = {}
        for iface_name, iface_dict in from_dict.get('interfaces', {}).items():
            iface_name = f'wg-{iface_name}'
            iface_dict['name'] = iface_name
            interfaces[iface_name] = IfaceConfig.from_dict(iface_dict)
        for svc_type, svc_dict in from_dict.get('service_handlers', {}).items():
            if not svc_type.endswith('.'):
                svc_type += '.'
            svc_dict['type'] = svc_type
            service_handlers[svc_type] = ServiceHandlerConfig.from_dict(svc_dict)
        return Cls(interfaces, service_handlers)

    def __getitem__(self, key: str) -> IfaceConfig:
        return self.interfaces[key]

    def __iter__(self) -> Iterator[str]:
        return self.interfaces.__iter__()

    def __len__(self) -> int:
        return self.interfaces.__len__()
