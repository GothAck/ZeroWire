from typing import Union
from ipaddress import IPv4Interface, IPv6Interface, IPv4Network, IPv6Network

TAddress = Union[IPv4Interface, IPv6Interface]
TNetwork = Union[IPv4Network, IPv6Network]
