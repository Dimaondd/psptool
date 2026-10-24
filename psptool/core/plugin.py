"""Game plugins.

A game plugin knows one game (or one engine/family) and wires the format
modules it needs: archive, compression, text, font. The core only knows
ISO, projects and this interface.
"""
from typing import Dict, List, Optional, Type

from .iso import IsoImage
from .project import Project


class GamePlugin:
    id = ""
    name = ""
    # what the UI may offer for this game: "texts", "charmap", ...
    features: tuple = ()

    @classmethod
    def detect(cls, iso: IsoImage, sfo: dict) -> bool:
        return False

    def __init__(self, project: Project):
        self.project = project

    def unpack(self, iso: IsoImage, everything: bool = False):
        """Pull files out of the ISO into the project folder."""
        raise NotImplementedError

    def pack(self, out_iso: str):
        """Build a new ISO from the original plus everything changed."""
        raise NotImplementedError

    def info(self) -> List[str]:
        return []


_REGISTRY: Dict[str, Type[GamePlugin]] = {}


def register(cls: Type[GamePlugin]) -> Type[GamePlugin]:
    _REGISTRY[cls.id] = cls
    return cls


def all_plugins() -> List[Type[GamePlugin]]:
    _load_builtin()
    return list(_REGISTRY.values())


def get_plugin(plugin_id: str) -> Type[GamePlugin]:
    _load_builtin()
    return _REGISTRY[plugin_id]


def detect(iso: IsoImage, sfo: dict) -> Optional[Type[GamePlugin]]:
    for cls in all_plugins():
        if cls.detect(iso, sfo):
            return cls
    return None


def _load_builtin():
    # importing a game module registers it
    from ..games import bleach_sc2  # noqa: F401
