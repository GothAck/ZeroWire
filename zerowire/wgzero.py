from __future__ import annotations
from typing import (
    Callable,
    List,
    Dict,
    Union,
    Optional,
    TypeVar,
)
import os
import socket
import base64
import netifaces
import ipaddress
from threading import Lock
import logging

from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo, ServiceListener
from pyroute2 import IPRoute
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from .config import Config, IfaceConfig, MACHINE_ID, HOSTNAME
from .wg import wg_proc
from .types import TAddress
from .dns import SimpleDNSServer

logger = logging.getLogger(__name__)

WG_TYPE = "_wireguard._udp.local."

assert socket.AF_INET == netifaces.AF_INET
assert socket.AF_INET6 == netifaces.AF_INET6

class WGServiceInfo(ServiceInfo):
    salt: bytes
    auth: bytes

    @classmethod
    def new(Cls, machineid: str, addresses: List[bytes], hostname: str, config: IfaceConfig) -> WGServiceInfo:
        salt = base64.b64encode(os.urandom(32))

        dnshost = f'{machineid}.{WG_TYPE}'
        logger.debug('dnshost %s', dnshost)
        addr = config.addr.ip.compressed.encode('utf-8')
        port = config.port
        hostnameenc = hostname.encode('utf-8')
        pubkey = config.pubkey.encode('utf-8')
        psk = config.psk.encode('utf-8')
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(dnshost.encode('utf-8'))
        digest.update(str(port).encode('utf-8'))
        # print(addresses)
        # for address in addresses:
        #     digest.update(address)
        digest.update(addr)
        digest.update(hostnameenc)
        digest.update(pubkey)
        digest.update(salt)
        digest.update(psk)
        auth = base64.b64encode(digest.finalize())
        self = Cls(
            WG_TYPE,
            dnshost,
            port=port,
            addresses=addresses,
            properties={
                'addr': addr,
                'hostname': hostnameenc,
                'pubkey': pubkey,
                'salt': salt,
                'auth': auth,
            }
        )

        self.salt = salt
        self.auth = auth
        return self

    @staticmethod
    def authenticate(info: ServiceInfo, psk: str) -> bool:
        props: Dict[bytes, bytes] = info.properties
        addr = props.get(b'addr', b'')
        hostname = props.get(b'hostname', b'')
        pubkey = props.get(b'pubkey', b'')
        salt = props.get(b'salt', b'')
        auth = props.get(b'auth', b'')
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())

        digest.update(info.name.encode('utf-8'))
        digest.update(str(info.port).encode('utf-8'))
        # print(info.addresses)
        # for address in info.addresses:
        #     digest.update(address)
        digest.update(addr)
        digest.update(hostname)
        digest.update(pubkey)
        digest.update(salt)
        digest.update(psk.encode('utf-8'))
        res = base64.b64encode(digest.finalize())
        return res == auth



class WGInterface:
    def __init__(self, ifname: str, config: Config, wg_ifname: str, dns: SimpleDNSServer):
        logging.info('Setting up WGInterface phys %s wg_if %s', ifname, wg_ifname)
        self.ifname = ifname
        self.wg_ifname = wg_ifname
        self.dns = dns
        self.wg_ifconfig = config[wg_ifname]
        self.ifindex: int = IPRoute().link_lookup(ifname=ifname)[0]
        self.wg_ifindex: int = IPRoute().link_lookup(ifname=wg_ifname)[0]
        self.config = config
        self.listener = WGServiceListener(self)
        self.addresses = self.get_addrs()
        self.zeroconf = Zeroconf([addr.compressed for addr in self.addresses])

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(MACHINE_ID.encode('utf-8'))
        digest.update(ifname.encode('utf-8'))

        self.service: WGServiceInfo = WGServiceInfo.new(
            digest.finalize()[:16].hex(),
            addresses=[addr.packed for addr in self.addresses],
            hostname=HOSTNAME,
            config=self.wg_ifconfig,
        )
        dns.add_to_resolved(self)

    def close(self) -> None:
        if getattr(self, '_zeroconf', None) is not None:
            self._zeroconf.close()

    def get_addrs(self) -> List[Union[ipaddress.IPv6Address, ipaddress.IPv4Address]]:
        addrs = netifaces.ifaddresses(self.ifname)
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


class WGServiceListener(ServiceListener):
    peers: Dict[str, TAddress]
    def __init__(self, iface: WGInterface):
        self.iface = iface
        self.my_address = iface.wg_ifconfig.addr
        self.my_prefix = iface.wg_ifconfig.prefix
        self.pubkey = iface.wg_ifconfig.pubkey
        self.psk = iface.wg_ifconfig.psk
        self.peers = {}
        self.lock = Lock()

    def remove_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        with self.lock:
            print("Service %s removed" % (name,))

    def update_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        pass

    def add_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        with self.lock:
            info = zeroconf.get_service_info(type, name)
            logger.debug('WGServiceListener add_service %s %s %r', type, name, info)
            if not info: return
            if not WGServiceInfo.authenticate(info, self.psk):
                print('Failed to authenticate remote with psk hash')
                return
            props: Dict[bytes, bytes] = info.properties
            addrs: List[TAddress] = [ipaddress.ip_address(addr) for addr in info.addresses]
            _internal_addr = props.get(b'addr', b'').decode('utf-8')
            internal_addr: Optional[TAddress] = ipaddress.ip_interface(_internal_addr) if _internal_addr else None
            pubkey = props.get(b'pubkey', b'').decode('utf-8')
            hostname = props.get(b'hostname', b'').decode('utf-8')
            if not internal_addr or not pubkey:
                print('Service does not have requisite properties')
                return
            if internal_addr == self.my_address: return
            if not internal_addr.network.subnet_of(self.my_prefix): # type: ignore
                return
            print(f'Found remote. name "{name}" pubkey "{pubkey}" addrs {addrs} port {info.port}')
            if pubkey in self.peers: return
            # if self.peers.get(pubkey, None) == : return
            # if pubkey in self.iface.wg.get_interface(IFACE).peers: return
            for addr in addrs:
                addr = ipaddress.ip_address(addr)
                if addr.is_link_local: continue
                endpoint = f'[{addr.compressed}]' if addr.version == 6 else addr.compressed
                endpoint = f'{endpoint}:{info.port}'
                internal_addr_o = internal_addr.ip
                wg_proc(
                    [
                        'set', self.iface.wg_ifname,
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
                zw_hostname = hostname + '.zw.'
                self.iface.dns.add_record(
                    zw_hostname,
                    f'{zw_hostname} AAAA {internal_addr_o.compressed}')
