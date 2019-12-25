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
from .types import TIfaceAddress
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


class WGZeroconf:
    def __init__(self, ifname: str, wg_iface: WGInterface):
        self.ifname = ifname
        self.ifindex: int = IPRoute().link_lookup(ifname=ifname)[0]
        self.wg_iface = wg_iface
        self.addresses = self.get_addrs()
        self.zeroconf = Zeroconf([addr.compressed for addr in self.addresses])
        self.listener = WGServiceListener(self)
        self.browser = ServiceBrowser(self.zeroconf, WG_TYPE, self.listener)

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(MACHINE_ID.encode('utf-8'))
        digest.update(ifname.encode('utf-8'))

        self.service: WGServiceInfo = WGServiceInfo.new(
            digest.finalize()[:16].hex(),
            addresses=[addr.packed for addr in self.addresses],
            hostname=HOSTNAME,
            config=wg_iface.config,
        )
        self.zeroconf.register_service(self.service)

    def get_addrs(self) -> List[Union[ipaddress.IPv6Address, ipaddress.IPv4Address]]:
        addrs = netifaces.ifaddresses(self.ifname)
        return [
            ipaddress.ip_address(addr['addr'].split('%', 2)[0])
            for type in (socket.AF_INET, socket.AF_INET6)
            for addr in addrs.get(type, [])
        ]

    def close(self) -> None:
        self.zeroconf.close()


class WGInterface:
    def __init__(self, ifname: str, config: IfaceConfig, dns: SimpleDNSServer):
        self.ifname = ifname
        self.ifindex: int = IPRoute().link_lookup(ifname=ifname)[0]
        self.dns = dns
        self.config = config

        self.zeroconfs = [
            WGZeroconf(name, self)
            for name in netifaces.interfaces()
            if name != 'lo' and not name.startswith('wg')
        ]

        dns.add_to_resolved(self)

    def close(self) -> None:
        for wg_zero in self.zeroconfs:
            wg_zero.close()


class WGServiceListener(ServiceListener):
    peers: Dict[str, TIfaceAddress]
    def __init__(self, wg_zero: WGZeroconf):
        self.wg_zero = wg_zero
        self.my_address = wg_zero.wg_iface.config.addr
        self.my_prefix = wg_zero.wg_iface.config.prefix
        self.pubkey = wg_zero.wg_iface.config.pubkey
        self.psk = wg_zero.wg_iface.config.psk
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
            addrs: List[TIfaceAddress] = [ipaddress.ip_address(addr) for addr in info.addresses]
            _internal_addr = props.get(b'addr', b'').decode('utf-8')
            internal_addr: Optional[TIfaceAddress] = ipaddress.ip_interface(_internal_addr) if _internal_addr else None
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
                wg_proc(
                    [
                        'set', self.wg_zero.wg_iface.ifname,
                        'peer', pubkey,
                        'preshared-key', '/dev/stdin',
                        'endpoint', endpoint,
                        'persistent-keepalive', '5',
                        'allowed-ips',
                        ','.join([
                            internal_addr.ip.compressed,
                            # Apparently we cannot add the same addr to multiple peers
                            # self.my_prefix.broadcast_address.compressed,
                        ])
                    ],
                    input=self.psk)

                # self.iface.wg.set_peer(interface=IFACE, public_key=pubkey, endpoint=endpoint, allowedips=[internal_addr])
                self.peers[pubkey] = addr
                zw_hostname = hostname + '.zerowire.'
                self.wg_zero.wg_iface.dns.add_record(
                    zw_hostname,
                    f'{zw_hostname} AAAA {internal_addr.ip.compressed}')
