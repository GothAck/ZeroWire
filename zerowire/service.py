from __future__ import annotations
from typing import (
    List,
    Dict,
)
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
from .config import Config

class ServiceInterface:
    def __init__(self, config: Config):
        self.config = config
        self.zeroconf = Zeroconf(config.my_address().compressed, True)
