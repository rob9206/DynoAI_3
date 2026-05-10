"""
Kernel sentinel safety checks for live capture and correction generation.

The sentinel is intentionally conservative:
- It never increases correction authority beyond existing workflow limits.
- It can tighten correction authority per session (`ve_clamp_pct_per_cell`).
- It can emit hard-stop breaches for thermal or lean-streak conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SentinelSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class SentinelBreach:
    code: str
    message: str
    severity: SentinelSeverity
    halt: bool = False


@dataclass
class LambdaTargets:
    # User-approved default for this session family.
    wot: float = 0.88
    cruise_min: Optional[float] = None
    cruise_max: Optional[float] = None
    idle: Optional[float] = None


@dataclass
class KernelSentinelConfig:
    ve_clamp_pct_per_cell: Optional[float] = None
    knock_aware_retract: bool = True
    lambda_targets: LambdaTargets = field(default_factory=LambdaTargets)
    egt_redline_f: Optional[float] = None
    egt_warn_f: Optional[float] = None
    oil_temp_rollback_f: Optional[float] = None
    max_consecutive_lean_cells: Optional[int] = None
    halt_on_breach: bool = True
    afr_error_tolerance: float = 0.3

    @classmethod
    def from_dict(cls, payload: dict | None) -> "KernelSentinelConfig":
        if not payload:
            return cls()

        lambda_payload = payload.get("lambda_targets") or {}
        lambda_targets = LambdaTargets(
            wot=float(lambda_payload.get("wot", 0.88)),
            cruise_min=lambda_payload.get("cruise_min"),
            cruise_max=lambda_payload.get("cruise_max"),
            idle=lambda_payload.get("idle"),
        )

        return cls(
            ve_clamp_pct_per_cell=payload.get("ve_clamp_pct_per_cell"),
            knock_aware_retract=bool(payload.get("knock_aware_retract", True)),
            lambda_targets=lambda_targets,
            egt_redline_f=payload.get("egt_redline_f"),
            egt_warn_f=payload.get("egt_warn_f"),
            oil_temp_rollback_f=payload.get("oil_temp_rollback_f"),
            max_consecutive_lean_cells=payload.get("max_consecutive_lean_cells"),
            halt_on_breach=bool(payload.get("halt_on_breach", True)),
        )


class KernelSentinel:
    """Stateful evaluator for realtime and correction-time safety checks."""

    def __init__(self, config: KernelSentinelConfig | None = None) -> None:
        self.config = config or KernelSentinelConfig()
        self._lean_streak = 0

    def reset(self) -> None:
        self._lean_streak = 0

    def effective_max_correction_pct(self, workflow_limit_pct: float) -> float:
        """
        Never expand authority; only tighten it.
        """
        session_limit = self.config.ve_clamp_pct_per_cell
        if session_limit is None:
            return workflow_limit_pct
        return min(float(workflow_limit_pct), float(session_limit))

    def evaluate_realtime_sample(
        self,
        sample: dict,
        *,
        afr_error: float | None = None,
    ) -> list[SentinelBreach]:
        breaches: list[SentinelBreach] = []
        cfg = self.config

        egt_f = _as_float(sample.get("egt_f"))
        if egt_f is not None:
            if cfg.egt_redline_f is not None and egt_f >= float(cfg.egt_redline_f):
                breaches.append(
                    SentinelBreach(
                        code="egt_redline",
                        message=f"EGT {egt_f:.1f}F exceeds redline {float(cfg.egt_redline_f):.1f}F",
                        severity=SentinelSeverity.CRITICAL,
                        halt=cfg.halt_on_breach,
                    )
                )
            elif cfg.egt_warn_f is not None and egt_f >= float(cfg.egt_warn_f):
                breaches.append(
                    SentinelBreach(
                        code="egt_warn",
                        message=f"EGT {egt_f:.1f}F exceeds warning {float(cfg.egt_warn_f):.1f}F",
                        severity=SentinelSeverity.WARNING,
                        halt=False,
                    )
                )

        oil_temp_f = _as_float(sample.get("oil_temp_f"))
        if (
            oil_temp_f is not None
            and cfg.oil_temp_rollback_f is not None
            and oil_temp_f >= float(cfg.oil_temp_rollback_f)
        ):
            breaches.append(
                SentinelBreach(
                    code="oil_temp_rollback",
                    message=(
                        f"Oil temp {oil_temp_f:.1f}F exceeds rollback threshold "
                        f"{float(cfg.oil_temp_rollback_f):.1f}F"
                    ),
                    severity=SentinelSeverity.CRITICAL,
                    halt=cfg.halt_on_breach,
                )
            )

        lambda_val = _as_float(sample.get("lambda"))
        tps = _as_float(sample.get("tps")) or 0.0
        if (
            lambda_val is not None
            and tps >= 85.0
            and lambda_val > cfg.lambda_targets.wot
        ):
            breaches.append(
                SentinelBreach(
                    code="lambda_wot_lean",
                    message=(
                        f"WOT lambda {lambda_val:.3f} is leaner than target "
                        f"{cfg.lambda_targets.wot:.3f}"
                    ),
                    severity=SentinelSeverity.CRITICAL,
                    halt=cfg.halt_on_breach,
                )
            )

        if cfg.max_consecutive_lean_cells is not None:
            if afr_error is not None and afr_error > cfg.afr_error_tolerance:
                self._lean_streak += 1
            else:
                self._lean_streak = 0

            if self._lean_streak > int(cfg.max_consecutive_lean_cells):
                breaches.append(
                    SentinelBreach(
                        code="lean_streak_exceeded",
                        message=(
                            f"Lean streak {self._lean_streak} exceeds "
                            f"max_consecutive_lean_cells={int(cfg.max_consecutive_lean_cells)}"
                        ),
                        severity=SentinelSeverity.CRITICAL,
                        halt=cfg.halt_on_breach,
                    )
                )

        return breaches

    def evaluate_lean_streak_from_grid(
        self,
        ve_delta_matrix,
        valid_mask,
        *,
        afr_error_tolerance: float,
    ) -> Optional[SentinelBreach]:
        """
        Check for lean runs across MAP columns for any RPM row.

        A lean cell is `ve_delta > afr_error_tolerance` because positive VE delta
        means measured AFR is leaner than target and the workflow wants to add fuel.
        """
        limit = self.config.max_consecutive_lean_cells
        if limit is None:
            return None

        max_run = 0
        rows = ve_delta_matrix.shape[0]
        cols = ve_delta_matrix.shape[1]

        for i in range(rows):
            run = 0
            for j in range(cols):
                if (
                    bool(valid_mask[i, j])
                    and float(ve_delta_matrix[i, j]) > afr_error_tolerance
                ):
                    run += 1
                    max_run = max(max_run, run)
                else:
                    run = 0

        if max_run > int(limit):
            return SentinelBreach(
                code="lean_streak_grid_exceeded",
                message=(
                    f"Lean streak across MAP cells reached {max_run}; "
                    f"limit is {int(limit)}"
                ),
                severity=SentinelSeverity.CRITICAL,
                halt=self.config.halt_on_breach,
            )
        return None


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
