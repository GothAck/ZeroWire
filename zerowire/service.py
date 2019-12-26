from __future__ import annotations

from .config import Config
from .dns import dns_query_timeout, DNSRecord, DNSLabel

from typing import (
    Any,
    List,
    Dict,
    Optional,
    Tuple,
    Union,
    TypeVar,
    TYPE_CHECKING
)

if TYPE_CHECKING:
    from .wgzero import WGInterface, WGPeerInfo

import logging
import asyncio
import subprocess
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

TVar = TypeVar('TVar')

async def async_pair(name: str, future: asyncio.Future[TVar]) -> Tuple[str, Union[TVar, Exception]]:
    try:
        return (name, await future)
    except Exception as e:
        return (name, e)


@dataclass
class ServiceData:
    name: str
    priority: int
    weight: int
    port: int
    target: str
    properties: Dict[str, Any]

    @classmethod
    async def query_data(Cls, peer: WGPeerInfo, name: DNSLabel, type: DNSLabel) -> ServiceData:
        srv, txt = await asyncio.gather(
            dns_query_timeout(
                peer.addr.ip, 53,
                DNSRecord.question(name, 'SRV')),
            dns_query_timeout(
                peer.addr.ip, 53,
                DNSRecord.question(name, 'TXT')),
        )
        assert srv.rr and txt.rr
        srv_rd = srv.rr[0].rdata
        txt_rd = txt.rr[0].rdata.data
        txt_rd = b''.join(txt_rd)
        properties = {}
        while txt_rd:
            size = txt_rd[0]
            data = txt_rd[1: 1 + size]
            if b'=' not in data:
                properties[data.decode('ascii')] = True
            else:
                key, val = data.split(b'=', 2)
                properties[key.decode('ascii')] = val.decode('ascii') or False
            txt_rd = txt_rd[1 + size:]
        return Cls(
            str(name.stripSuffix(peer.hostname).stripSuffix(type)),
            srv_rd.priority,
            srv_rd.weight,
            srv_rd.port,
            str(srv_rd.target),
            properties,
        )


class ServiceDiscovery:
    task: Optional[asyncio.Task[None]]
    def __init__(self, iface: WGInterface, config: Config):
        self.iface = iface
        self.config = config
        self.service_handlers = config.service_handlers
        self.services: Dict[str, str] = {}
        self.loop = asyncio.get_event_loop()
        self.task = None

    def start(self) -> None:
        self.task = self.loop.create_task(self.discover())

    def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            self.task = None

    async def query_peer_service_types(self, peer: WGPeerInfo) -> List[DNSLabel]:
        root = await dns_query_timeout(
            peer.addr.ip, 53,
            DNSRecord.question(
                f'_services._dns-sd._udp.{peer.hostname}',
                'PTR'
            )
        )
        if not root.rr:
            logger.info('No RR returned, skipping')
            return []
        return [DNSLabel(str(type_ptr.rdata)).stripSuffix(peer.hostname) for type_ptr in root.rr]

    async def query_peer_type_services(self, peer: WGPeerInfo, types: List[DNSLabel]) -> Dict[DNSLabel, List[DNSLabel]]:
        hostname = DNSLabel(peer.hostname)
        queries = {
            type: dns_query_timeout(
                peer.addr.ip, 53,
                DNSRecord.question(
                    hostname.add(type),
                    'PTR'
                )
            )
            for type in types
        }

        services = {
            key.stripSuffix(peer.hostname): [DNSLabel(str(rr.rdata)) for rr in value.rr]
            for key, value in await asyncio.gather(*(
                async_pair(name, value)
                for name, value in queries.items()
            ))
        }

        return services

    async def query_service_data(
        self,
        peer: WGPeerInfo,
        services: Dict[DNSLabel, List[DNSLabel]]
    ) -> Dict[DNSLabel, List[ServiceData]]:
        return {
            type: await asyncio.gather(*(
                ServiceData.query_data(peer, v, type)
                for v in value
            ))
            for type, value in services.items()
        }


    async def discover(self) -> None:
        while True:
            for peer in self.iface.peers.values():
                try:
                    logger.info('Looking up services for peer %r', peer)

                    types = [
                        type
                        for type in await self.query_peer_service_types(peer)
                        if str(type) in self.service_handlers
                    ]
                    type_services = await self.query_peer_type_services(peer, types)
                    service_data = await self.query_service_data(peer, type_services)

                    for type, services in service_data.items():
                        typestr = str(type)
                        handler = self.service_handlers[typestr]
                        for service in services:
                            if service.name in self.services: continue
                            subprocess.Popen(handler.script, shell=True, env={
                                'ZW_SVC_TYPE': typestr[:-1],
                                'ZW_SVC_NAME': service.name[:-1],
                                'ZW_SVC_PORT': str(service.port),
                                'ZW_SVC_TARGET': service.target[:-1],
                                'ZW_SVC_PROPERTIES': json.dumps(service.properties),
                            })
                            self.services[service.name] = ''
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(60)
