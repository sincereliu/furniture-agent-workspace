"""Hardware connectors — each connector packages its own matching, drilling, and machining logic."""

from .base import Connector, HoleSpec
from .trinity import TrinityConnector
from .hinge import HingeConnector
from .shelf import ShelfConnector

__all__ = ["Connector", "HoleSpec", "TrinityConnector", "HingeConnector", "ShelfConnector"]

ALL_CONNECTORS = [TrinityConnector, HingeConnector, ShelfConnector]
