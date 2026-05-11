from dataclasses import dataclass
from typing import Callable, List, Optional

from .base import ToolResult


@dataclass(frozen=True)
class ToolCapabilities:
    needs_internet: bool = False
    needs_camera: bool = False
    needs_microphone: bool = False
    affects_motion: bool = False


@dataclass(frozen=True)
class ToolMeta:
    name: str
    description: str
    required_args: List[str]
    optional_args: List[str]
    implemented: bool
    needs_internet: bool
    needs_camera: bool
    needs_microphone: bool
    affects_motion: bool
    recommended_display_face: str
    fn: Optional[Callable[..., ToolResult]]

    @property
    def capabilities(self) -> ToolCapabilities:
        return ToolCapabilities(
            needs_internet=self.needs_internet,
            needs_camera=self.needs_camera,
            needs_microphone=self.needs_microphone,
            affects_motion=self.affects_motion,
        )
