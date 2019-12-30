from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    TYPE_CHECKING
)

import logging
import weakref
import asyncio
from dataclasses import dataclass
from collections.abc import Mapping
import json

from .config import Config, ServiceHandlerConfig
from .dns import dns_query_timeout, DNSRecord, DNSLabel

if TYPE_CHECKING:
    from .wgzero import WGPeer

logger = logging.getLogger(__name__)

TKey = TypeVar('TKey')
TVar = TypeVar('TVar')


async def async_pair(
    key: TKey,
    future: Awaitable[TVar],
) -> Tuple[TKey, Union[TVar, Exception]]:
    try:
        return (key, await future)
    except Exception as e:
        return (key, e)


@dataclass
class ServiceData:
    type: str
    name: str
    priority: int
    weight: int
    port: int
    target: str
    properties: Dict[str, Any]
    handler: Optional[ServiceHandlerConfig] = None

    def __hash__(self) -> int:
        return hash(self.name)

    @classmethod
    async def query_data(
        Cls,
        peer: WGPeer,
        name: DNSLabel,
        type: DNSLabel,
    ) -> ServiceData:
        srv, txt = await asyncio.gather(
            dns_query_timeout(
                peer.int_addr.ip, 53,
                DNSRecord.question(name, 'SRV')),
            dns_query_timeout(
                peer.int_addr.ip, 53,
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
            str(type),
            str(name.stripSuffix(peer.hostname).stripSuffix(type)),
            srv_rd.priority,
            srv_rd.weight,
            srv_rd.port,
            str(srv_rd.target),
            properties,
        )

    async def run_start(
        self,
    ) -> Optional[asyncio.subprocess.Process]:
        if self.handler:
            logger.info('Running handler start %s', self.handler.start)
            return await asyncio.create_subprocess_shell(
                self.handler.start,
                env=self.get_env())
        logger.info('No handler, start')
        return None

    async def run_stop(
        self,
    ) -> Optional[asyncio.subprocess.Process]:
        if self.handler:
            logger.info('Running handler stop %s', self.handler.stop)
            return await asyncio.create_subprocess_shell(
                self.handler.stop,
                env=self.get_env())
        logger.info('No handler, stop')
        return None

    def get_env(self) -> Dict[str, str]:
        return {
            'ZW_SVC_TYPE': self.type[:-1],
            'ZW_SVC_NAME': self.name[:-1],
            'ZW_SVC_PORT': str(self.port),
            'ZW_SVC_TARGET': self.target[:-1],
            'ZW_SVC_PROPERTIES': json.dumps(self.properties),
        }


async def wait_terminate_process(
    process: asyncio.subprocess.Process,
    timeout: int = 2,
) -> Optional[int]:
    for _ in range(3):
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
        else:
            break
    return process.returncode


if TYPE_CHECKING:
    MappingBase = Mapping[str, ServiceData]
else:
    MappingBase = Mapping


class ServiceDiscovery(MappingBase):
    task: Optional[asyncio.Task[None]]

    def __init__(self, peer: WGPeer, config: Config):
        logger.debug('ServiceDiscovery.__init__ %s', peer.name)
        self.peer = peer
        self.config = config
        self.service_handlers = config.service_handlers
        self.services: Dict[str, ServiceData] = {}
        self.task = None
        # weakref.finalize(self, lambda services: , self.services)

    # def __del__(self) -> None:
    #     self.stop()
    #     for service in self.services.values():
    #         handler = self.service_handlers.get(service.type)
    #         if handler:
    #             loop.call_soon_threadsafe(handler.run_stop, service)

    def __start(self) -> None:
        logger.debug('__start %s', self.peer.name)
        self.task = asyncio.create_task(self.discover())

    def start(self) -> None:
        logger.debug('start %s', self.peer.name)
        self.peer.wg_iface.loop.call_soon_threadsafe(self.__start)

    def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def __len__(self) -> int:
        return len(self.services)

    def __getitem__(self, key: str) -> ServiceData:
        return self.services[key]

    def __iter__(self) -> Iterator[str]:
        return self.services.__iter__()

    async def query_peer_service_types(self, peer: WGPeer) -> List[DNSLabel]:
        root = await dns_query_timeout(
            peer.int_addr.ip, 53,
            DNSRecord.question(
                f'_services._dns-sd._udp.{peer.hostname}',
                'PTR'
            )
        )
        if not root.rr:
            logger.info('No RR returned, skipping')
            return []
        return [
            DNSLabel(str(type_ptr.rdata)).stripSuffix(peer.hostname)
            for type_ptr in root.rr
        ]

    async def query_peer_type_services(
        self,
        peer: WGPeer,
        types: List[DNSLabel],
    ) -> Dict[DNSLabel, List[DNSLabel]]:
        hostname = DNSLabel(peer.hostname)
        queries = {
            type: dns_query_timeout(
                peer.int_addr.ip, 53,
                DNSRecord.question(
                    hostname.add(type),
                    'PTR'
                )
            )
            for type in types
        }

        services = {
            key.stripSuffix(peer.hostname): [
                DNSLabel(str(rr.rdata)) for rr in value.rr
            ]
            for key, value in await asyncio.gather(*(
                async_pair(name, value)
                for name, value in queries.items()
            ))
        }

        return services

    async def query_service_data(
        self,
        peer: WGPeer,
        services: Dict[DNSLabel, List[DNSLabel]]
    ) -> Dict[DNSLabel, List[ServiceData]]:
        return {
            type: await asyncio.gather(*(
                ServiceData.query_data(peer, v, type)
                for v in value
            ))
            for type, value in services.items()
        }

    async def discover_peer(self, peer: WGPeer) -> None:
        subprocesses: Dict[ServiceData, asyncio.subprocess.Process] = {}
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
                for service in services:
                    if service.name in self.services:
                        continue
                    start = await service.run_start()
                    if start is not None:
                        subprocesses[service] = start
                    else:
                        self.services[service.name] = service
        except Exception as e:
            logger.exception(e)
            return
        all_results = asyncio.gather(*(
            async_pair(key, wait_terminate_process(process))
            for key, process in subprocesses.items()
        ))
        for service, returncode in all_results:
            print(service.name)
            if returncode is None or returncode != 0:
                logger.error(
                    'Subprocess for service %s failed with returncode %i',
                    service.name,
                    returncode)
            else:
                self.services[service.name] = service

    async def discover(self) -> None:
        while True:
            logger.debug('Run peer detection for peer %s', self.peer.name)
            await self.discover_peer(self.peer)
            await asyncio.sleep(60)
