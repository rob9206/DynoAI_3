"""InjectorMismatchDetector: tune scalars disagree with vehicle profile.

Tune-as-data detector that flags configuration mismatches between the
PVV's declared hardware scalars and the profile's declared hardware.

Per AGENTS.md: "When stock ECU or download baselines disagree on
displacement, stoich, or fuel table references, reconcile against the
user's stated hardware and fuel before trusting a single file's defaults;
a wrong displacement in the base tune masks itself by inflating VE
during autotune."

This detector implements that reconciliation. It treats the profile as
the source of truth — if the customer's `vehicles/<vid>/profile.json`
says `displacement_ci = 95.5` but the PVV declares 103, the *tune* is
the one that needs to be rebased, not the profile.

Signals checked:
  - `tbl_engine_displacement` (PVV) vs `profile["displacement_ci"]`
  - `tbl_injector_size` (PVV) vs `profile["injector_size_lb_hr"]` if
    declared (optional — most profiles don't carry injector size yet)

Fires `injector_calibration` finding routed to `injector_scalar_rebase`,
binding `displacement_cid` (and optionally `injector_gps`) in
`tool_params` so the tool rebases to the profile's declared values.

Severity:
  - 0..5%   mismatch : no finding
  - 5..10%  mismatch : 0.30 -> 0.55 (mild)
  - 10..20% mismatch : 0.55 -> 0.80 (moderate)
  - >20%    mismatch : 0.80 -> 1.00 (severe)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Mapping, Tuple

from dynoai.diagnostics.detector import DetectionContext
from dynoai.diagnostics.finding import Finding
from dynoai.pvv.io import parse_scalar


_INJECTOR_CALIB_KIND = "injector_calibration"
_INJECTOR_REBASE_TOOL = "injector_scalar_rebase"
_LB_HR_PER_G_PER_SEC = 3600.0 / 453.59237


def _mismatch_pct(declared: float, in_tune: float) -> float:
    if declared <= 0:
        return 0.0
    return abs(declared - in_tune) / declared * 100.0


def _severity_from_mismatch(pct: float, min_pct: float) -> float:
    p = float(pct)
    if p < min_pct:
        return 0.0
    if p <= 10.0:
        span = max(10.0 - min_pct, 1e-9)
        return 0.30 + (p - min_pct) * (0.55 - 0.30) / span
    if p <= 20.0:
        return 0.55 + (p - 10.0) * (0.80 - 0.55) / 10.0
    if p <= 40.0:
        return 0.80 + (p - 20.0) * (1.00 - 0.80) / 20.0
    return 1.0


class InjectorMismatchDetector:
    """Detect tune scalar mismatches vs vehicle profile declared hardware.

    Reads two scalars from the base PVV and compares to profile.json.
    Emits one Finding when displacement disagrees beyond the threshold;
    if the profile also declares injector size, the same finding's
    tool_params bind the injector target too.
    """

    name = "injector_mismatch_detector"
    fix_kinds: Tuple[str, ...] = (_INJECTOR_CALIB_KIND,)

    def __init__(
        self,
        *,
        displacement_id: str = "tbl_engine_displacement",
        injector_id: str = "tbl_injector_size",
        min_mismatch_pct: float = 5.0,
        profile_displacement_key: str = "displacement_ci",
        profile_injector_lb_hr_key: str = "injector_size_lb_hr",
    ) -> None:
        if min_mismatch_pct <= 0.0:
            raise ValueError("min_mismatch_pct must be > 0")
        self.displacement_id = displacement_id
        self.injector_id = injector_id
        self.min_mismatch_pct = float(min_mismatch_pct)
        self.profile_displacement_key = profile_displacement_key
        self.profile_injector_lb_hr_key = profile_injector_lb_hr_key

    def detect(self, ctx: DetectionContext) -> List[Finding]:
        if ctx.base_pvv_path is None or not ctx.base_pvv_path.exists():
            return []
        profile = ctx.vehicle_profile or {}
        declared_disp = profile.get(self.profile_displacement_key)
        if declared_disp is None:
            # No profile-side declaration -> nothing to compare against.
            return []

        try:
            declared_disp_f = float(declared_disp)
        except (TypeError, ValueError):
            return []
        if declared_disp_f <= 0:
            return []

        root = ET.parse(ctx.base_pvv_path).getroot()
        try:
            tune_disp = parse_scalar(root, self.displacement_id)
        except ValueError:
            return []
        try:
            tune_inj = parse_scalar(root, self.injector_id)
        except ValueError:
            tune_inj = None  # not all tunes have this scalar

        disp_pct = _mismatch_pct(declared_disp_f, tune_disp)
        if disp_pct < self.min_mismatch_pct:
            return []

        # Severity dominated by displacement mismatch since that's what we have.
        severity = _severity_from_mismatch(disp_pct, self.min_mismatch_pct)
        confidence = 0.95  # profile.json declared values are high-confidence

        tool_params: Dict[str, Any] = {
            "displacement_cid": declared_disp_f,
        }
        # If profile also carries an injector size, bind that too.
        declared_inj_lb_hr = profile.get(self.profile_injector_lb_hr_key)
        inj_pct: float | None = None
        if declared_inj_lb_hr is not None and tune_inj is not None:
            try:
                declared_inj_f = float(declared_inj_lb_hr)
                inj_pct = _mismatch_pct(declared_inj_f, tune_inj)
                tool_params["injector_gps"] = declared_inj_f / _LB_HR_PER_G_PER_SEC
                # Bump severity if both mismatch compoundingly.
                severity = min(
                    1.0,
                    severity + 0.5 * _severity_from_mismatch(inj_pct, self.min_mismatch_pct),
                )
            except (TypeError, ValueError):
                inj_pct = None

        return [
            Finding(
                kind=_INJECTOR_CALIB_KIND,
                severity=severity,
                confidence=confidence,
                evidence={
                    "declared_displacement_ci": declared_disp_f,
                    "tune_displacement_ci": tune_disp,
                    "displacement_mismatch_pct": disp_pct,
                    "tune_injector_lb_hr": tune_inj,
                    "declared_injector_lb_hr": (
                        float(declared_inj_lb_hr)
                        if declared_inj_lb_hr is not None else None
                    ),
                    "injector_mismatch_pct": inj_pct,
                    "min_mismatch_pct": self.min_mismatch_pct,
                },
                suggested_tool=_INJECTOR_REBASE_TOOL,
                tool_params=tool_params,
                source="injector_mismatch_detector",
            )
        ]
