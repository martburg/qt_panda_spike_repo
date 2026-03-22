from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FrameImage:
    width: int
    height: int
    rgba_bytes: bytes


@dataclass(frozen=True)
class PickRequest:
    widget_x: float
    widget_y: float
    widget_width: float
    widget_height: float
    display_x: float
    display_y: float
    display_width: float
    display_height: float
    image_x: float
    image_y: float
    image_width: float
    image_height: float

    def to_record(self) -> dict[str, object]:
        return {
            "widget": {
                "x": self.widget_x,
                "y": self.widget_y,
                "width": self.widget_width,
                "height": self.widget_height,
            },
            "display_rect": {
                "x": self.display_x,
                "y": self.display_y,
                "width": self.display_width,
                "height": self.display_height,
            },
            "image": {
                "x": self.image_x,
                "y": self.image_y,
                "width": self.image_width,
                "height": self.image_height,
                "normalized_x": (self.image_x / self.image_width) * 2.0 - 1.0 if self.image_width > 0.0 else 0.0,
                "normalized_y": 1.0 - (self.image_y / self.image_height) * 2.0 if self.image_height > 0.0 else 0.0,
            },
        }


@dataclass(frozen=True)
class PickReport:
    status_text: str
    debug_record: dict[str, object]


class ViewportBackend(ABC):
    @abstractmethod
    def start(self, host_widget: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def step(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def resize(self, width: int, height: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def orbit(self, delta_x: float, delta_y: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def zoom(self, wheel_delta: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError

    def is_ready(self) -> bool:
        return True

    def latest_frame(self) -> FrameImage | None:
        return None

    def pick(self, request: PickRequest) -> PickReport | None:
        return None

    def drain_status_messages(self) -> list[str]:
        return []
