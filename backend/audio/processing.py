from __future__ import annotations

from dataclasses import dataclass
from math import pow
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class ProcessingProfile:
    """A conservative, station-specific stream-processing preset."""

    name: str = "default"
    target_lufs: float = -16.0
    loudness_tolerance_lu: float = 1.0
    true_peak_ceiling_dbtp: float = -1.0
    input_gain_db: float = 0.0
    wideband_agc_max_gain_db: float = 3.0
    multiband_ratio: float = 1.5

    stage_names: ClassVar[tuple[str, ...]] = (
        "input_level_control",
        "gentle_wideband_agc",
        "restrained_multiband_dynamics",
        "true_peak_limiter",
        "encoder",
    )

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be blank")
        if not -17.0 <= self.target_lufs <= -15.0:
            raise ValueError("target_lufs must stay within the approved -16 LUFS ±1 range")
        if self.loudness_tolerance_lu != 1.0:
            raise ValueError("loudness_tolerance_lu must be 1.0")
        if self.true_peak_ceiling_dbtp > -1.0:
            raise ValueError("true_peak_ceiling_dbtp must not exceed -1 dBTP")
        if not -6.0 <= self.input_gain_db <= 3.0:
            raise ValueError("input_gain_db must remain conservative")
        if not 0.0 < self.wideband_agc_max_gain_db <= 3.0:
            raise ValueError("wideband_agc_max_gain_db must remain gentle")
        if not 1.0 < self.multiband_ratio <= 2.0:
            raise ValueError("multiband_ratio must remain restrained")

    @property
    def input_gain_factor(self) -> float:
        return pow(10.0, self.input_gain_db / 20.0)
