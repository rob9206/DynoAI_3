"""P0 plausibility checks against known displacement and dyno telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PlausibilityResult:
    status: str
    score: int
    checks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "checks": self.checks,
        }


def evaluate_p0_plausibility(
    *,
    known_displacement_ci: float,
    measured_displacement_ci: float | None = None,
    peak_tq_ftlb: float | None = None,
    peak_tq_rpm: float | None = None,
    bmep_psi: float | None = None,
    bsfc_lb_hp_hr: float | None = None,
) -> PlausibilityResult:
    """
    Run conservative P0 plausibility checks.

    Includes:
    - displacement consistency versus known platform value
    - BMEP plausibility band check
    - peak-torque RPM band sanity
    - BSFC plausibility sanity
    """
    checks: list[dict[str, Any]] = []
    score = 100

    if measured_displacement_ci is not None:
        delta = abs(float(measured_displacement_ci) - float(known_displacement_ci))
        ok = delta <= 8.0
        if not ok:
            score -= 20
        checks.append(
            {
                "id": "displacement_consistency",
                "ok": ok,
                "detail": {
                    "known_ci": known_displacement_ci,
                    "measured_ci": measured_displacement_ci,
                    "delta_ci": round(delta, 2),
                },
            }
        )

    derived_bmep = None
    if peak_tq_ftlb is not None:
        derived_bmep = _compute_bmep_psi(
            float(peak_tq_ftlb), float(known_displacement_ci)
        )
        checks.append(
            {
                "id": "bmep_derived",
                "ok": 70.0 <= derived_bmep <= 220.0,
                "detail": {
                    "peak_tq_ftlb": peak_tq_ftlb,
                    "derived_bmep_psi": round(derived_bmep, 2),
                },
            }
        )
        if not (70.0 <= derived_bmep <= 220.0):
            score -= 25

    if bmep_psi is not None:
        bmep_ok = 70.0 <= float(bmep_psi) <= 220.0
        checks.append(
            {
                "id": "bmep_input_band",
                "ok": bmep_ok,
                "detail": {"bmep_psi": bmep_psi},
            }
        )
        if not bmep_ok:
            score -= 20

    if peak_tq_rpm is not None:
        rpm_ok = 2500.0 <= float(peak_tq_rpm) <= 4500.0
        checks.append(
            {
                "id": "peak_tq_rpm_band",
                "ok": rpm_ok,
                "detail": {"peak_tq_rpm": peak_tq_rpm, "expected_band": [2500, 4500]},
            }
        )
        if not rpm_ok:
            score -= 15

    if bsfc_lb_hp_hr is not None:
        bsfc_ok = 0.35 <= float(bsfc_lb_hp_hr) <= 0.75
        checks.append(
            {
                "id": "bsfc_band",
                "ok": bsfc_ok,
                "detail": {
                    "bsfc_lb_hp_hr": bsfc_lb_hp_hr,
                    "expected_band": [0.35, 0.75],
                },
            }
        )
        if not bsfc_ok:
            score -= 15

    if score >= 85:
        status = "pass"
    elif score >= 65:
        status = "warn"
    else:
        status = "fail"
    return PlausibilityResult(status=status, score=score, checks=checks)


def _compute_bmep_psi(torque_ftlb: float, displacement_ci: float) -> float:
    # 4-stroke approximation in psi.
    return (150.8 * torque_ftlb) / displacement_ci
