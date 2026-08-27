"""Hardware connectors — each connector packages its own matching, drilling, and machining logic."""

from .base import Connector, HoleSpec
from .trinity import TrinityConnector
from .hinge import HingeConnector
from .shelf import ShelfConnector
from .back_mount import BackMountConnector
from .drawer_slide import DrawerSlideConnector

__all__ = [
    "Connector",
    "HoleSpec",
    "TrinityConnector",
    "HingeConnector",
    "ShelfConnector",
    "BackMountConnector",
    "DrawerSlideConnector",
]

ALL_CONNECTORS = [
    TrinityConnector,
    HingeConnector,
    ShelfConnector,
    BackMountConnector,
    DrawerSlideConnector,
]
