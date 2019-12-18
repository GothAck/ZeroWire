from __future__ import annotations
from typing import (
    List,
    Dict,
)
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
from .config import IfaceConfig

class ServiceInterface:
    def __init__(self, config: IfaceConfig):
        self.config = config
        self.zeroconf = Zeroconf([config.addr.compressed], True)
