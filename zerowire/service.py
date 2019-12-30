from __future__ import annotations

from .config import IfaceConfig

from zeroconf import Zeroconf


class ServiceInterface:
    def __init__(self, config: IfaceConfig):
        self.config = config
        self.zeroconf = Zeroconf([config.addr.compressed], True)
