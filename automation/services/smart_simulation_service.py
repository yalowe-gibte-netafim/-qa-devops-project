"""Smart WM/DM pulse simulation calculations.

Provides unit conversion, pulse-flow formulas, target calibration,
multi-valve support, correction factor, irrigation volume, and
proportional dosing for the Smart Simulation UI.
"""

from __future__ import annotations

from automation.models.models import SmartSimulationInput, SmartSimulationResult


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

def _to_lph(flow_value: float, flow_unit: str, area_ha: float) -> tuple[float | None, str | None]:
    """Convert any supported flow unit to L/h.

    Formula 1  – m3/h → L/h : flow_lph = flow_m3ph * 1000
    Formula mm/h : flow_lph  = flow_mm_h * area_ha * 10 000
                               (1 mm on 1 ha = 10 m³ = 10 000 L)
    """
    if flow_value <= 0:
        return None, None
    if flow_unit == "m3/h":
        return flow_value * 1000.0, None
    if flow_unit == "mm/h":
        if area_ha <= 0:
            return None, "Area (ha) must be greater than 0 when unit is mm/h."
        # 1 mm/h on 1 ha = 10 000 L/h
        return flow_value * area_ha * 10_000.0, None
    # L/h — pass through
    return flow_value, None


# ---------------------------------------------------------------------------
# Status classification  (Formula 8)
# ---------------------------------------------------------------------------

def _status_from_pulse_sec(pulse_time_sec: float | None) -> tuple[str, str]:
    """Classify pulse timing quality.

    <1 s      → Too Fast
    1–5 s     → Ideal
    5–10 s    → Borderline
    >10 s     → Low Flow Risk
    """
    if pulse_time_sec is None:
        return "N/A", "#666666"
    if pulse_time_sec > 10:
        return "LOW FLOW RISK", "#c62828"
    if 5 < pulse_time_sec <= 10:
        return "BORDERLINE", "#f9a825"
    if 1 <= pulse_time_sec <= 5:
        return "IDEAL", "#2e7d32"
    return "TOO FAST", "#ef6c00"


# ---------------------------------------------------------------------------
# Main calculation entry point
# ---------------------------------------------------------------------------

