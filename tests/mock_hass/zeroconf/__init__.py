"""Mock zeroconf package for test environment."""
from enum import Enum


class IPVersion(Enum):
    V4Only = 1
    All = 2
