"""
Server-side wideband O2 sensor (LC-1 / LC-2) voltage-to-AFR rescaling.

Why this lives here (and not in the frontend):
-------------------------------------------------
DynoWare publishes the Innovate LC-1/LC-2 wideband as an **analog voltage**
channel (typically named "LC2 Volts Petrol AFR1" / "LC2 Volts Petrol AFR2").
The raw value on the wire is volts (0-5V), not AFR points.

Every downstream consumer of JetDrive telemetry expects AFR, not volts:

- The ring buffer and live CSV feed :mod:`api.services.jetdrive.jetdrive_live_queue`,
  which in turn feeds :mod:`api.services.jetdrive.jetdrive_realtime_analysis` for
  live VE-delta tracking.
- The workspace analyzer at :mod:`api.services.workspace_analyzer` imports the
  live CSV into :class:`api.services.autotune_workflow.AutoTuneWorkflow`, which
  computes VE corrections via ``afr_error = measured_afr - target_afr``. If the
  "measured AFR" is actually volts (0-5 range vs target ~14.7), the error is
  ~-10 to -14 AFR points and the resulting corrections are hard-pegged garbage.

Prior to this module the conversion lived in a React hook
(``useJetDriveLive.normalizeChannelValue``) and was only applied at the UI
display layer, so the server-side consumers above all silently received volts
as AFR. Real corrections were written against that bad data. That is precisely
the scenario the ``no-physics-in-frontend`` repo rule exists to prevent.

This module is the single source of truth for wideband rescaling. It is
invoked at the ingest boundary (``_live_capture_loop`` in
:mod:`api.routes.jetdrive.hardware`) so every downstream path sees AFR.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WidebandCalibration:
    """Linear voltage-to-AFR calibration for a wideband O2 sensor.

    The Innovate LC-1 and LC-2 both use a default analog mapping of
    ``0.0 V -> 7.35 AFR`` and ``5.0 V -> 22.39 AFR`` for gasoline
    (petrol) stoich. Custom Innovate calibrations can override the
    endpoints in the sensor's programmer software; when a shop uses a
    custom calibration, the env overrides (see :func:`_load_calibration`)
    must be set to match.
    """

    name: str
    v_min: float
    v_max: float
    afr_min: float
    afr_max: float

    @property
    def slope(self) -> float:
        return (self.afr_max - self.afr_min) / (self.v_max - self.v_min)

    @property
    def intercept(self) -> float:
        return self.afr_min - (self.slope * self.v_min)

    def volts_to_afr(self, volts: float) -> float:
        """Apply the linear transfer function. Does not clip; caller decides."""
        return (volts * self.slope) + self.intercept


@dataclass(frozen=True)
class CanonicalizedSample:
    """Result of canonicalizing a wideband voltage channel sample."""

    canonical_name: str
    afr: float
    units: str = "AFR"
    category: str = "afr"


DEFAULT_LC2_PETROL_CALIBRATION = WidebandCalibration(
    name="LC-2 Petrol (default)",
    v_min=0.0,
    v_max=5.0,
    afr_min=7.35,
    afr_max=22.39,
)


def _load_calibration() -> WidebandCalibration:
    """Load calibration from env with a safe default.

    Env overrides (all optional):
        DYNOAI_WIDEBAND_V_MIN / DYNOAI_WIDEBAND_V_MAX
        DYNOAI_WIDEBAND_AFR_MIN / DYNOAI_WIDEBAND_AFR_MAX

    If any env var is set, the full calibration must be set (no mixing).
    """
    env_keys = (
        "DYNOAI_WIDEBAND_V_MIN",
        "DYNOAI_WIDEBAND_V_MAX",
        "DYNOAI_WIDEBAND_AFR_MIN",
        "DYNOAI_WIDEBAND_AFR_MAX",
    )
    env_values = [os.environ.get(k) for k in env_keys]
    if any(v is not None for v in env_values):
        if not all(v is not None for v in env_values):
            missing = [k for k, v in zip(env_keys, env_values) if v is None]
            raise RuntimeError(
                "wideband calibration partially set via env; missing: "
                + ", ".join(missing)
            )
        return WidebandCalibration(
            name="LC-2 Petrol (env override)",
            v_min=float(env_values[0]),
            v_max=float(env_values[1]),
            afr_min=float(env_values[2]),
            afr_max=float(env_values[3]),
        )
    return DEFAULT_LC2_PETROL_CALIBRATION


_CURRENT_CALIBRATION: WidebandCalibration = _load_calibration()


def get_active_calibration() -> WidebandCalibration:
    """Return the currently active wideband calibration (for diagnostics/tests)."""
    return _CURRENT_CALIBRATION


def set_active_calibration(cal: WidebandCalibration) -> None:
    """Override the active calibration. Intended for tests and admin endpoints only."""
    global _CURRENT_CALIBRATION
    _CURRENT_CALIBRATION = cal


def match_wideband_channel(name: str) -> Optional[str]:
    """Detect a DynoWare channel that carries LC-1/LC-2 voltage.

    Returns the canonical target slot (e.g. "AFR Front", "AFR Rear", or
    plain "AFR") when the name matches a known LC voltage channel naming;
    returns None otherwise.

    Recognized forms (case-insensitive, in priority order):

    1. The Innovate-canonical "LC2 Volts Petrol AFR1/2" / "LC1 Volts ...".
       Identified by all three tokens ("volts", "petrol", "afr").
    2. "LC1 Volts AFR1" / "LC2 Volts AFR1/2" forms exported by some
       Power Core / DynoWare configurations that drop "petrol".
       Identified by "lc" + a digit + "volts" + "afr".
    3. "WBO2 F Volts" / "Wideband Volts 1/F" / "Innovate Volts F" /
       "AFR Volts F/1". Identified by "volts" plus a wideband marker
       ("wbo2", "wideband", "innovate") or "afr volts" / "volts afr"
       with a cylinder hint.

    Front vs rear is decided by the cylinder/index hint ("1" / "front" /
    "f" -> front; "2" / "rear" / "r" -> rear). When no hint is present
    the canonical slot is plain "AFR".

    Rigs with non-standard naming that this still misses should configure
    an explicit alias mapping rather than relying on pattern matching.
    """
    if not isinstance(name, str) or not name:
        return None

    lowered = name.lower()
    if "volts" not in lowered:
        return None

    is_innovate_canonical = "petrol" in lowered and "afr" in lowered
    is_lc_short_form = (
        "lc1" in lowered or "lc2" in lowered or "lc-1" in lowered or "lc-2" in lowered
    ) and "afr" in lowered
    is_wb_marker = "wbo2" in lowered or "wideband" in lowered or "innovate" in lowered
    is_afr_volts_form = (
        "afr volts " in f"{lowered} " or " volts afr" in f" {lowered}"
    ) and (
        "1" in lowered
        or "2" in lowered
        or " f " in f" {lowered} "
        or " r " in f" {lowered} "
        or "front" in lowered
        or "rear" in lowered
        or lowered.endswith(" f")
        or lowered.endswith(" r")
    )
    if not (
        is_innovate_canonical or is_lc_short_form or is_wb_marker or is_afr_volts_form
    ):
        return None

    has_front_hint = (
        "front" in lowered
        or "afr1" in lowered
        or "afr 1" in lowered
        or " f " in f" {lowered} "
        or lowered.endswith(" f")
        or "volts 1" in lowered
        or " 1 " in f" {lowered} "
    )
    has_rear_hint = (
        "rear" in lowered
        or "afr2" in lowered
        or "afr 2" in lowered
        or " r " in f" {lowered} "
        or lowered.endswith(" r")
        or "volts 2" in lowered
        or " 2 " in f" {lowered} "
    )

    if has_front_hint and not has_rear_hint:
        return "AFR Front"
    if has_rear_hint and not has_front_hint:
        return "AFR Rear"
    return "AFR"


def _is_voltage_plausible(volts: float, cal: WidebandCalibration) -> bool:
    """Only rescale when the value actually looks like a sensor voltage.

    Guards against accidentally rescaling an already-AFR value if a
    future ingest path mislabels a channel. The allowed range is the
    calibration voltage window extended by 10% on each side to cover
    brief transients at the sensor rails.
    """
    span = cal.v_max - cal.v_min
    pad = span * 0.1
    return (cal.v_min - pad) <= volts <= (cal.v_max + pad)


def canonicalize_wideband_sample(
    channel_name: str,
    raw_value: float,
    *,
    calibration: Optional[WidebandCalibration] = None,
) -> Optional[CanonicalizedSample]:
    """Convert a wideband voltage sample to canonical AFR, if applicable.

    Returns None if the channel name does not match a wideband voltage
    channel, or if the raw value is outside the plausible voltage range.
    Otherwise returns the canonical slot name, the AFR value, and
    canonical units/category metadata ready to be written into the live
    data dictionary.

    This is the single entry point the ingest loop should call. Keep the
    rescale math here, never in a caller.
    """
    canonical = match_wideband_channel(channel_name)
    if canonical is None:
        return None

    try:
        volts = float(raw_value)
    except (TypeError, ValueError):
        return None

    cal = calibration or _CURRENT_CALIBRATION
    if not _is_voltage_plausible(volts, cal):
        return None

    afr = cal.volts_to_afr(volts)
    return CanonicalizedSample(canonical_name=canonical, afr=afr)


__all__ = [
    "WidebandCalibration",
    "CanonicalizedSample",
    "DEFAULT_LC2_PETROL_CALIBRATION",
    "canonicalize_wideband_sample",
    "match_wideband_channel",
    "get_active_calibration",
    "set_active_calibration",
]
