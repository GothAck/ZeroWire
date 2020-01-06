from __future__ import annotations

from .config import ServiceConfig
from .types import TAddress, TIfaceAddress

from typing import (
    Tuple,
    List,
    Dict,
    Optional,
    Union,
    cast,
    TYPE_CHECKING
)
from copy import deepcopy
import asyncio
import logging
import ipaddress
from abc import abstractmethod
from collections import defaultdict

import dbus
import dnslib
from dnslib import DNSRecord, DNSLabel, QTYPE, RCODE, RD

from .classlogger import ClassLogger

if TYPE_CHECKING:
    from .wgzero import WGInterface

logger = logging.getLogger(__name__)

TSource = Tuple[TAddress, int]
TStrOrLabel = Union[str, DNSLabel]


class DNSClientProtocol(asyncio.DatagramProtocol, ClassLogger):
    result: Optional[DNSRecord]

    def __init__(self, query: DNSRecord, future: asyncio.Future[DNSRecord]):
        self.query = query
        self.future = future
        self.result = None
        super().__init__()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        cast(asyncio.DatagramTransport, transport).sendto(self.query.pack())
        self.transport = transport

    def datagram_received(
        self,
        data: Union[bytes, str],
        src: Tuple[str, int],
    ) -> None:
        try:
            self.result = DNSRecord.parse(data)
        except Exception as e:
            self.future.set_exception(e)
        finally:
            self.transport.close()

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc is not None:
            self.future.set_exception(exc)
        elif self.result is not None:
            self.future.set_result(self.result)


async def dns_query(host: TAddress, port: int, query: DNSRecord) -> DNSRecord:
    logger.debug('dns_query %r:%i %r', host, port, query)
    loop = asyncio.get_running_loop()
    result_future = loop.create_future()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DNSClientProtocol(query, result_future),
        remote_addr=(host.compressed, port))
    try:
        return await result_future
    finally:
        transport.close()


class DNSServerProtocol(asyncio.DatagramProtocol, ClassLogger):
    transport: asyncio.DatagramTransport

    def __init__(self, server: BaseDNSServer) -> None:
        self.server = server
        self._setLoggerName(server)
        super().__init__()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(
        self,
        data: Union[bytes, str],
        src: Tuple[str, int],
    ) -> None:
        asyncio.run_coroutine_threadsafe(
            self.handle_query(data, src), self.server.loop)

    async def handle_query(
        self,
        data: Union[bytes, str],
        src: Tuple[str, int],
    ) -> None:
        source = cast(TSource, (ipaddress.ip_address(src[0]), int))
        query = DNSRecord.parse(data)
        try:
            reply = await self.server.handle_query(query, source)
        except Exception as e:
            self.logger.exception(e)
            reply = query.reply()
            reply.header.set_rcode(RCODE.SERVFAIL)
        self.logger.debug('Reply %r to %r', reply, src)
        if reply is not None:
            self.transport.sendto(reply.pack(), src)
        self.logger.debug('Done')


class BaseDNSServer(ClassLogger):
    __records: Dict[DNSLabel, Dict[QTYPE, List[RD]]]

    def __init__(self, bind: TAddress, port: int):
        self._setLoggerName(f'{bind}:{port}')
        self.bind = bind
        self.port = port
        self.loop = asyncio.get_event_loop()
        self.__records = defaultdict(lambda: defaultdict(list))

    async def start(
        self,
    ) -> Tuple[asyncio.BaseTransport, asyncio.BaseProtocol]:
        return await self.loop.create_datagram_endpoint(
            lambda: DNSServerProtocol(self),
            local_addr=(self.bind.compressed, self.port))

    @staticmethod
    def addr_to_qdata(addr: TAddress) -> dnslib.RD:
        ip = addr.compressed
        return dnslib.A(ip) if addr.version == 4 else dnslib.AAAA(ip)

    @staticmethod
    def addr_to_qtype(addr: TAddress) -> QTYPE:
        return QTYPE.A if addr.version == 4 else QTYPE.AAAA

    def add_record(self, name: TStrOrLabel, type: QTYPE, record: RD) -> RD:
        name = name if isinstance(name, DNSLabel) else DNSLabel(name)
        records = self.__records[name][type]
        if record not in records:
            records.append(record)
        return record

    def add_addr_record(self, name: TStrOrLabel, addr: TAddress) -> RD:
        return self.add_record(
            name, self.addr_to_qtype(addr), self.addr_to_qdata(addr))

    def del_record(
        self,
        name: TStrOrLabel,
        type: Optional[QTYPE] = None,
        record: Optional[RD] = None,
    ) -> None:
        name = name if isinstance(name, DNSLabel) else DNSLabel(name)
        records = self.__records[name]
        if record is None:
            if type is None:
                del self.__records[name]
            else:
                del records[type]
        else:
            if type is None:
                for type_records in records.values():
                    type_records.remove(record)
            else:
                records[type].remove(record)

    def get_records(self, name: TStrOrLabel, type: QTYPE) -> List[RD]:
        name = name if isinstance(name, DNSLabel) else DNSLabel(name)
        records = self.__records.get(name, {})
        return records.get(type, [])

    def get_addr_records(self, name: TStrOrLabel) -> List[RD]:
        name = name if isinstance(name, DNSLabel) else DNSLabel(name)
        return [
            *self.get_records(name, QTYPE.AAAA),
            *self.get_records(name, QTYPE.A)
        ]

    def has_name(self, name: TStrOrLabel) -> bool:
        name = name if isinstance(name, DNSLabel) else DNSLabel(name)
        return name in self.__records

    def get_all_records(self) -> Dict[DNSLabel, Dict[QTYPE, List[RD]]]:
        return deepcopy(self.__records)

    @staticmethod
    def validate_query_label(query: DNSLabel) -> None:
        if query.label[-1] != b'zerowire':
            raise Exception('Invalid suffix')

    @abstractmethod
    async def handle_query(
        self,
        request: DNSRecord,
        source: TSource,
    ) -> Optional[DNSRecord]:
        pass


