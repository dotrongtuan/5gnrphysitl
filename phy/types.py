from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True, frozen=True)
class SpatialLayout:
    num_codewords: int = 1
    num_layers: int = 1
    num_ports: int = 1
    num_tx_antennas: int = 1
    num_rx_antennas: int = 1

    def __post_init__(self) -> None:
        for field_name in (
            "num_codewords",
            "num_layers",
            "num_ports",
            "num_tx_antennas",
            "num_rx_antennas",
        ):
            value = int(getattr(self, field_name))
            if value < 1:
                raise ValueError(f"{field_name} must be at least 1, got {value}.")

    @classmethod
    def from_config(cls, config: Mapping[str, Any] | None) -> "SpatialLayout":
        spatial_cfg = dict(config.get("spatial", {})) if config else {}
        return cls(
            num_codewords=int(spatial_cfg.get("num_codewords", 1)),
            num_layers=int(spatial_cfg.get("num_layers", 1)),
            num_ports=int(spatial_cfg.get("num_ports", 1)),
            num_tx_antennas=int(spatial_cfg.get("num_tx_antennas", 1)),
            num_rx_antennas=int(spatial_cfg.get("num_rx_antennas", 1)),
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "num_codewords": self.num_codewords,
            "num_layers": self.num_layers,
            "num_ports": self.num_ports,
            "num_tx_antennas": self.num_tx_antennas,
            "num_rx_antennas": self.num_rx_antennas,
        }


@dataclass(slots=True, frozen=True)
class TensorViewSpec:
    name: str
    axes: tuple[str, ...]
    shape: tuple[int, ...]
    description: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "axes": list(self.axes),
            "shape": list(self.shape),
            "description": self.description,
        }
