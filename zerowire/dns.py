from __future__ import annotations
from typing import (
    Tuple,
    Any,
    Dict,
    Union,
    cast,
    TYPE_CHECKING
)
import asyncio
import logging
import ipaddress

import dbus
from dnslib import DNSRecord, DNSHeader, DNSLabel, RR

if TYPE_CHECKING:
    from .wgzero import WGInterface

logger = logging.getLogger(__name__)

class SimpleDNSServer:
    records: Dict[DNSLabel, str]

    def __init__(self, bind: str, port: int):
        self.bind = ipaddress.ip_address(bind)
        self.port = port
        self.loop = asyncio.get_event_loop()
        self.records = {}

    async def start(self) -> Tuple[Any, Any]:
        return await self.loop.create_datagram_endpoint(
            lambda: DNSDatagramProtocol(self),
            local_addr=(self.bind.compressed, self.port))

    def add_record(self, name: str, dest: str) -> None:
        self.records[DNSLabel(name)] = dest

    def rem_record(self, name: str) -> None:
        del self.records[name]

    def add_to_resolved(self, iface: WGInterface) -> None:
        logger.debug('ifindex %r', iface.wg_ifindex)
        bus = dbus.SystemBus()
        dbus_proxy = bus.get_object(
            'org.freedesktop.resolve1', '/org/freedesktop/resolve1')
        dbus_iface = dbus.Interface(dbus_proxy, 'org.freedesktop.resolve1.Manager')
        dbus_iface.SetLinkDNS(iface.wg_ifindex, [(2, [int(b) for b in self.bind.packed])])
        dbus_iface.SetLinkDomains(iface.wg_ifindex, [['zerowire.', True]])


class DNSDatagramProtocol(asyncio.DatagramProtocol):
    transport: asyncio.DatagramTransport

    def __init__(self, server: SimpleDNSServer) -> None:
        self.server = server
        super().__init__()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: Union[bytes, str], addr: Tuple[str, int]) -> None:
        request = DNSRecord.parse(data)
        reply = request.reply()

        for question in request.questions:
            logger.debug('Question %r', question.qname)
            record = self.server.records.get(question.qname)
            if record is not None:
                reply.add_answer(*RR.fromZone(record))

        self.transport.sendto(reply.pack(), addr)