def calculate_smart_simulation(payload: SmartSimulationInput) -> SmartSimulationResult:
    """Compute all simulation metrics from user inputs with full validation."""
    errors: list[str] = []

    # ── Basic input validation ────────────────────────────────────────────────
    if payload.liters_per_pulse <= 0:
        errors.append("Liters per pulse must be greater than 0.")
    if payload.num_valves <= 0:
        errors.append("Number of valves must be greater than 0.")
    if payload.correction_factor <= 0:
        errors.append("Correction factor must be greater than 0.")

    # ── Formula 1 – flow conversion ───────────────────────────────────────────
    flow_lph, convert_error = _to_lph(payload.flow_value, payload.flow_unit, payload.area_ha)
    if convert_error:
        errors.append(convert_error)

    # ── Formula 9 – multi-valve total flow ────────────────────────────────────
    total_flow_lph: float | None = None
    if flow_lph is not None and payload.num_valves > 0:
        total_flow_lph = payload.num_valves * flow_lph

    # Use total (multi-valve) flow for pulse timing
    effective_flow_lph = total_flow_lph if total_flow_lph is not None else flow_lph

    # ── Formulas 2 & 3 – pulse timing and rate ────────────────────────────────
    pulse_time_ms: float | None = None
    if effective_flow_lph is not None and payload.liters_per_pulse > 0:
        # time_ms = (L/pulse * 3 600 000) / flow_lph
        pulse_time_ms = (payload.liters_per_pulse * 3_600_000.0) / effective_flow_lph

    # Override with manual pulse time if given (and reverse-calculate flow)
    if payload.pulse_time_ms is not None:
        if payload.pulse_time_ms <= 0:
            errors.append("Pulse time (ms) must be greater than 0 when provided.")
        elif payload.liters_per_pulse > 0:
            pulse_time_ms = payload.pulse_time_ms
            # Formula 7 – reverse: flow_lph = (L/pulse * 3 600 000) / time_ms
            effective_flow_lph = (payload.liters_per_pulse * 3_600_000.0) / payload.pulse_time_ms
            total_flow_lph = effective_flow_lph
            flow_lph = (
                effective_flow_lph / payload.num_valves
                if payload.num_valves > 0
                else effective_flow_lph
            )

    pulse_time_sec = (pulse_time_ms / 1000.0) if pulse_time_ms is not None else None

    # Formula 10 – corrected time
    corrected_time_sec: float | None = None
    if pulse_time_sec is not None:
        corrected_time_sec = pulse_time_sec * payload.correction_factor

    # pulses_per_hour = flow_lph / L_per_pulse   (Formula 3)
    pulses_per_hour: float | None = None
    pulses_per_min: float | None = None
    if effective_flow_lph is not None and payload.liters_per_pulse > 0:
        pulses_per_hour = effective_flow_lph / payload.liters_per_pulse
        pulses_per_min = pulses_per_hour / 60.0

    # ── Formula 5 – irrigation volume from mm + hectare ───────────────────────
    # volume_m3 = irrigation_mm * area_ha * 10   (1 mm on 1 ha = 10 m³)
    volume_m3: float | None = None
    if payload.irrigation_mm is not None and payload.irrigation_mm > 0 and payload.area_ha > 0:
        volume_m3 = payload.irrigation_mm * payload.area_ha * 10.0

    # ── Formula 4 – program runtime ───────────────────────────────────────────
    # time_hours = volume_m3 / flow_m3ph
    runtime_hours: float | None = None
    runtime_minutes: float | None = None
    runtime_seconds: float | None = None
    if volume_m3 is not None and effective_flow_lph is not None and effective_flow_lph > 0:
        flow_m3ph = effective_flow_lph / 1000.0
        runtime_hours = volume_m3 / flow_m3ph
        runtime_minutes = runtime_hours * 60.0
        runtime_seconds = runtime_minutes * 60.0

    # ── Formula 6 – proportional dosing ──────────────────────────────────────
    # dose_L = volume_m3 * ratio_L_per_m3
    dose_liters: float | None = None
    if (
        volume_m3 is not None
        and payload.dose_ratio_l_per_m3 is not None
        and payload.dose_ratio_l_per_m3 > 0
    ):
        dose_liters = volume_m3 * payload.dose_ratio_l_per_m3

    # ── Target volume analysis (existing feature) ─────────────────────────────
    required_pulses: float | None = None
    required_flow_lph: float | None = None
    recommended_pulse_time_ms: float | None = None

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
                    (payload.liters_per_pulse * 3_600_000.0) / required_flow_lph
                )

    # ── Status classification ─────────────────────────────────────────────────
    status, status_color = _status_from_pulse_sec(pulse_time_sec)

    stable_cycle_ms = (pulse_time_ms * 1.2) if pulse_time_ms is not None else None
    fast_cycle_ms = pulse_time_ms

    return SmartSimulationResult(
        flow_lph=flow_lph,
        pulse_time_ms=pulse_time_ms,
        pulse_time_sec=pulse_time_sec,
        corrected_time_sec=corrected_time_sec,
        pulses_per_hour=pulses_per_hour,
        pulses_per_min=pulses_per_min,
        total_flow_lph=total_flow_lph,
        required_pulses=required_pulses,
        required_flow_lph=required_flow_lph,
        recommended_pulse_time_ms=recommended_pulse_time_ms,
        stable_cycle_ms=stable_cycle_ms,
        fast_cycle_ms=fast_cycle_ms,
        volume_m3=volume_m3,
        dose_liters=dose_liters,
        runtime_hours=runtime_hours,
        runtime_minutes=runtime_minutes,
        runtime_seconds=runtime_seconds,
        status=status,
        status_color=status_color,
        errors=errors,
    )
