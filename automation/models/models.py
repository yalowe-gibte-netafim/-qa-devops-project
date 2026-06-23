"""Domain models shared across all layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class LogEvent:
    """Represents a single parsed event from a FLEX CLI log file."""
    time: str                        # full datetime string "YYYY-MM-DD HH:MM:SS"
    original_time: str               # raw HH:MM:SS from log
    full_time: datetime              # parsed datetime object
    type: str                        # 'valve' | 'wm'
    id: int                          # device number
    action: str                      # lowercase action string, e.g. 'open', 'close'
    count: int = 0                   # pulse count (wm events)
    wm_snapshot: dict[int, int] = field(default_factory=dict)  # {wm_id: cumulative_count}


@dataclass
class SmartSimulationInput:
    """Input payload for smart WM/DM pulse simulation calculations."""

    meter_type: Literal["WM", "DM"]
    flow_value: float
    flow_unit: Literal["L/h", "m3/h", "mm/h"]
    area_m2: float
    liters_per_pulse: float
    pulse_time_ms: float | None = None
    target_volume_l: float | None = None
    runtime_min: float | None = None


@dataclass
class SmartSimulationResult:
    """Computed pulse-flow calibration values for UI display."""

    flow_lph: float | None
    pulse_time_ms: float | None
    pulse_time_sec: float | None
    pulses_per_min: float | None
    required_pulses: float | None
    required_flow_lph: float | None
    recommended_pulse_time_ms: float | None
    stable_cycle_ms: float | None
    fast_cycle_ms: float | None
    status: str
    status_color: str
    errors: list[str] = field(default_factory=list)
