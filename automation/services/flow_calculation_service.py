"""Reusable calculation service for irrigation and dosing programs.

All methods are stateless with no UI dependencies.
Input validation raises ValueError with a descriptive message.
Formulas follow the specification exactly.
"""

from __future__ import annotations

from automation.models.models import (
    IrrigationProgramInput,
    IrrigationProgramResult,
    DosingProgramInput,
    DosingProgramResult,
)


class FlowCalculationService:
    """Business logic for flow, pulse timing, runtime, volume and dosing."""

    # ── Formula 1 – unit conversion ───────────────────────────────────────

    @staticmethod
    def m3h_to_lph(flow_m3ph: float) -> float:
        """Convert m³/h to L/h.  flow_lph = flow_m3ph × 1000."""
        if flow_m3ph <= 0:
            raise ValueError("Valve flow must be > 0.")
        return flow_m3ph * 1000.0

    # ── Formula 2 – pulse interval ────────────────────────────────────────

    @staticmethod
    def pulse_time_ms(liters_per_pulse: float, flow_lph: float) -> float:
        """Time between pulses in milliseconds.
        time_ms = (L/pulse × 3 600 000) / flow_lph
        """
        if liters_per_pulse <= 0:
            raise ValueError("Liters per pulse must be > 0.")
        if flow_lph <= 0:
            raise ValueError("Flow must be > 0.")
        return (liters_per_pulse * 3_600_000.0) / flow_lph

    @staticmethod
    def pulse_time_sec(liters_per_pulse: float, flow_lph: float) -> float:
        """Time between pulses in seconds.
        time_sec = (L/pulse × 3600) / flow_lph
        """
        return FlowCalculationService.pulse_time_ms(liters_per_pulse, flow_lph) / 1000.0

    # ── Formula 3 – pulse frequency ───────────────────────────────────────

    @staticmethod
    def pulses_per_hour(flow_lph: float, liters_per_pulse: float) -> float:
        """pulses_per_hour = flow_lph / liters_per_pulse"""
        if flow_lph <= 0 or liters_per_pulse <= 0:
            raise ValueError("Flow and pulse size must be > 0.")
        return flow_lph / liters_per_pulse

    @staticmethod
    def pulses_per_minute(flow_lph: float, liters_per_pulse: float) -> float:
        """pulses_per_minute = pulses_per_hour / 60"""
        return FlowCalculationService.pulses_per_hour(flow_lph, liters_per_pulse) / 60.0

    # ── Formula 4 – runtime from volume ──────────────────────────────────

    @staticmethod
    def runtime_from_volume(
        volume_m3: float, total_flow_m3ph: float
    ) -> tuple[float, float, float]:
        """Runtime given volume and flow.  Returns (hours, minutes, seconds).
        time_hours = volume_m3 / flow_m3ph
        """
        if volume_m3 <= 0:
            raise ValueError("Volume must be > 0.")
        if total_flow_m3ph <= 0:
            raise ValueError("Flow must be > 0.")
        hours = volume_m3 / total_flow_m3ph
        return hours, hours * 60.0, hours * 3600.0

    # ── Formula 5 – irrigation volume from mm ────────────────────────────

    @staticmethod
    def volume_from_mm(irrigation_mm: float, area_ha: float) -> float:
        """Irrigation volume from depth and field area.
        volume_m3 = irrigation_mm × area_ha × 10
        (1 mm on 1 ha = 10 m³)
        """
        if irrigation_mm <= 0:
            raise ValueError("Irrigation depth must be > 0.")
        if area_ha <= 0:
            raise ValueError("Area must be > 0.")
        return irrigation_mm * area_ha * 10.0

    # ── Formula 6 – proportional dosing ──────────────────────────────────

    @staticmethod
    def dose_volume(volume_m3: float, ratio_l_per_m3: float) -> float:
        """Fertiliser dose volume.
        dose_L = volume_m3 × ratio_L_per_m3
        """
        if volume_m3 <= 0:
            raise ValueError("Irrigation volume must be > 0.")
        if ratio_l_per_m3 <= 0:
            raise ValueError("Dose ratio must be > 0.")
        return volume_m3 * ratio_l_per_m3

    # ── Formula 7 – reverse flow calculation ──────────────────────────────

    @staticmethod
    def reverse_flow_lph(liters_per_pulse: float, time_sec: float) -> float:
        """Derive flow from known pulse interval.
        flow_lph = (L/pulse × 3600) / time_sec
        """
        if liters_per_pulse <= 0:
            raise ValueError("Liters per pulse must be > 0.")
        if time_sec <= 0:
            raise ValueError("Pulse time must be > 0.")
        return (liters_per_pulse * 3600.0) / time_sec

    # ── Formula 8 – status classification ────────────────────────────────

    @staticmethod
    def classify_status(time_sec: float) -> tuple[str, str]:
        """Classify pulse timing quality.  Returns (label, colour_hex).
        < 1 s   → Too Fast
        1–5 s   → Ideal
        5–10 s  → Borderline
        > 10 s  → Low Flow Risk
        """
        if time_sec <= 0:
            return "N/A", "#666666"
        if time_sec < 1.0:
            return "TOO FAST", "#ef6c00"
        if time_sec <= 5.0:
            return "IDEAL", "#2e7d32"
        if time_sec <= 10.0:
            return "BORDERLINE", "#f9a825"
        return "LOW FLOW RISK", "#c62828"

    # ── Formula 9 – multi-valve total flow ───────────────────────────────

    @staticmethod
    def total_flow_lph(num_valves: int, valve_flow_lph: float) -> float:
        """total_flow_LPH = num_valves × valve_flow_LPH"""
        if num_valves <= 0:
            raise ValueError("Number of valves must be > 0.")
        if valve_flow_lph <= 0:
            raise ValueError("Valve flow must be > 0.")
        return num_valves * valve_flow_lph

    # ── Formula 10 – correction factor ───────────────────────────────────

    @staticmethod
    def corrected_time_sec(time_sec: float, factor: float = 1.0) -> float:
        """corrected_time_sec = calculated_time_sec × correction_factor"""
        if time_sec < 0:
            raise ValueError("Time must be >= 0.")
        if factor <= 0:
            raise ValueError("Correction factor must be > 0.")
        return time_sec * factor

    # ── High-level calculators ────────────────────────────────────────────

    @classmethod
    def calculate_irrigation(
        cls, inp: IrrigationProgramInput
    ) -> IrrigationProgramResult:
        """Complete irrigation program calculation.

        Handles duration / mm / m³ program modes.
        WM meters are configured by liters-per-pulse only (no flow rate on the meter).
        """
        errors: list[str] = []

        valve_flow_lph:       float | None = None
        eff_flow_lph:         float | None = None
        volume_m3:            float | None = None
        runtime_h:            float | None = None
        runtime_min:          float | None = None
        runtime_sec_val:      float | None = None
        wm_pulse_ms:          float | None = None
        wm_pulse_sec_val:     float | None = None
        corrected_sec:        float | None = None
        pph:                  float | None = None
        ppm:                  float | None = None
        status = "N/A"
        status_color = "#666666"

        # Valve flow conversion (m³/h → L/h)
        if inp.valve_flow_m3ph <= 0:
            errors.append("Valve flow rate must be > 0.")
        else:
            try:
                valve_flow_lph = cls.m3h_to_lph(inp.valve_flow_m3ph)
                eff_flow_lph = cls.total_flow_lph(inp.num_valves, valve_flow_lph)
            except ValueError as exc:
                errors.append(str(exc))

        # WM liters-per-pulse validation
        if inp.wm_liters_per_pulse <= 0:
            errors.append("WM Liters per pulse must be > 0.")

        # Volume determination from program mode
        if inp.program_value > 0:
            if inp.program_mode == "mm":
                if inp.area_ha > 0:
                    try:
                        volume_m3 = cls.volume_from_mm(inp.program_value, inp.area_ha)
                    except ValueError as exc:
                        errors.append(str(exc))
                else:
                    errors.append("Area (ha) must be > 0 for mm mode.")
            elif inp.program_mode == "m3":
                volume_m3 = inp.program_value
            elif inp.program_mode == "duration":
                # duration in minutes; convert to volume via total flow
                if eff_flow_lph is not None and eff_flow_lph > 0:
                    volume_m3 = (eff_flow_lph * inp.program_value / 60.0) / 1000.0

        # Runtime from volume
        if volume_m3 is not None and inp.valve_flow_m3ph > 0 and inp.num_valves > 0:
            try:
                total_m3ph = inp.valve_flow_m3ph * inp.num_valves
                runtime_h, runtime_min, runtime_sec_val = cls.runtime_from_volume(
                    volume_m3, total_m3ph
                )
            except ValueError as exc:
                errors.append(str(exc))

        # WM pulse timing from total flow
        if eff_flow_lph is not None and inp.wm_liters_per_pulse > 0:
            try:
                wm_pulse_ms = cls.pulse_time_ms(inp.wm_liters_per_pulse, eff_flow_lph)
                wm_pulse_sec_val = wm_pulse_ms / 1000.0
                corrected_sec = cls.corrected_time_sec(
                    wm_pulse_sec_val, inp.correction_factor
                )
                pph = cls.pulses_per_hour(eff_flow_lph, inp.wm_liters_per_pulse)
                ppm = pph / 60.0
                status, status_color = cls.classify_status(wm_pulse_sec_val)
            except ValueError as exc:
                errors.append(str(exc))

        return IrrigationProgramResult(
            valve_flow_lph=valve_flow_lph,
            total_flow_lph=eff_flow_lph,
            volume_m3=volume_m3,
            runtime_hours=runtime_h,
            runtime_minutes=runtime_min,
            runtime_seconds=runtime_sec_val,
            wm_pulse_time_ms=wm_pulse_ms,
            wm_pulse_time_sec=wm_pulse_sec_val,
            corrected_pulse_time_sec=corrected_sec,
            pulses_per_hour=pph,
            pulses_per_minute=ppm,
            status=status,
            status_color=status_color,
            errors=errors,
        )

    @classmethod
    def calculate_dosing(
        cls, inp: DosingProgramInput
    ) -> DosingProgramResult:
        """Complete dosing channel calculation.

        Handles duration / liters program modes.
        DM meters are configured by liters-per-pulse only (no flow rate on the meter).
        """
        errors: list[str] = []

        total_vol_l:     float | None = None
        runtime_h:       float | None = None
        runtime_min_val: float | None = None
        dm_pulse_ms:     float | None = None
        dm_pulse_sec_v:  float | None = None
        pph:             float | None = None
        ppm:             float | None = None
        dose_l:          float | None = None
        status = "N/A"
        status_color = "#666666"

        if inp.channel_flow_lph <= 0:
            errors.append("Channel flow rate must be > 0.")
        if inp.dm_liters_per_pulse <= 0:
            errors.append("DM Liters per pulse must be > 0.")

        # DM pulse timing
        if inp.channel_flow_lph > 0 and inp.dm_liters_per_pulse > 0:
            try:
                dm_pulse_ms = cls.pulse_time_ms(
                    inp.dm_liters_per_pulse, inp.channel_flow_lph
                )
                dm_pulse_sec_v = dm_pulse_ms / 1000.0
                pph = cls.pulses_per_hour(
                    inp.channel_flow_lph, inp.dm_liters_per_pulse
                )
                ppm = pph / 60.0
                status, status_color = cls.classify_status(dm_pulse_sec_v)
            except ValueError as exc:
                errors.append(str(exc))

        # Volume / runtime from program mode
        if inp.program_value > 0:
            if inp.program_mode == "duration":
                if inp.channel_flow_lph > 0:
                    total_vol_l = inp.channel_flow_lph * inp.program_value / 60.0
                    runtime_h = inp.program_value / 60.0
                    runtime_min_val = inp.program_value
            elif inp.program_mode == "liters":
                total_vol_l = inp.program_value
                if inp.channel_flow_lph > 0:
                    runtime_h = inp.program_value / inp.channel_flow_lph
                    runtime_min_val = runtime_h * 60.0

        # Proportional dosing
        if total_vol_l is not None and inp.dose_ratio_l_per_m3 > 0:
            try:
                dose_l = cls.dose_volume(total_vol_l / 1000.0, inp.dose_ratio_l_per_m3)
            except ValueError as exc:
                errors.append(str(exc))

        return DosingProgramResult(
            total_volume_l=total_vol_l,
            runtime_hours=runtime_h,
            runtime_minutes=runtime_min_val,
            dm_pulse_time_ms=dm_pulse_ms,
            dm_pulse_time_sec=dm_pulse_sec_v,
            pulses_per_hour=pph,
            pulses_per_minute=ppm,
            dose_liters=dose_l,
            status=status,
            status_color=status_color,
            errors=errors,
        )
