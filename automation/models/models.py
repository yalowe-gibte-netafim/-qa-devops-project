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
    area_ha: float                          # hectares (1 ha = 10 000 m²)
    liters_per_pulse: float
    pulse_time_ms: float | None = None
    target_volume_l: float | None = None
    runtime_min: float | None = None
    num_valves: int = 1                     # multi-valve total flow
    correction_factor: float = 1.0          # real-world timing correction
    irrigation_mm: float | None = None      # depth of irrigation in mm
    dose_ratio_l_per_m3: float | None = None  # L of fertiliser per m³ irrigated


@dataclass
class SmartSimulationResult:
    """Computed pulse-flow calibration values for UI display."""

    flow_lph: float | None
    pulse_time_ms: float | None
    pulse_time_sec: float | None
    corrected_time_sec: float | None        # pulse_time_sec × correction_factor
    pulses_per_hour: float | None
    pulses_per_min: float | None
    total_flow_lph: float | None            # flow_lph × num_valves
    required_pulses: float | None
    required_flow_lph: float | None
    recommended_pulse_time_ms: float | None
    stable_cycle_ms: float | None
    fast_cycle_ms: float | None
    volume_m3: float | None                 # irrigation_mm × area_ha × 10
    dose_liters: float | None               # volume_m3 × dose_ratio_l_per_m3
    runtime_hours: float | None
    runtime_minutes: float | None
    runtime_seconds: float | None
    status: str
    status_color: str
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Irrigation program models
# ---------------------------------------------------------------------------

@dataclass
class IrrigationProgramInput:
    """Input for a single irrigation program calculation.

    Irrigation valves always use m³/h.
    WM meters are characterised by liters-per-pulse only (no flow rate on the meter).
    Program modes: 'duration' (minutes) | 'mm' (depth) | 'm3' (volume).
    """

    valve_flow_m3ph: float
    wm_liters_per_pulse: float
    program_mode: Literal["duration", "mm", "m3"]
    program_value: float                # minutes / mm / m³ depending on mode
    num_valves: int = 1
    area_ha: float = 0.0               # required for mm mode
    correction_factor: float = 1.0


@dataclass
class IrrigationProgramResult:
    """Computed results for an irrigation program."""

    valve_flow_lph: float | None
    total_flow_lph: float | None
    volume_m3: float | None
    runtime_hours: float | None
    runtime_minutes: float | None
    runtime_seconds: float | None
    wm_pulse_time_ms: float | None
    wm_pulse_time_sec: float | None
    corrected_pulse_time_sec: float | None
    pulses_per_hour: float | None
    pulses_per_minute: float | None
    status: str
    status_color: str
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dosing channel program models
# ---------------------------------------------------------------------------

@dataclass
class DosingProgramInput:
    """Input for a dosing channel program.

    Dosing channels always use L/h.
    DM meters are characterised by liters-per-pulse only (no flow rate on the meter).
    Program modes: 'duration' (minutes) | 'liters' (total volume).
    Dosing channels never use mm.
    """

    channel_flow_lph: float
    dm_liters_per_pulse: float
    program_mode: Literal["duration", "liters"]
    program_value: float                # minutes or litres depending on mode
    dose_ratio_l_per_m3: float = 0.0   # optional proportional fertiliser dosing


@dataclass
class DosingProgramResult:
    """Computed results for a dosing channel program."""

    total_volume_l: float | None
    runtime_hours: float | None
    runtime_minutes: float | None
    dm_pulse_time_ms: float | None
    dm_pulse_time_sec: float | None
    pulses_per_hour: float | None
    pulses_per_minute: float | None
    dose_liters: float | None
    status: str
    status_color: str
    errors: list[str] = field(default_factory=list)
