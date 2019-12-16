from __future__ import annotations
from typing import (
    Any,
    Callable,
    List,
    Dict,
    Union,
    Optional,
    TypeVar,
)
import typing
import os
import socket
import base64
import netifaces
import ipaddress
from threading import Lock
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
from pyroute2 import IPRoute
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from .config import Config, MACHINE_ID, HOSTNAME
from .wg import wg_proc
from .types import TAddress

WG_TYPE = "_wireguard._udp.local."

IFACE = 'wg-zero'
PORT = 12345

assert socket.AF_INET == netifaces.AF_INET
assert socket.AF_INET6 == netifaces.AF_INET6

class WGServiceInfo(ServiceInfo):
    salt: bytes
    auth: bytes

    @classmethod
    def new(Cls, machineid: str, addresses: List[bytes], hostname: str, config: Config) -> WGServiceInfo:
        salt = base64.b64encode(os.urandom(32))

        dnshost = f'{machineid}.{WG_TYPE}'
        addr = config.my_address().compressed.encode('utf-8')
        hostnameenc = hostname.encode('utf-8')
        pubkey = config.pubkey.encode('utf-8')
        psk = config.psk.encode('utf-8')
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(addr)
        digest.update(hostnameenc)
        digest.update(pubkey)
        digest.update(salt)
        digest.update(psk)
        auth = base64.b64encode(digest.finalize())
        self = Cls(
            WG_TYPE,
            dnshost,
            port=config.port or PORT,
            addresses=addresses,
            properties={
                'addr': config.my_address().compressed.encode('utf-8'),
                'hostname': hostnameenc,
                'pubkey': config.pubkey,
                'salt': salt,
                'auth': auth,
            }
        )

        self.salt = salt
        self.auth = auth
        return self

    @staticmethod
    def authenticate(info: ServiceInfo, psk: str) -> bool:
        props: Dict[bytes, bytes] = info.properties # type: ignore
        addr = props.get(b'addr', b'')
        hostname = props.get(b'hostname', b'')
        pubkey = props.get(b'pubkey', b'')
        salt = props.get(b'salt', b'')
        auth = props.get(b'auth', b'')
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(addr)
        digest.update(hostname)
        digest.update(pubkey)
        digest.update(salt)
        digest.update(psk.encode('utf-8'))
        res = base64.b64encode(digest.finalize())
        return res == auth



class WGInterface:
    def __init__(self, name: str, config: Config):
        self.name = name
        self.ifindex: int = IPRoute().link_lookup(ifname=name)[0]
        self.config = config
        self.listener = ServiceListener(self, config)
        self.addresses = self.get_addrs()
        self.zeroconf = Zeroconf([addr.compressed for addr in self.addresses])
        self.service: WGServiceInfo = WGServiceInfo.new(
            MACHINE_ID,
            addresses=[addr.packed for addr in self.addresses],
            hostname=HOSTNAME,
            config=config,
        )

    def close(self) -> None:
        if getattr(self, '_zeroconf', None) is not None:
            self._zeroconf.close()

    def get_addrs(self) -> List[Union[ipaddress.IPv6Address, ipaddress.IPv4Address]]:
        addrs = netifaces.ifaddresses(self.name)
        return [
            ipaddress.ip_address(addr['addr'].split('%', 2)[0])
            for type in (socket.AF_INET, socket.AF_INET6)
            for addr in addrs.get(type, [])
        ]

    @property
    def service(self) -> ServiceInfo:
        val: Optional[ServiceInfo] = getattr(self, '_service', None)
        if val is None: raise Exception('Service not initialized')
        return val

    @service.setter
    def service(self, value: ServiceInfo) -> None:
        if getattr(self, '_service', None):
            if getattr(self, '_zeroconf', None):
                pass
                ## TODO: unregister service
        self._service = value
        if getattr(self, '_zeroconf', None):
            self._zeroconf.register_service(value)

    @property
    def zeroconf(self) -> Zeroconf:
        val: Optional[Zeroconf] = getattr(self, '_zeroconf', None)
        if val is None: raise Exception('Service not initialized')
        return val
    @zeroconf.setter
    def zeroconf(self, value: Zeroconf) -> None:
        self._zeroconf = value
        self._browser = ServiceBrowser(value, WG_TYPE, self.listener)


TRet = TypeVar('TRet')
TFunc = TypeVar('TFunc', bound=Callable[..., TRet])


class ServiceListener:
    peers: Dict[str, TAddress]
    def __init__(self, iface: WGInterface, config: Config):
        self.iface = iface
        self.my_address = config.my_address()
        self.my_prefix = config.my_prefix()
        self.pubkey = config.pubkey
        self.psk = config.psk
        self.peers = {}
        self.lock = Lock()

    def remove_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        with self.lock:
            print("Service %s removed" % (name,))

    def add_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        with self.lock:
            info = zeroconf.get_service_info(type, name)
            if not info: return
            if not WGServiceInfo.authenticate(info, self.psk):
                print('Failed to authenticate remote with psk hash')
                return
            props: Dict[bytes, bytes] = info.properties # type: ignore
            addrs: List[TAddress] = [ipaddress.ip_address(addr) for addr in info.addresses]
            _internal_addr = props.get(b'addr', b'').decode('utf-8')
            internal_addr: Optional[TAddress] = ipaddress.ip_address(_internal_addr) if _internal_addr else None
            pubkey = props.get(b'pubkey', b'').decode('utf-8')
            if not internal_addr or not pubkey:
                print('Service does not have requisite properties')
                return
            if internal_addr == self.my_address: return
            if not ipaddress.ip_network(internal_addr).subnet_of(self.my_prefix): return
            print(f'Found remote. name "{name}" pubkey "{pubkey}" addrs {addrs} port {info.port}')
            if pubkey in self.peers: return
            # if self.peers.get(pubkey, None) == : return
            # if pubkey in self.iface.wg.get_interface(IFACE).peers: return
            for addr in addrs:
                addr = ipaddress.ip_address(addr)
                if addr.is_link_local: continue
                endpoint = f'[{addr.compressed}]' if addr.version == 6 else addr.compressed
                endpoint = f'{endpoint}:{info.port}'
                print(endpoint)
                internal_addr_o = ipaddress.ip_address(addr)
                wg_proc(
                    [
                        'set', IFACE,
                        'peer', pubkey,
                        'preshared-key', '/dev/stdin',
                        'endpoint', endpoint,
                        'persistent-keepalive', '5',
                        'allowed-ips',
                        ','.join([
                            internal_addr_o.compressed,
                            self.my_prefix.broadcast_address.compressed,
                        ])
                    ],
                    input=self.psk)

                # self.iface.wg.set_peer(interface=IFACE, public_key=pubkey, endpoint=endpoint, allowedips=[internal_addr])
                self.peers[pubkey] = addr
