"""Smart WM/DM pulse simulation calculations.

Provides unit conversion, pulse-flow formulas, target calibration,
and status validation for the Smart Simulation UI.
"""

from __future__ import annotations

from automation.models.models import SmartSimulationInput, SmartSimulationResult


def _to_lph(flow_value: float, flow_unit: str, area_m2: float) -> tuple[float | None, str | None]:
    if flow_value <= 0:
        return None, None
    if flow_unit == "m3/h":
        return flow_value * 1000.0, None
    if flow_unit == "mm/h":
        if area_m2 <= 0:
            return None, "Area (m2) must be greater than 0 when unit is mm/h."
        return flow_value * area_m2, None
    return flow_value, None


def _status_from_pulse_sec(pulse_time_sec: float | None) -> tuple[str, str]:
    if pulse_time_sec is None:
        return "N/A", "#666666"
    if pulse_time_sec > 10:
        return "LOW FLOW RISK", "#c62828"
    if 5 <= pulse_time_sec <= 10:
        return "BORDERLINE", "#f9a825"
    if 1 <= pulse_time_sec < 5:
        return "IDEAL", "#2e7d32"
    return "VERY HIGH PULSE RATE", "#ef6c00"


def calculate_smart_simulation(payload: SmartSimulationInput) -> SmartSimulationResult:
    """Compute simulation metrics from user inputs with validation."""
    errors: list[str] = []

    if payload.liters_per_pulse <= 0:
        errors.append("Liters per pulse must be greater than 0.")

    flow_lph, convert_error = _to_lph(payload.flow_value, payload.flow_unit, payload.area_m2)
    if convert_error:
        errors.append(convert_error)

    pulse_time_ms = payload.pulse_time_ms if payload.pulse_time_ms and payload.pulse_time_ms > 0 else None

    if flow_lph is not None and payload.liters_per_pulse > 0:
        pulse_time_ms = (payload.liters_per_pulse * 3600000.0) / flow_lph

    if payload.pulse_time_ms is not None:
        if payload.pulse_time_ms <= 0:
            errors.append("Pulse time (ms) must be greater than 0 when provided.")
        elif payload.liters_per_pulse > 0:
            pulse_time_ms = payload.pulse_time_ms
            flow_lph = (payload.liters_per_pulse * 3600000.0) / payload.pulse_time_ms

    pulse_time_sec = (pulse_time_ms / 1000.0) if pulse_time_ms is not None else None
    pulses_per_min = (60.0 / pulse_time_sec) if pulse_time_sec and pulse_time_sec > 0 else None

    required_pulses = None
    required_flow_lph = None
    recommended_pulse_time_ms = None

    if payload.target_volume_l is not None:
        if payload.target_volume_l <= 0:
            errors.append("Target volume (L) must be greater than 0 when provided.")
        elif payload.liters_per_pulse > 0:
            required_pulses = payload.target_volume_l / payload.liters_per_pulse

        if payload.runtime_min is not None:
            if payload.runtime_min <= 0:
                errors.append("Runtime (minutes) must be greater than 0 when provided.")
            elif payload.target_volume_l > 0 and payload.liters_per_pulse > 0:
                required_flow_lph = (payload.target_volume_l / payload.runtime_min) * 60.0
                recommended_pulse_time_ms = (
                    (payload.liters_per_pulse * 3600000.0) / required_flow_lph
                )

    status, status_color = _status_from_pulse_sec(pulse_time_sec)

    stable_cycle_ms = (pulse_time_ms * 1.2) if pulse_time_ms is not None else None
    fast_cycle_ms = pulse_time_ms

    return SmartSimulationResult(
        flow_lph=flow_lph,
        pulse_time_ms=pulse_time_ms,
        pulse_time_sec=pulse_time_sec,
        pulses_per_min=pulses_per_min,
        required_pulses=required_pulses,
        required_flow_lph=required_flow_lph,
        recommended_pulse_time_ms=recommended_pulse_time_ms,
        stable_cycle_ms=stable_cycle_ms,
        fast_cycle_ms=fast_cycle_ms,
        status=status,
        status_color=status_color,
        errors=errors,
    )
