#!/usr/bin/env python3
from __future__ import annotations

from .args import Args
from .config import Config
from .wgzero import WGInterface
from .dns import LocalDNSServer

from typing import (
    List,
)

import logging
from .classlogger import ClassLogger

import ipaddress
from asyncio import (
    AbstractEventLoop,
    gather,
    get_event_loop,
    Task,
)
from signal import SIGINT, SIGTERM


FORMAT = '[%(levelname)s] %(name)s - %(message)s'


class App(ClassLogger):
    loop: AbstractEventLoop
    interfaces: List[WGInterface]
    __stopping: bool = False

    def __init__(self) -> None:
        self.loop = get_event_loop()
        self.interfaces = []

        self.args = Args.from_docopt()

        logging.basicConfig(format=FORMAT, level=self.args.level)
        self.config = Config.load(self.args.config)
        self.logger.debug('Config %s', self.config.__dict__)
        self.dns = LocalDNSServer(ipaddress.ip_address('127.122.119.53'), 53)

        for wg_ifname in self.config:
            wg_ifconfig = self.config[wg_ifname]
            wg_ifconfig.configure()
            self.interfaces.append(
                WGInterface(wg_ifname, wg_ifconfig, self.dns))

        for sig in {SIGINT, SIGTERM}:
            self.loop.add_signal_handler(sig, self.stop, sig)

    async def __stop(self, sig: int) -> None:
        self.logger.info('Exiting on signal %d', sig)
        for wgiface in self.interfaces:
            wgiface.close()

    def stop(self, sig: int) -> None:
        if self.__stopping:
            return
        self.__stopping = True

        def stop(task: Task[None]) -> None:
            self.logger.info('Stopping event loop')
            self.loop.stop()
        self.loop.create_task(self.__stop(sig)).add_done_callback(stop)

    async def init_task(self) -> None:
        await self.dns.start()
        await gather(*(
            iface.start()
            for iface in self.interfaces
        ))
        self.logger.info('Init done')

    def run(self) -> None:
        try:
            self.loop.create_task(self.init_task())
            self.loop.run_forever()
        finally:
            self.loop.close()


if __name__.endswith("__main__"):
    App().run()
