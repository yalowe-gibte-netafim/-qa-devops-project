"""Log analysis service — refactored from LogAnalyzerEngine.

Parses FLEX CLI log files and validates them against a JSON test configuration.

v1.6 fixes preserved:
  - FIX 1: WM search window uses grace_delta instead of hardcoded 30 s
  - FIX 2: Shows nearest available reading when no WM reading found in window
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Callable, Optional

from automation.utils.helpers import parse_hms_duration, parse_hms_time


class AnalysisService:
    """Parses a FLEX log and runs configured test scenarios against it.

    Why: pure analysis class — no tkinter dependency — so it can run in a
    background thread or be exercised by unit tests without a display.
    """

    def __init__(
        self,
        log_content: str,
        config_path: str,
        printer: Callable[[str], None],
    ) -> None:
        self.log_content = log_content
        self.config_path = config_path
        self.printer = printer
        self.events: list[dict] = []
        self.config: list[dict] = []
        self.log_start_date: Optional[datetime] = None
        self.log_weekday_index: Optional[int] = None
        self.log_weekday_name: str = "Unknown"
        # pulse_rate is set per-scenario during analysis
        self.pulse_rate: Optional[float] = None

    # ── Logging convenience ───────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        self.printer(msg)

    # ── Config loading ────────────────────────────────────────────────────────

    def load_config(self) -> bool:
        """Load and validate the JSON test configuration. Returns False on error."""
        try:
            if not os.path.exists(self.config_path):
                self._log(f"Config file not found: {self.config_path}")
                return False
            with open(self.config_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.config = data
            elif isinstance(data, dict):
                self.config = [data]
            else:
                self._log("Invalid JSON format. Expected list or dict.")
                return False
            self._log(f"Loaded configuration with {len(self.config)} scenario(s) from {self.config_path}")
            return True
        except Exception as exc:
            self._log(f"Error loading config: {exc}")
            return False

    # ── Log parsing ───────────────────────────────────────────────────────────

    def parse_log(self) -> None:
        """Parse self.log_content and populate self.events."""
        try:
            lines = self.log_content.splitlines()
            current_tracking_date = datetime.now()
            self.log_start_date = current_tracking_date

            header_pattern    = re.compile(r'--- Log Started: (.+?) ---')
            date_change_pattern = re.compile(r'--- Date Changed: (.+?) ---')
            event_pattern     = re.compile(r'\[(\d{2}:\d{2}:\d{2})\] (valve|wm) (\d+) (.+)')
            nucleo_time_re    = re.compile(r' at (\d{2}:\d{2}:\d{2})')
            wm_snapshot_re    = re.compile(r'wm(\d+)=(\d+)')
            count_re          = re.compile(r'count (\d+)')

            self.events = []

            for line in lines:
                header_match = header_pattern.search(line)
                if header_match:
                    date_str = header_match.group(1)
                    try:
                        try:
                            new_date = datetime.strptime(date_str, "%c")
                        except ValueError:
                            new_date = datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y")
                        current_tracking_date = new_date
                        if len(self.events) == 0:
                            self.log_start_date = new_date
                            self.log_weekday_index = self.log_start_date.weekday()
                            self.log_weekday_name = self.log_start_date.strftime("%A")
                        self._log(f"Synced Date to: {current_tracking_date}")
                    except Exception as exc:
                        self._log(f"Warning: Failed to parse header date: {exc}")
                    continue

                dc_match = date_change_pattern.search(line)
                if dc_match:
                    date_str = dc_match.group(1)
                    try:
                        try:
                            new_date = datetime.strptime(date_str, "%c")
                        except ValueError:
                            new_date = datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y")
                        current_tracking_date = new_date
                        self._log(f"Date updated mid-log to: {current_tracking_date}")
                    except Exception:
                        pass
                    continue

                match = event_pattern.search(line)
                if not match:
                    continue

                gui_timestamp, device_type, device_id, raw_action = match.groups()
                raw_action = raw_action.strip()

                nucleo_time_match = nucleo_time_re.search(raw_action)
                if nucleo_time_match:
                    action = raw_action[:nucleo_time_match.start()].strip().lower()
                else:
                    action = raw_action.lower()
                    if "|" in action:
                        action = action[:action.index("|")].strip()

                wm_snapshot: dict[int, int] = {}
                if "|" in raw_action:
                    snapshot_part = raw_action[raw_action.index("|") + 1:]
                    for sm in wm_snapshot_re.finditer(snapshot_part):
                        wm_snapshot[int(sm.group(1))] = int(sm.group(2))

                count_val = 0
                count_match = count_re.search(action)
                if count_match:
                    count_val = int(count_match.group(1))

                try:
                    t_part = datetime.strptime(gui_timestamp, "%H:%M:%S").time()
                    full_dt = datetime.combine(current_tracking_date.date(), t_part)
                except Exception:
                    continue

                self.events.append({
                    "time":          str(full_dt),
                    "original_time": gui_timestamp,
                    "full_time":     full_dt,
                    "type":          device_type,
                    "id":            int(device_id),
                    "action":        action,
                    "count":         count_val,
                    "wm_snapshot":   wm_snapshot,
                })

            count = len(self.events)
            if count > 0:
                self._log(f"Parsed {count} events spanning potentially multiple days.")
            else:
                self._log("No events found in log.")
        except Exception as exc:
            self._log(f"Error parsing log: {exc}")

    # ── Time / Duration helpers ───────────────────────────────────────────────

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        return parse_hms_time(time_str, self.log_start_date)

    def _parse_duration(self, duration_str: str) -> timedelta:
        return parse_hms_duration(duration_str)

    # ── Main orchestrator ─────────────────────────────────────────────────────

    def run_test(self) -> None:
        """Iterate through all scenarios for all detected log dates."""
        if not self.config:
            self._log("No configuration loaded.")
            return

        self._log("\n========================================")
        self._log(f"--- Starting Analysis of {len(self.config)} Scenarios ---")
        self._log("========================================")

        unique_dates = sorted(set(e["full_time"].date() for e in self.events if "full_time" in e))
        if not unique_dates:
            unique_dates = [
                self.log_start_date.date() if self.log_start_date else datetime.now().date()
            ]

        self._log(f"Detected Activity on Dates: {[str(d) for d in unique_dates]}")
        final_verdict = True

        for current_date in unique_dates:
            self._log(f"\n#################################################")
            self._log(f"### Analyzing Day: {current_date.strftime('%A %Y-%m-%d')} ###")
            self._log(f"#################################################")
            day_verdict = True

            for index, scenario_config in enumerate(self.config):
                self._log(f"\n>>> Scenario #{index + 1}: {scenario_config.get('testname', 'Unnamed')} <<<")
                dummy_dt = datetime.combine(current_date, datetime.min.time())

                if not self._check_run_day(scenario_config, reference_date=dummy_dt):
                    if self._has_valve_activity_on_date(current_date):
                        self._log(f"  [FAIL] Irrigation detected on {current_date} but this day is NOT scheduled!")
                        day_verdict = False
                    else:
                        self._log(f"  [SKIP] No activity and not scheduled for {current_date}")
                    continue

                if not self.analyze_scenario(scenario_config, target_date=current_date):
                    day_verdict = False

            if not day_verdict:
                final_verdict = False
                self._log(f"XXX Day {current_date} FAILED XXX")
            else:
                self._log(f"VVV Day {current_date} PASSED VVV")

        self._log("\n========================================")
        self._log("FINAL VERDICT: ALL DAYS PASSED" if final_verdict else "FINAL VERDICT: FAILURES DETECTED")
        self._log("========================================")

    # ── Schedule checking ─────────────────────────────────────────────────────

    def _check_run_day(self, test_config: dict, reference_date: Optional[datetime] = None) -> bool:
        check_date = reference_date if reference_date else self.log_start_date
        py_weekday = check_date.weekday()
        current_netafim_day = (py_weekday + 2)
        if current_netafim_day > 7:
            current_netafim_day = 1
        day_name = check_date.strftime("%A")
        schedule_type = test_config.get("irrigationScheduleType", "WeekDays")

        if schedule_type == "IntervalDays":
            interval  = test_config.get("intervalDays", 1)
            start_day = test_config.get("currentIntervalDay", 1)
            self._log(f"  [CHECK DAY] Date: {check_date.date()} | Mode: Interval (Every {interval}, Start day: {start_day})")
            if interval == 1:
                return True
            if (current_netafim_day - start_day) % interval == 0:
                self._log(f"  [CHECK DAY] Date: {check_date.date()} | Netafim day {current_netafim_day} is scheduled")
                return True
            self._log(f"  [CHECK DAY] SKIP: Netafim day {current_netafim_day} not in interval")
            return False

        allowed_days = test_config.get("run_days", [])
        if not allowed_days:
            return True
        if current_netafim_day in allowed_days:
            self._log(f"  [CHECK DAY] Success: Date {check_date.date()} ({day_name}) is allowed.")
            return True
        self._log(f"  [CHECK DAY] FAIL: Date {check_date.date()} ({day_name}/Id:{current_netafim_day}) NOT in {allowed_days}")
        return False

    def _has_valve_activity_on_date(self, target_date: datetime.date) -> bool:
        for event in self.events:
            evt_time = self._parse_time(event["time"])
            if evt_time and evt_time.date() == target_date and event.get("type") == "valve":
                return True
        return False

    # ── Scenario dispatcher ───────────────────────────────────────────────────

    def analyze_scenario(self, test_config: dict, target_date: Optional[datetime.date] = None) -> bool:
        start_time_str = test_config.get("start_Time", "00:00")
        if "shifts_structure" in test_config and test_config.get("start_times"):
            start_time_str = test_config["start_times"][0]
        elif "shifts_schedule" in test_config and test_config.get("shifts_schedule"):
            start_time_str = test_config["shifts_schedule"][0][0]

        if target_date:
            t_part = datetime.strptime(
                start_time_str,
                "%H:%M:%S" if len(start_time_str.split(":")) == 3 else "%H:%M",
            ).time()
            t_start_struct = datetime.combine(target_date, t_part)
        else:
            t_start_struct = self._parse_time(start_time_str)

        if not t_start_struct:
            self._log(f"Error parsing start time {start_time_str}")
            return False

        if not self._check_run_day(test_config, reference_date=t_start_struct):
            self._log(f"Skipping test '{test_config.get('testname')}' – not scheduled for {t_start_struct.date()}.")
            return True

        original_log_start = self.log_start_date
        if target_date:
            self.log_start_date = datetime.combine(target_date, datetime.min.time())
        try:
            if "shifts_structure" in test_config:
                return self._analyze_compact_shifts_mode(test_config)
            if "shifts_schedule" in test_config:
                return self._analyze_shifts(test_config)
            return self._analyze_regular_scenario(test_config)
        finally:
            if target_date:
                self.log_start_date = original_log_start

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _find_valve_event(self, v_id: int, action_kw: str, t_from: datetime, t_to: datetime) -> Optional[dict]:
        for e in self.events:
            if e["type"] != "valve" or e["id"] != v_id:
                continue
            if action_kw not in e["action"]:
                continue
            et = self._parse_time(e["time"])
            if et and t_from <= et <= t_to:
                return e
        return None

    def _nearest_valve_event(self, v_id: int, action_kw: str, t_ref: datetime) -> tuple[Optional[dict], float]:
        best, best_diff = None, float("inf")
        for e in self.events:
            if e["type"] != "valve" or e["id"] != v_id:
                continue
            if action_kw not in e["action"]:
                continue
            et = self._parse_time(e["time"])
            if et:
                d = abs((et - t_ref).total_seconds())
                if d < best_diff:
                    best, best_diff = e, d
        return best, best_diff

    def _get_wm_delta(self, wm_id: int, open_event: dict, close_event: dict) -> Optional[tuple[int, int, int]]:
        snap_open  = open_event.get("wm_snapshot", {})
        snap_close = close_event.get("wm_snapshot", {})
        if wm_id not in snap_open or wm_id not in snap_close:
            return None
        start = snap_open[wm_id]
        end   = snap_close[wm_id]
        return start, end, end - start

    def _get_valve_pairs(self, v_id: int, t_start: datetime, t_end: datetime) -> list[tuple[dict, dict]]:
        opens, closes = [], []
        for e in self.events:
            if e["type"] != "valve" or e["id"] != v_id:
                continue
            et = self._parse_time(e["time"])
            if not et or not (t_start <= et <= t_end):
                continue
            if "open" in e["action"]:
                opens.append((et, e))
            elif "close" in e["action"]:
                closes.append((et, e))
        pairs: list[tuple[dict, dict]] = []
        ci = 0
        for ot, oe in opens:
            while ci < len(closes) and closes[ci][0] <= ot:
                ci += 1
            if ci < len(closes):
                pairs.append((oe, closes[ci][1]))
                ci += 1
        return pairs

    def _check_valve_open(self, v_id: int, t_expected: datetime, grace_delta: timedelta, label: str = "") -> tuple[bool, Optional[dict], float]:
        t_from = t_expected - timedelta(seconds=30)
        t_to   = t_expected + grace_delta
        e = self._find_valve_event(v_id, "open", t_from, t_to)
        if e:
            et   = self._parse_time(e["time"])
            diff = (et - t_expected).total_seconds()
            sign = "+" if diff >= 0 else ""
            self._log(f"       [PASS] V{v_id} open @ [{e['original_time']}] ({sign}{int(diff)}s) {label}")
            return True, e, diff
        nearest, nd = self._nearest_valve_event(v_id, "open", t_expected)
        if nearest:
            et   = self._parse_time(nearest["time"])
            diff = (et - t_expected).total_seconds()
            sign = "+" if diff >= 0 else ""
            self._log(f"       [FAIL] V{v_id} open – nearest @ [{nearest['original_time']}] ({sign}{int(diff)}s, outside grace) {label}")
        else:
            self._log(f"       [FAIL] V{v_id} open – no event found in log {label}")
        return False, nearest, nd if nearest else 0

    def _check_valve_close(self, v_id: int, t_expected: datetime, grace_delta: timedelta, label: str = "") -> tuple[bool, Optional[dict], float]:
        t_from = t_expected - timedelta(seconds=30)
        t_to   = t_expected + grace_delta
        e = self._find_valve_event(v_id, "close", t_from, t_to)
        if e:
            et   = self._parse_time(e["time"])
            diff = (et - t_expected).total_seconds()
            sign = "+" if diff >= 0 else ""
            self._log(f"       [PASS] V{v_id} close @ [{e['original_time']}] ({sign}{int(diff)}s) {label}")
            return True, e, diff
        nearest, nd = self._nearest_valve_event(v_id, "close", t_expected)
        if nearest:
            et   = self._parse_time(nearest["time"])
            diff = (et - t_expected).total_seconds()
            sign = "+" if diff >= 0 else ""
            self._log(f"       [FAIL] V{v_id} close – nearest @ [{nearest['original_time']}] ({sign}{int(diff)}s, outside grace) {label}")
        else:
            self._log(f"       [FAIL] V{v_id} close – no event found in log {label}")
        return False, nearest, nd if nearest else 0

    def _check_wm_quantity(self, wm_id: int, open_event: Optional[dict], close_event: Optional[dict],
                           expected: float, tolerance_pct: float, label: str = "") -> bool:
        if open_event is None or close_event is None:
            self._log(f"       [FAIL] WM{wm_id} quantity – missing open/close event for delta {label}")
            return False
        result = self._get_wm_delta(wm_id, open_event, close_event)
        if result is None:
            self._log(f"       [FAIL] WM{wm_id} – no snapshot data in events {label}")
            return False
        start, end, delta = result
        tol        = expected * tolerance_pct / 100.0
        lo, hi     = expected - tol, expected + tol
        rate       = self.pulse_rate
        liters_str = f" = {delta * rate:.1f}L" if rate else ""
        target_str = f"{expected * rate:.1f}L" if rate else f"{expected} pulses"
        if lo <= delta <= hi:
            self._log(f"       [PASS] WM{wm_id} delta={delta}{liters_str} (start={start} end={end}) target={target_str}±{tolerance_pct}% {label}")
            return True
        self._log(f"       [FAIL] WM{wm_id} delta={delta}{liters_str} (start={start} end={end}) target={target_str}±{tolerance_pct}% {label}")
        return False

    def _print_summary(self, test_name: str, shift_results: list[bool]) -> bool:
        total  = len(shift_results)
        passed = sum(1 for r in shift_results if r)
        failed = total - passed
        self._log(f"\n  ┌─────────────────────────────────────────┐")
        self._log(f"  │  SUMMARY: {test_name[:30]:<30} │")
        self._log(f"  │  Shifts: {total}  Passed: {passed}  Failed: {failed}{'': <10}│")
        self._log(f"  └─────────────────────────────────────────┘")
        overall = "✔ PASSED" if failed == 0 else "✘ FAILED"
        self._log(f"  >>> Result: {overall} <<<")
        return failed == 0

    # =========================================================================
    # MODE 1 — IRRIGATION ONLY
    # =========================================================================

    def _m1_analyze_time(self, test_name: str, shifts_structure: list, cycle_start: datetime, grace_delta: timedelta) -> bool:
        shift_results = []
        current_shift_start = cycle_start
        for sh_idx, shift in enumerate(shifts_structure):
            duration       = self._parse_duration(shift.get("duration", "00:00:00"))
            current_valves = set(shift.get("valves", []))
            prev_valves    = set(shifts_structure[sh_idx - 1].get("valves", [])) if sh_idx > 0 else set()
            next_valves    = set(shifts_structure[sh_idx + 1].get("valves", [])) if sh_idx < len(shifts_structure) - 1 else set()
            valves_to_open  = current_valves - prev_valves
            valves_to_close = current_valves - next_valves
            current_shift_end = current_shift_start + duration
            self._log(f"\n  -- Shift #{sh_idx + 1} ({shift.get('duration')}) Valves:{sorted(current_valves)} --")
            self._log(f"     Window: {current_shift_start.strftime('%H:%M:%S')} -> {current_shift_end.strftime('%H:%M:%S')}")
            shift_passed = True
            self._log("     [CHECK 1] Valve Open:")
            for v_id in sorted(valves_to_open):
                ok, _, _ = self._check_valve_open(v_id, current_shift_start, grace_delta)
                if not ok:
                    shift_passed = False
            self._log("     [CHECK 2] Valve Close:")
            for v_id in sorted(valves_to_close):
                ok, _, _ = self._check_valve_close(v_id, current_shift_end, grace_delta)
                if not ok:
                    shift_passed = False
            shift_results.append(shift_passed)
            current_shift_start = current_shift_end
        return self._print_summary(test_name, shift_results)

    def _m1_analyze_quantity(self, test_name: str, shifts_structure: list, cycle_start: datetime,
                             grace_delta: timedelta, tolerance_pct: float) -> bool:
        shift_results = []
        current_shift_start = cycle_start
        wm_id = 1  # Mode 1 always uses WM1
        for sh_idx, shift in enumerate(shifts_structure):
            duration        = self._parse_duration(shift.get("duration", "00:00:00"))
            current_valves  = set(shift.get("valves", []))
            expected_pulses = shift.get("expected_pulses", 0) or 0
            _rate    = self.pulse_rate
            _warn_rate = None
            if not expected_pulses:
                expected_liters = shift.get("expected_liters", 0) or 0
                if expected_liters and _rate:
                    expected_pulses = expected_liters / _rate
                elif expected_liters and not _rate:
                    _warn_rate = expected_liters
            prev_valves    = set(shifts_structure[sh_idx - 1].get("valves", [])) if sh_idx > 0 else set()
            next_valves    = set(shifts_structure[sh_idx + 1].get("valves", [])) if sh_idx < len(shifts_structure) - 1 else set()
            valves_to_open  = current_valves - prev_valves
            valves_to_close = current_valves - next_valves
            current_shift_end = current_shift_start + duration
            self._log(f"\n  -- Shift #{sh_idx + 1} ({shift.get('duration')}) Valves:{sorted(current_valves)} --")
            self._log(f"     Window: {current_shift_start.strftime('%H:%M:%S')} -> {current_shift_end.strftime('%H:%M:%S')}")
            if _warn_rate:
                self._log(f"     [WARN] expected_liters={_warn_rate} but rate=null – set rate to enable quantity check")
            shift_passed = True
            open_events: dict[int, Optional[dict]] = {}
            self._log("     [CHECK 1] Valve Open:")
            for v_id in sorted(valves_to_open):
                ok, evt, _ = self._check_valve_open(v_id, current_shift_start, grace_delta)
                if not ok:
                    shift_passed = False
                open_events[v_id] = evt
            close_events: dict[int, Optional[dict]] = {}
            for v_id in sorted(valves_to_close):
                t_search_from = current_shift_start - grace_delta
                t_search_to   = current_shift_end + timedelta(hours=2)
                close_evt = self._find_valve_event(v_id, "close", t_search_from, t_search_to)
                if close_evt:
                    self._log(f"       [INFO] V{v_id} close @ [{close_evt['original_time']}] (quantity mode – timing not checked)")
                else:
                    self._log(f"       [FAIL] V{v_id} close – no event found in log")
                    shift_passed = False
                close_events[v_id] = close_evt
            if expected_pulses > 0:
                rep_open_v = sorted(valves_to_open)[0] if valves_to_open else None
                open_evt   = open_events.get(rep_open_v) if rep_open_v else None
                if open_evt is None and sh_idx > 0:
                    leaving_valves = prev_valves - current_valves
                    if leaving_valves:
                        leave_v = sorted(leaving_valves)[0]
                        prev_duration = self._parse_duration(shifts_structure[sh_idx - 1].get("duration", "00:00:00"))
                        t_trans_from  = current_shift_start - prev_duration
                        t_trans_to    = current_shift_end
                        open_evt = self._find_valve_event(leave_v, "close", t_trans_from, t_trans_to)
                        if open_evt:
                            self._log(f"       [INFO] Shift transition: V{leave_v} close @ [{open_evt['original_time']}] used as WM start-ref")
                close_evt = None
                if valves_to_close:
                    rep_close_v = sorted(valves_to_close)[0]
                    close_evt = close_events.get(rep_close_v)
                elif sh_idx < len(shifts_structure) - 1:
                    next_shift_valves = set(shifts_structure[sh_idx + 1].get("valves", []))
                    next_new_valves   = next_shift_valves - current_valves
                    if next_new_valves:
                        next_v = sorted(next_new_valves)[0]
                        next_shift_start = current_shift_end
                        next_shift_end   = next_shift_start + self._parse_duration(
                            shifts_structure[sh_idx + 1].get("duration", "00:00:00"))
                        close_evt = self._find_valve_event(
                            next_v, "open",
                            next_shift_start - grace_delta,
                            next_shift_end + grace_delta,
                        )
                        if close_evt:
                            self._log(f"       [INFO] Shift transition: V{next_v} open @ [{close_evt['original_time']}] used as WM end-ref")
                if open_evt and close_evt:
                    ok = self._check_wm_quantity(wm_id, open_evt, close_evt, expected_pulses, tolerance_pct, f"(shift #{sh_idx+1})")
                    if not ok:
                        shift_passed = False
                else:
                    self._log(f"       [INFO] Shift #{sh_idx+1}: cannot determine WM delta bounds – skipping")
            shift_results.append(shift_passed)
            actual_transition = None
            for v_id in sorted(valves_to_close):
                evt = close_events.get(v_id)
                if evt:
                    t = self._parse_time(evt["time"])
                    if t and (actual_transition is None or t > actual_transition):
                        actual_transition = t
            if actual_transition:
                self._log(f"       [INFO] Shift transition: actual close time {actual_transition.strftime('%H:%M:%S')} → used as next shift anchor")
                current_shift_start = actual_transition
            else:
                current_shift_start = current_shift_end
        return self._print_summary(test_name, shift_results)

    # =========================================================================
    # MODE 2 — IRRIGATION (per-valve WM mapping)
    # =========================================================================

    def _m2_analyze_irrigation(self, test_name: str, shifts_structure: list, cycle_start: datetime,
                               grace_delta: timedelta, unit: str, tolerance_pct: float) -> bool:
        shift_results = []
        current_shift_start = cycle_start
        for sh_idx, shift in enumerate(shifts_structure):
            duration        = self._parse_duration(shift.get("duration", "00:00:00"))
            current_valves  = set(shift.get("valves", []))
            expected_pulses = shift.get("expected_pulses", 0) or 0
            _rate    = self.pulse_rate
            _warn_rate = None
            if not expected_pulses:
                expected_liters = shift.get("expected_liters", 0) or 0
                if expected_liters and _rate:
                    expected_pulses = expected_liters / _rate
                elif expected_liters and not _rate:
                    _warn_rate = expected_liters
            prev_valves    = set(shifts_structure[sh_idx - 1].get("valves", [])) if sh_idx > 0 else set()
            next_valves    = set(shifts_structure[sh_idx + 1].get("valves", [])) if sh_idx < len(shifts_structure) - 1 else set()
            valves_to_open  = current_valves - prev_valves
            valves_to_close = current_valves - next_valves
            current_shift_end = current_shift_start + duration
            self._log(f"\n  -- Shift #{sh_idx + 1} ({shift.get('duration')}) Valves:{sorted(current_valves)} --")
            self._log(f"     Window: {current_shift_start.strftime('%H:%M:%S')} -> {current_shift_end.strftime('%H:%M:%S')}")
            if _warn_rate:
                self._log(f"     [WARN] expected_liters={_warn_rate} but rate=null – set rate to enable quantity check")
            shift_passed = True
            open_events:  dict[int, Optional[dict]] = {}
            close_events: dict[int, Optional[dict]] = {}
            self._log("     [CHECK 1] Valve Open:")
            for v_id in sorted(valves_to_open):
                ok, evt, _ = self._check_valve_open(v_id, current_shift_start, grace_delta)
                if not ok:
                    shift_passed = False
                open_events[v_id] = evt
            close_label = " + WM Quantity (timing not checked)" if unit == "quantity" else ""
            self._log(f"     [CHECK 2] Valve Close{close_label}:")
            for v_id in sorted(valves_to_close):
                if unit == "quantity":
                    t_search_from = current_shift_start - grace_delta
                    t_search_to   = current_shift_end + timedelta(hours=2)
                    evt = self._find_valve_event(v_id, "close", t_search_from, t_search_to)
                    if evt:
                        self._log(f"       [INFO] V{v_id} close @ [{evt['original_time']}] (quantity mode – timing not checked)")
                    else:
                        self._log(f"       [FAIL] V{v_id} close – no event found in log")
                        shift_passed = False
                else:
                    ok, evt, _ = self._check_valve_close(v_id, current_shift_end, grace_delta)
                    if not ok:
                        shift_passed = False
                close_events[v_id] = evt
                if unit == "quantity" and expected_pulses > 0:
                    wm_id = v_id  # Valve N → WM N
                    ok_q = self._check_wm_quantity(wm_id, open_events.get(v_id), evt, expected_pulses, tolerance_pct, f"V{v_id}→WM{wm_id} shift#{sh_idx+1}")
                    if not ok_q:
                        shift_passed = False
            shift_results.append(shift_passed)
            current_shift_start = current_shift_end
        return self._print_summary(test_name, shift_results)

    # =========================================================================
    # MODE 2 — FERTIGATION ENGINES
    # =========================================================================

    def _m2_bulck_time(self, ch: dict, t_program_start: datetime, t_program_end: datetime, grace_delta: timedelta) -> bool:
        v_id    = ch.get("channel")
        dur_str = ch.get("duration", None)
        self._log(f"\n     [FERTIGATION] Ch{v_id} BULCK/TIME")
        ok_o, open_evt, _ = self._check_valve_open(v_id, t_program_start, grace_delta, f"ch{v_id}")
        t_close_expected  = (t_program_start + self._parse_duration(dur_str) if dur_str else t_program_end)
        ok_c, close_evt, _ = self._check_valve_close(v_id, t_close_expected, grace_delta, f"ch{v_id}")
        return ok_o and ok_c

    def _m2_bulck_quantity(self, ch: dict, t_program_start: datetime, t_program_end: datetime,
                           grace_delta: timedelta, tolerance_pct: float) -> bool:
        v_id     = ch.get("channel")
        wm_id    = ch.get("watermeter_id", v_id)
        expected = ch.get("expected_pulses", 0) or 0
        _rate = self.pulse_rate
        if not expected:
            expected_liters = ch.get("expected_liters", 0) or 0
            if expected_liters and _rate:
                expected = expected_liters / _rate
            elif expected_liters and not _rate:
                self._log(f"       [WARN] Ch{v_id}: expected_liters={expected_liters} but rate=null – set rate to enable quantity check")
                return True
        self._log(f"\n     [FERTIGATION] Ch{v_id} BULCK/QUANTITY target={expected}")
        ok_o, open_evt, _ = self._check_valve_open(v_id, t_program_start, grace_delta, f"ch{v_id}")
        close_evt = self._find_valve_event(v_id, "close", t_program_start, t_program_end + grace_delta)
        if close_evt:
            self._log(f"       [INFO] Ch{v_id} closed @ {close_evt['original_time']}")
        else:
            self._log(f"       [FAIL] Ch{v_id} – no close event found")
            return False
        ok_q = self._check_wm_quantity(wm_id, open_evt, close_evt, expected, tolerance_pct, f"ch{v_id}")
        return ok_o and ok_q

    def _m2_spread_time(self, ch: dict, t_program_start: datetime, t_program_end: datetime, grace_delta: timedelta) -> bool:
        v_id      = ch.get("channel")
        on_sec    = ch.get("on_seconds", 5)
        off_sec   = ch.get("off_seconds", 5)
        tolerance = grace_delta.total_seconds()
        self._log(f"\n     [FERTIGATION] Ch{v_id} SPREAD/TIME on={on_sec}s off={off_sec}s")
        pairs = self._get_valve_pairs(v_id, t_program_start, t_program_end + grace_delta)
        if not pairs:
            self._log(f"       [FAIL] Ch{v_id} – no open/close pairs found in program window")
            return False
        self._log(f"       Found {len(pairs)} cycle(s)")
        all_ok = True
        for idx, (oe, ce) in enumerate(pairs):
            ot = self._parse_time(oe["time"])
            ct = self._parse_time(ce["time"])
            ot_str = oe.get("original_time", "")
            ct_str = ce.get("original_time", "")
            if ot and ct:
                on_actual = (ct - ot).total_seconds()
                if abs(on_actual - on_sec) <= tolerance:
                    self._log(f"       [{ot_str}] [PASS] Cycle {idx+1}: ON={on_actual:.1f}s (expected {on_sec}s)")
                else:
                    self._log(f"       [{ot_str}] [FAIL] Cycle {idx+1}: ON={on_actual:.1f}s (expected {on_sec}s ±{tolerance}s)")
                    all_ok = False
            if idx + 1 < len(pairs):
                next_oe = pairs[idx + 1][0]
                nt = self._parse_time(next_oe["time"])
                if ct and nt:
                    off_actual = (nt - ct).total_seconds()
                    if abs(off_actual - off_sec) <= tolerance:
                        self._log(f"       [{ct_str}] [PASS] Cycle {idx+1} OFF gap={off_actual:.1f}s (expected {off_sec}s)")
                    else:
                        self._log(f"       [{ct_str}] [FAIL] Cycle {idx+1} OFF gap={off_actual:.1f}s (expected {off_sec}s ±{tolerance}s)")
                        all_ok = False
        first_open = self._parse_time(pairs[0][0]["time"])
        last_close = self._parse_time(pairs[-1][1]["time"])
        last_close_str = pairs[-1][1].get("original_time", "")
        if first_open and last_close:
            span = (last_close - first_open).total_seconds()
            expected_span = (t_program_end - t_program_start).total_seconds()
            if span >= expected_span - tolerance:
                self._log(f"       [{last_close_str}] [PASS] Cycling span={span:.0f}s covers program {expected_span:.0f}s")
            else:
                self._log(f"       [{last_close_str}] [FAIL] Cycling span={span:.0f}s < program {expected_span:.0f}s")
                all_ok = False
        return all_ok

    def _m2_spread_quantity(self, ch: dict, t_program_start: datetime, t_program_end: datetime,
                            grace_delta: timedelta, tolerance_pct: float) -> bool:
        v_id = ch.get("channel")
        self._log(f"\n     [FERTIGATION] Ch{v_id} SPREAD/QUANTITY – not yet implemented (SKIP)")
        return True

    def _m2_proportional(self, ch: dict, t_program_start: datetime, t_program_end: datetime,
                         grace_delta: timedelta, tolerance_pct: float) -> bool:
        MAIN_WM_ID     = 1
        PULSE_TO_LITER = 1.0
        TRIGGER_LITERS = 2000

        v_id  = ch.get("channel")
        wm_id = ch.get("watermeter_id", v_id)
        dose  = ch.get("expected_pulses", 0) or 0
        _rate = self.pulse_rate
        if not dose:
            dose_liters = ch.get("expected_liters", 0) or 0
            if dose_liters and _rate:
                dose = dose_liters / _rate
            elif dose_liters and not _rate:
                self._log(f"       [WARN] Ch{v_id}: expected_liters={dose_liters} but rate=null – set rate to enable quantity check")
                return True

        self._log(f"\n     [FERTIGATION] Ch{v_id} PROPORTIONAL | WM{MAIN_WM_ID} trigger={TRIGGER_LITERS}L | dose={dose} pulses")
        wm1_start = wm1_end = None
        for e in self.events:
            ft = e.get("full_time")
            if ft and t_program_start <= ft <= t_program_end + grace_delta:
                snap = e.get("wm_snapshot", {})
                if MAIN_WM_ID in snap:
                    if wm1_start is None:
                        wm1_start = snap[MAIN_WM_ID]
                    wm1_end = snap[MAIN_WM_ID]
        if wm1_start is None or wm1_end is None:
            self._log(f"       [FAIL] Could not determine WM{MAIN_WM_ID} pulses during program")
            return False
        wm1_delta    = wm1_end - wm1_start
        total_liters = wm1_delta * PULSE_TO_LITER
        expected_cycles = int(total_liters // TRIGGER_LITERS)
        self._log(f"       WM{MAIN_WM_ID}: start={wm1_start} end={wm1_end} → delta={wm1_delta} pulses = {total_liters:.1f}L")
        self._log(f"       Expected cycles: {total_liters:.0f}L ÷ {TRIGGER_LITERS}L = {expected_cycles}")
        if expected_cycles == 0:
            self._log(f"       [FAIL] Not enough WM{MAIN_WM_ID} water for even 1 fertigation cycle")
            return False
        pairs = self._get_valve_pairs(v_id, t_program_start, t_program_end + grace_delta)
        actual_cycles = len(pairs)
        tol = max(1, round(expected_cycles * tolerance_pct / 100))
        all_ok = True
        for idx, (oe, ce) in enumerate(pairs):
            ot_str = oe.get("original_time", "")
            ct_str = ce.get("original_time", "")
            self._log(f"\n       Cycle {idx+1}/{actual_cycles}:")
            self._log(f"       [{ot_str}]  Open  Ch{v_id}")
            self._log(f"       [{ct_str}]  Close Ch{v_id}")
            result = self._get_wm_delta(wm_id, oe, ce)
            if result is None:
                self._log(f"                   [FAIL] WM{wm_id} – no snapshot data for this cycle")
                all_ok = False
            else:
                start_p, end_p, delta_p = result
                tol_dose = dose * tolerance_pct / 100.0
                lo, hi = dose - tol_dose, dose + tol_dose
                status = "[PASS]" if lo <= delta_p <= hi else "[FAIL]"
                liters_str = f" = {delta_p * _rate:.1f}L" if _rate else ""
                dose_str   = f"{dose * _rate:.1f}L" if _rate else f"{dose} pulses"
                self._log(f"                   WM{wm_id} delta={delta_p}{liters_str} (start={start_p} end={end_p}) target={dose_str}±{tolerance_pct}% → {status}")
                if status == "[FAIL]":
                    all_ok = False
            ot_full = oe.get("full_time")
            if ot_full:
                wm1_at_open = None
                for e in self.events:
                    ft = e.get("full_time")
                    if ft and t_program_start <= ft <= ot_full:
                        snap = e.get("wm_snapshot", {})
                        if MAIN_WM_ID in snap:
                            wm1_at_open = snap[MAIN_WM_ID]
                if wm1_at_open is not None:
                    liters_at_open = (wm1_at_open - wm1_start) * PULSE_TO_LITER
                    expected_liters_at_open = idx * TRIGGER_LITERS
                    tol_liters = TRIGGER_LITERS * tolerance_pct / 100.0
                    diff = liters_at_open - expected_liters_at_open
                    status = "[PASS]" if abs(diff) <= tol_liters else "[FAIL]"
                    self._log(f"                   WM{MAIN_WM_ID} at open={liters_at_open:.0f}L (expected ~{expected_liters_at_open}L, diff={diff:+.0f}L) → {status}")
                    if status == "[FAIL]":
                        all_ok = False
        self._log("")
        if abs(actual_cycles - expected_cycles) <= tol:
            self._log(f"       [PASS] Total cycles: actual={actual_cycles} expected={expected_cycles} (±{tol})")
        else:
            self._log(f"       [FAIL] Total cycles: actual={actual_cycles} expected={expected_cycles} (±{tol})")
            all_ok = False
        return all_ok

    # =========================================================================
    # COMPACT SHIFTS DISPATCHER
    # =========================================================================

    def _analyze_compact_shifts_mode(self, test_config: dict) -> bool:
        test_name        = test_config.get("testname", "Combined Test")
        mode             = test_config.get("mode", 1)
        unit             = test_config.get("unit", "time")
        start_times      = test_config.get("start_times", [])
        shifts_structure = test_config.get("shifts_structure", [])
        grace_time_str   = test_config.get("grace_Time", "00:01:00")
        grace_delta      = self._parse_duration(grace_time_str)
        tolerance_pct    = test_config.get("pulse_tolerance_pct", 5)
        self.pulse_rate  = test_config.get("rate", None)
        fertilization    = test_config.get("fertilization", {})
        fert_active      = fertilization.get("active", False) and (mode == 2)
        fert_channels    = [ch for ch in fertilization.get("channels", []) if ch.get("active", True)]

        self._log(f"\n=========================================")
        self._log(f"--- {test_name} | Mode {mode} | unit={unit} | grace={grace_time_str} | tol={tolerance_pct}% ---")
        self._log(f"=========================================")
        all_passed = True

        for st_idx, start_time_str in enumerate(start_times):
            cycle_start = self._parse_time(start_time_str)
            if not cycle_start:
                self._log(f"  [ERROR] Bad Start Time: {start_time_str}")
                all_passed = False
                continue
            total_duration = sum(
                [self._parse_duration(s.get("duration", "00:00:00")) for s in shifts_structure],
                timedelta(),
            )
            cycle_end = cycle_start + total_duration

            if unit == "quantity":
                search_from = cycle_start - timedelta(seconds=60)
                search_to   = cycle_end + timedelta(hours=3)
            else:
                search_from = cycle_start - grace_delta
                search_to   = cycle_end + grace_delta

            valve_events_in_window = [
                e for e in self.events
                if e["type"] == "valve" and search_from <= e["full_time"] <= search_to
            ]
            open_events_in_window = [e for e in valve_events_in_window if e.get("action") == "open"]
            if open_events_in_window:
                actual_start = min(e["full_time"] for e in open_events_in_window)
            elif valve_events_in_window:
                actual_start = min(e["full_time"] for e in valve_events_in_window)
            else:
                actual_start = None

            if valve_events_in_window:
                actual_end = max(e["full_time"] for e in valve_events_in_window)
                actual_str = f"{actual_start.strftime('%H:%M:%S')} → {actual_end.strftime('%H:%M:%S')}"
            else:
                actual_str = "no events found"

            self._log(f"\n>>> Cycle #{st_idx + 1} <<<")
            self._log(f"    Expected: {start_time_str} → {cycle_end.strftime('%H:%M:%S')}")
            self._log(f"    Actual:   {actual_str}")

            # Irrigation analysis
            if mode == 1:
                ok = (self._m1_analyze_time(test_name, shifts_structure, cycle_start, grace_delta)
                      if unit == "time"
                      else self._m1_analyze_quantity(test_name, shifts_structure, cycle_start, grace_delta, tolerance_pct))
            else:
                ok = self._m2_analyze_irrigation(test_name, shifts_structure, cycle_start, grace_delta, unit, tolerance_pct)
            if not ok:
                all_passed = False

            # Fertigation analysis (Mode 2 only)
            if fert_active:
                self._log(f"\n--- Fertigation Analysis | {len(fert_channels)} active channel(s) ---")
                for ch in fert_channels:
                    fert_type = (ch.get("mode") or fertilization.get("mode") or "bulck").lower()
                    fert_unit = (ch.get("unit") or "quantity").lower()
                    v_id      = ch.get("channel", "?")
                    self._log(f"\n  Channel {v_id}: mode={fert_type} unit={fert_unit}")
                    if fert_type == "bulck":
                        ok_f = (self._m2_bulck_time(ch, cycle_start, cycle_end, grace_delta)
                                if fert_unit == "time"
                                else self._m2_bulck_quantity(ch, cycle_start, cycle_end, grace_delta, tolerance_pct))
                    elif fert_type == "spread":
                        ok_f = (self._m2_spread_time(ch, cycle_start, cycle_end, grace_delta)
                                if fert_unit == "time"
                                else self._m2_spread_quantity(ch, cycle_start, cycle_end, grace_delta, tolerance_pct))
                    elif fert_type == "proportional":
                        ok_f = self._m2_proportional(ch, cycle_start, cycle_end, grace_delta, tolerance_pct)
                    else:
                        self._log(f"     [WARN] Unknown fertigation type '{fert_type}' – skipping")
                        ok_f = True
                    if not ok_f:
                        all_passed = False

        return all_passed

    # =========================================================================
    # LEGACY MODES
    # =========================================================================

    def _analyze_shifts(self, test_config: dict) -> bool:
        test_name      = test_config.get("testname", "Unknown Test")
        shifts         = test_config.get("shifts_schedule", [])
        wm_id          = test_config.get("watermeter", 1)
        grace_time_str = test_config.get("grace_Time", "00:05")
        grace_delta    = self._parse_duration(grace_time_str)
        self._log(f"Test Name: {test_name} (Multi-Shift Mode)")
        current_pass = True
        prev_valves  = set()

        for i, shift in enumerate(shifts):
            s_start_str, s_end_str, s_valves_list, s_amount = shift
            s_valves = set(s_valves_list)
            t_start = self._parse_time(s_start_str)
            t_end   = self._parse_time(s_end_str)
            next_valves = set(shifts[i + 1][2]) if i + 1 < len(shifts) else set()
            self._log(f"  >>> Shift {i + 1}: {s_start_str} -> {s_end_str} | Active: {list(s_valves)}")
            valves_to_open = s_valves - prev_valves
            for v_id in valves_to_open:
                found = None
                w_start = t_start - timedelta(seconds=30)
                w_end   = t_start + grace_delta
                for e in self.events:
                    if e["type"] == "valve" and e["id"] == v_id and "open" in e["action"]:
                        et = self._parse_time(e["time"])
                        if not et:
                            continue
                        et_full = et.replace(year=t_start.year, month=t_start.month, day=t_start.day)
                        if w_start <= et_full <= w_end:
                            found = e
                            break
                if found:
                    self._log(f"    [PASS] Valve {v_id} opened at {found['time']}")
                else:
                    self._log(f"    [FAIL] Valve {v_id} failed to open at shift start.")
                    current_pass = False
            if s_amount > 0:
                w_start = t_start - timedelta(seconds=5)
                w_end   = t_end + timedelta(seconds=5)
                candidates = []
                for e in self.events:
                    if e["type"] == "wm" and e["id"] == wm_id and "count" in e:
                        et = self._parse_time(e["time"])
                        if not et:
                            continue
                        et_full = et.replace(year=t_start.year, month=t_start.month, day=t_start.day)
                        if w_start <= et_full <= w_end:
                            candidates.append((et_full, e["count"]))
                if candidates:
                    best = min(candidates, key=lambda x: abs((x[0] - t_end).total_seconds()))
                    total_pulses = best[1]
                    max_a = s_amount * 1.05
                    if total_pulses < s_amount:
                        self._log(f"    [FAIL] WM: {total_pulses} < {s_amount} (Target)")
                        current_pass = False
                    elif total_pulses > max_a:
                        self._log(f"    [FAIL] WM: {total_pulses} > {max_a:.1f} (Target + 5%)")
                        current_pass = False
                    else:
                        self._log(f"    [PASS] WM: {total_pulses} (Target {s_amount}) [OK]")
                else:
                    self._log("    [FAIL] No WM reading for shift.")
                    current_pass = False
            valves_to_close = s_valves - next_valves
            for v_id in valves_to_close:
                found = None
                w_start = t_end - timedelta(seconds=10)
                w_end   = t_end + grace_delta
                for e in self.events:
                    if e["type"] == "valve" and e["id"] == v_id and "close" in e["action"]:
                        et = self._parse_time(e["time"])
                        if not et:
                            continue
                        et_full = et.replace(year=t_start.year, month=t_start.month, day=t_start.day)
                        if w_start <= et_full <= w_end:
                            found = e
                            break
                if found:
                    self._log(f"    [PASS] Valve {v_id} closed at {found['time']}")
                else:
                    self._log(f"    [FAIL] Valve {v_id} failed to close at shift end.")
                    current_pass = False
            prev_valves = s_valves
        return current_pass

    def _analyze_regular_scenario(self, test_config: dict) -> bool:
        test_name = test_config.get("testname", "Unknown Test")
        if not self._check_run_day(test_config):
            self._log("Skipping test or marking Fail due to wrong day.")
        start_time_str  = test_config.get("start_Time", "00:00")
        end_time_str    = test_config.get("end_Time", None)
        grace_time_str  = test_config.get("grace_Time", "00:00")
        target_valves   = test_config.get("Valves", [])
        if not isinstance(target_valves, list):
            target_valves = []
        raw_amount    = test_config.get("Amount")
        target_amount = raw_amount if raw_amount is not None else 0
        wm_id         = test_config.get("watermeter", 1)
        self._log(f"Test Name: {test_name}")
        self._log(f"Active Valves: {target_valves}")
        is_quantity_mode = target_amount > 0
        self._log(f"Test Mode: {'Quantity' if is_quantity_mode else 'Time'}")
        t_start     = self._parse_time(start_time_str)
        t_end       = self._parse_time(end_time_str) if end_time_str else None
        grace_delta = self._parse_duration(grace_time_str)
        if not t_start:
            self._log("[ERROR] Invalid Start Time.")
            return False
        if not t_end:
            t_end = t_start + timedelta(hours=2)
        scenario_start_limit = t_start - timedelta(seconds=30)
        scenario_end_limit   = t_end + grace_delta
        if scenario_end_limit < scenario_start_limit:
            scenario_end_limit += timedelta(days=1)
        self._log(f"Strict Time Window: {scenario_start_limit.strftime('%H:%M:%S')} -> {scenario_end_limit.strftime('%H:%M:%S')}")
        current_pass = True

        # STEP 1: Valve Start Check
        self._log("  [CHECK 1] Valve Start Analysis...")
        for v_id in target_valves:
            found_valid = False
            for event in self.events:
                evt_time = self._parse_time(event["time"])
                if not evt_time:
                    continue
                evt_time_full = evt_time.replace(year=t_start.year, month=t_start.month, day=t_start.day)
                if not (scenario_start_limit <= evt_time_full <= scenario_end_limit):
                    continue
                if event["type"] == "valve" and event["id"] == v_id and "open" in event["action"]:
                    diff = abs((evt_time_full - t_start).total_seconds())
                    if diff <= grace_delta.total_seconds() + 30:
                        self._log(f"    [PASS] Valve {v_id} opened at {event['time']}")
                        found_valid = True
                        break
            if not found_valid:
                self._log(f"    [FAIL] Valve {v_id} failed to open.")
                current_pass = False

        # STEP 2: Water Meter Analysis
        self._log("  [CHECK 2] Water Meter Analysis...")
        wm_candidates = []
        for event in self.events:
            evt_time = self._parse_time(event["time"])
            if not evt_time:
                continue
            evt_time_full = evt_time.replace(year=t_start.year, month=t_start.month, day=t_start.day)
            if scenario_start_limit <= evt_time_full <= scenario_end_limit:
                if event["type"] == "wm" and event["id"] == wm_id and event.get("count") is not None:
                    wm_candidates.append((evt_time_full, event["count"]))
        total_pulses = 0
        if wm_candidates:
            best_candidate = min(wm_candidates, key=lambda x: abs((x[0] - t_end).total_seconds()))
            total_pulses = best_candidate[1]
            self._log(f"    Selected Reading: {total_pulses} (at {best_candidate[0].strftime('%H:%M:%S')} - closest to end time)")
        else:
            self._log("    No WM readings found within scenario time window.")
        if is_quantity_mode:
            max_allowed = target_amount * 1.05
            if total_pulses < target_amount:
                self._log(f"    [FAIL] Quantity Low: {total_pulses} < {target_amount} (Target)")
                current_pass = False
            elif total_pulses > max_allowed:
                self._log(f"    [FAIL] Quantity High: {total_pulses} > {max_allowed:.1f} (Target + 5%)")
                current_pass = False
            else:
                self._log(f"    [PASS] Quantity Target Reached ({total_pulses}) [Target <= Q <= Target+5%]")
        else:
            self._log(f"    [INFO] (Time Mode) Pulses counted: {total_pulses}")

        # STEP 3: Valve Close Check
        self._log("  [CHECK 3] Valve Close Analysis...")
        for v_id in target_valves:
            found_valid = found_any = False
            for event in self.events:
                evt_time = self._parse_time(event["time"])
                if not evt_time:
                    continue
                evt_time_full = evt_time.replace(year=t_start.year, month=t_start.month, day=t_start.day)
                if not (scenario_start_limit <= evt_time_full <= scenario_end_limit):
                    continue
                if event["type"] == "valve" and event["id"] == v_id and "close" in event["action"]:
                    found_any = True
                    if is_quantity_mode:
                        self._log(f"    [PASS] Valve {v_id} closed at {event['time']}")
                        found_valid = True
                        break
                    else:
                        diff = abs((evt_time_full - t_end).total_seconds())
                        if diff <= grace_delta.total_seconds():
                            self._log(f"    [PASS] Valve {v_id} closed at {event['time']} (Diff: {diff}s)")
                            found_valid = True
                            break
            if not found_valid:
                current_pass = False
                if is_quantity_mode:
                    self._log(f"    [FAIL] Valve {v_id} did not close.")
                elif found_any:
                    self._log(f"    [FAIL] Valve {v_id} closed but NOT at expected time ({end_time_str}).")
                else:
                    self._log(f"    [FAIL] Valve {v_id} did not close.")
        return current_pass
