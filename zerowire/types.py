from typing import Union
from ipaddress import (
    IPv4Interface,
    IPv6Interface,
    IPv4Address,
    IPv6Address,
    IPv4Network,
    IPv6Network,
)

TIfaceAddress = Union[IPv4Interface, IPv6Interface]
TAddress = Union[IPv4Address, IPv6Address]
TNetwork = Union[IPv4Network, IPv6Network]