class LocalDNSServer(BaseDNSServer):
    def __init__(self, bind: TAddress, port: int):
        super().__init__(bind, port)

    async def handle_query(
        self,
        request: DNSRecord,
        source: TSource,
    ) -> DNSRecord:
        reply = request.reply()
        queries: List[asyncio.Future[DNSRecord]] = []

        nxdomain = False

        for question in request.questions:
            qname = question.qname
            qtype = question.qtype
            self.validate_query_label(qname)
            self.logger.debug('Question %r %r', qname, QTYPE[qtype])
            if len(qname.label) > 2:
                remote_qname = str(DNSLabel(qname.label[-2:]))
                remote_records = self.get_addr_records(remote_qname)
                self.logger.debug('Remote question %r', question.qname)
                if remote_records:
                    q = DNSRecord()
                    q.add_question(question)
                    queries.append(asyncio.wait_for(
                        dns_query(
                            ipaddress.ip_address(repr(remote_records[0])),
                            53,
                            q,
                        ),
                        0.5
                    ))
                else:
                    nxdomain = True
                continue
            if not self.has_name(qname):
                nxdomain = True
            records = self.get_records(qname, qtype)
            self.logger.debug('Record %r', records)
            for record in records:
                reply.add_answer(dnslib.RR(
                    rname=qname,
                    rtype=qtype,
                    rdata=record,
                ))
        if queries:
            self.logger.debug('Awaiting gather')
            try:
                answers = await asyncio.gather(
                    *queries, return_exceptions=True)
            except Exception as e:
                self.logger.error(e)
            else:
                self.logger.debug('gather complete %r', answers)
                for answer in answers:
                    self.logger.debug('answer %r', answer)
                    if isinstance(answer, Exception):
                        self.logger.exception(answer)
                    else:
                        reply.add_answer(*answer.rr)

        if nxdomain:
            self.logger.debug('No answers')
            reply.header.set_rcode(RCODE.NXDOMAIN)

        return reply

    def add_to_resolved(self, iface: WGInterface) -> None:
        self.logger.debug('ifindex %r', iface.ifindex)
        bus = dbus.SystemBus()
        dbus_proxy = bus.get_object(
            'org.freedesktop.resolve1', '/org/freedesktop/resolve1')
        dbus_iface = dbus.Interface(
            dbus_proxy, 'org.freedesktop.resolve1.Manager')
        dbus_iface.SetLinkDNS(
            iface.ifindex, [(2, [int(b) for b in self.bind.packed])])
        dbus_iface.SetLinkDomains(
            iface.ifindex, [['zerowire.', True]])


class InterfaceDNSServer(BaseDNSServer):
    def __init__(self, hostname: str, bind: TIfaceAddress, port: int = 53):
        super().__init__(bind.ip, port)
        self.hostname = DNSLabel(f'{hostname}.zerowire.')
        self.network = bind.network
        self.add_record(
            '_services._dns-sd._udp',
            QTYPE.PTR,
            dnslib.PTR(
                self.hostname.add('_services._dns-sd._udp')))
        self.add_record(
            'b._dns-sd._udp',
            QTYPE.PTR,
            dnslib.PTR(self.hostname))
        self.add_record(
            'lb._dns-sd._udp',
            QTYPE.PTR,
            dnslib.PTR(self.hostname))

    def add_service(self, service: ServiceConfig) -> None:
        type = DNSLabel(service.type)
        name = type.add(DNSLabel(service.name))
        type_suffixed = self.hostname.add(type)
        name_suffixed = self.hostname.add(name)
        port = service.port
        props_list = []
        for key, value in (service.properties or {}).items():
            prop = key
            if isinstance(value, bool):
                if not value:
                    prop += '='
            else:
                prop += '=' + str(value)
            if len(prop) > 255:
                self.logger.error('Property too large to add to txt record %s', key)
                continue
            props_list.append(prop)

        props = ''.join(
            chr(len(prop)) + prop
            for prop in props_list
        )

        self.add_record(
            type,
            QTYPE.PTR,
            dnslib.PTR(name_suffixed))
        self.add_record(
            '_services._dns-sd._udp',
            QTYPE.PTR,
            dnslib.PTR(type_suffixed))
        self.add_record(
            name,
            QTYPE.SRV,
            dnslib.SRV(0, 0, port, self.hostname))
        self.add_record(
            name,
            QTYPE.TXT,
            dnslib.TXT(props))

    async def handle_query(
        self,
        request: DNSRecord,
        source: TSource,
    ) -> DNSRecord:
        if source[0] not in self.network:
            return None
        reply = request.reply()
        gave_answers = False

        for question in request.questions:
            orig_qname = question.qname
            self.validate_query_label(orig_qname)
            if not orig_qname.matchSuffix(self.hostname):
                raise Exception('Request for non local domain.')
            qname = orig_qname.stripSuffix(self.hostname)
            qtype = question.qtype
            self.logger.debug('Question %r %r', qname, QTYPE[qtype])

            records = self.get_records(qname, qtype)
            for record in records:
                reply.add_answer(dnslib.RR(
                    rname=orig_qname,
                    rtype=qtype,
                    rdata=record,
                ))
                gave_answers = True

        if not gave_answers:
            self.logger.debug('No answers')
            reply.header.set_rcode(RCODE.NXDOMAIN)

        return reply
