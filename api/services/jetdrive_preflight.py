"""
JetDrive Preflight Module

Validates data quality and correctness before starting a dyno session.
Prevents wasted dyno time by catching configuration issues upfront.

Preflight Checks:
1. Connectivity: Provider discovered and responsive
2. Required Channels: RPM, at least one AFR channel
3. Recommended Channels: MAP, TPS, Torque, Power
4. Health Thresholds: Freshness < 2s, rate > 5 samples/sec
5. Semantic Validation: Detects mislabeled/swapped channels

Usage:
    from api.services.jetdrive_preflight import run_preflight, PreflightResult

    result = await run_preflight(
        provider_id=0x1234,  # Optional, auto-discover if not specified
        sample_seconds=15,
        mode="blocking"  # or "advisory"
    )

    if not result.passed:
        print("Preflight failed:", result.get_failure_summary())
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Required channels (must have at least one from each group)
REQUIRED_CHANNEL_GROUPS = {
    "rpm": [
        "Engine RPM",
        "Digital RPM 1",
        "Digital RPM 2",
        "RPM",
        "chan_10",
        "chan_11",
    ],
    "afr": [
        "Air/Fuel Ratio 1",
        "Air/Fuel Ratio 2",
        "AFR",
        "AFR Meas F",
        "AFR Meas R",
        "Lambda 1",
        "Lambda 2",
        "chan_15",
        "chan_16",
    ],
}

# Recommended channels (nice to have, warn if missing)
RECOMMENDED_CHANNELS = {
    "map": ["MAP kPa", "MAP", "Manifold Pressure", "chan_20"],
    "tps": ["TPS", "Throttle Position", "chan_21"],
    "torque": ["Torque", "chan_3"],
    "power": ["Horsepower", "Power", "chan_4"],
}

# Health thresholds
FRESHNESS_THRESHOLD_SEC = 2.0  # Data must be newer than this
MIN_SAMPLE_RATE_HZ = 5.0  # Minimum acceptable sample rate
MAX_DROP_RATE_PCT = 10.0  # Maximum acceptable frame drop rate

# Semantic validation ranges (for gasoline)
SEMANTIC_RANGES = {
    "rpm": (500, 12000),  # Plausible RPM range
    "afr": (10.0, 20.0),  # Plausible AFR range (gasoline)
    "lambda": (0.68, 1.36),  # Plausible lambda range
    "tps": (0, 100),  # TPS percentage
    "map": (10, 250),  # MAP in kPa
}

# Power/Torque/RPM relationship constant (HP = Torque * RPM / 5252)
POWER_CONSTANT = 5252

# =============================================================================
# Data Classes
# =============================================================================


class CheckStatus(Enum):
    """Status of a preflight check."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PreflightCheck:
    """Result of a single preflight check."""

    name: str
    status: CheckStatus
    message: str
    fix_suggestion: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "fix_suggestion": self.fix_suggestion,
            "details": self.details,
        }


@dataclass
class MislabelSuspicion:
    """Suspected channel mislabeling."""

    channel_name: str
    expected_type: str  # What we expected (e.g., "rpm")
    observed_behavior: str  # What we observed (e.g., "values 12-15, AFR-like")
    confidence: float  # 0.0 to 1.0
    fix_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "expected_type": self.expected_type,
            "observed_behavior": self.observed_behavior,
            "confidence": self.confidence,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class PreflightResult:
    """Result of the complete preflight check."""

    passed: bool
    provider_id: int | None
    provider_name: str | None
    provider_host: str | None
    checks: list[PreflightCheck]
    missing_channels: list[str]
    suspected_mislabels: list[MislabelSuspicion]
    can_override: bool  # True for advisory mode
    mode: str  # "blocking" or "advisory"
    sample_seconds: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "provider_host": self.provider_host,
            "checks": [c.to_dict() for c in self.checks],
            "missing_channels": self.missing_channels,
            "suspected_mislabels":
            [m.to_dict() for m in self.suspected_mislabels],
            "can_override": self.can_override,
            "mode": self.mode,
            "sample_seconds": self.sample_seconds,
            "timestamp": self.timestamp,
        }

    def get_failed_checks(self) -> list[PreflightCheck]:
        """Get all failed checks."""
        return [c for c in self.checks if c.status == CheckStatus.FAILED]

    def get_warning_checks(self) -> list[PreflightCheck]:
        """Get all warning checks."""
        return [c for c in self.checks if c.status == CheckStatus.WARNING]

    def get_failure_summary(self) -> str:
        """Get a human-readable summary of failures."""
        if self.passed:
            return "All checks passed"

        lines = []
        for check in self.get_failed_checks():
            lines.append(f"FAIL: {check.name} - {check.message}")
            if check.fix_suggestion:
                lines.append(f"  Fix: {check.fix_suggestion}")

        for mislabel in self.suspected_mislabels:
            lines.append(
                f"MISLABEL: {mislabel.channel_name} - {mislabel.observed_behavior}"
            )
            lines.append(f"  Fix: {mislabel.fix_suggestion}")

        return "\n".join(lines)


# =============================================================================
# Preflight Check Functions
# =============================================================================


async def _check_connectivity(
        config: Any,
        requested_provider_id: int | None,
        timeout: float = 10.0) -> tuple[PreflightCheck, Any]:
    """
    Check 1: Provider connectivity.

    Discovers providers and optionally filters to requested provider.
    """
    from api.services.jetdrive_client import discover_providers

    try:
        providers = await discover_providers(config, timeout=timeout)

        if not providers:
            return (
                PreflightCheck(
                    name="connectivity",
                    status=CheckStatus.FAILED,
                    message="No JetDrive providers found on network",
                    fix_suggestion=(
                        "1. Verify DynoWare RT is powered on and connected\n"
                        "2. Check that JetDrive is enabled in Power Core\n"
                        "3. Verify network cable and multicast routing"),
                    details={"providers_found": 0},
                ),
                None,
            )

        # Find requested provider or use first
        provider = None
        if requested_provider_id is not None:
            for p in providers:
                if p.provider_id == requested_provider_id:
                    provider = p
                    break
            if provider is None:
                available = [f"0x{p.provider_id:04X}" for p in providers]
                return (
                    PreflightCheck(
                        name="connectivity",
                        status=CheckStatus.FAILED,
                        message=f"Requested provider 0x{requested_provider_id:04X} not found",
                        fix_suggestion=f"Available providers: {', '.join(available)}",
                        details={
                            "requested_provider_id": requested_provider_id,
                            "available_providers": available,
                        },
                    ),
                    None,
                )
        else:
            provider = providers[0]

        return (
            PreflightCheck(
                name="connectivity",
                status=CheckStatus.PASSED,
                message=f"Connected to {provider.name} (0x{provider.provider_id:04X})",
                details={
                    "provider_id": provider.provider_id,
                    "provider_name": provider.name,
                    "provider_host": provider.host,
                    "channel_count": len(provider.channels),
                },
            ),
            provider,
        )

    except Exception as e:
        logger.error(f"Connectivity check failed: {e}", exc_info=True)
        return (
            PreflightCheck(
                name="connectivity",
                status=CheckStatus.FAILED,
                message=f"Network error: {str(e)}",
                fix_suggestion="Check network configuration and firewall settings",
                details={"error": str(e)},
            ),
            None,
        )


def _check_required_channels(
        available_channels: set[str], ) -> tuple[PreflightCheck, list[str]]:
    """
    Check 2: Required channels present.

    Checks that at least one channel from each required group is present.
    """
    missing_groups = []
    found_channels = {}

    for group_name, channel_names in REQUIRED_CHANNEL_GROUPS.items():
        found = None
        for name in channel_names:
            if name in available_channels:
                found = name
                break
        if found:
            found_channels[group_name] = found
        else:
            missing_groups.append(group_name)

    if missing_groups:
        # Build fix suggestion based on what's missing
        fix_parts = []
        if "rpm" in missing_groups:
            fix_parts.append(
                "Enable RPM channel in Power Core JetDrive settings")
        if "afr" in missing_groups:
            fix_parts.append("Enable AFR/Lambda channel in Power Core")

        return (
            PreflightCheck(
                name="required_channels",
                status=CheckStatus.FAILED,
                message=f"Missing required channel groups: {', '.join(missing_groups)}",
                fix_suggestion="\n".join(fix_parts),
                details={
                    "missing_groups": missing_groups,
                    "found_channels": found_channels,
                },
            ),
            missing_groups,
        )

    return (
        PreflightCheck(
            name="required_channels",
            status=CheckStatus.PASSED,
            message=f"Required channels found: {', '.join(found_channels.values())}",
            details={"found_channels": found_channels},
        ),
        [],
    )


def _check_recommended_channels(
        available_channels: set[str], ) -> PreflightCheck:
    """
    Check 3: Recommended channels present.

    Warns if recommended channels are missing but doesn't fail.
    """
    missing_groups = []
    found_channels = {}

    for group_name, channel_names in RECOMMENDED_CHANNELS.items():
        found = None
        for name in channel_names:
            if name in available_channels:
                found = name
                break
        if found:
            found_channels[group_name] = found
        else:
            missing_groups.append(group_name)

    if missing_groups:
        return PreflightCheck(
            name="recommended_channels",
            status=CheckStatus.WARNING,
            message=f"Missing recommended channels: {', '.join(missing_groups)}",
            fix_suggestion="Consider enabling these channels in Power Core for better analysis",
            details={
                "missing_groups": missing_groups,
                "found_channels": found_channels,
            },
        )

    return PreflightCheck(
        name="recommended_channels",
        status=CheckStatus.PASSED,
        message=f"All recommended channels found",
        details={"found_channels": found_channels},
    )


def _check_health_thresholds(
        validator_health: dict[str, Any], ) -> PreflightCheck:
    """
    Check 4: Health thresholds met.

    Checks freshness, sample rate, and drop rate.
    """
    issues = []
    details = {}

    # Check overall health
    overall = validator_health.get("overall_health", "unknown")
    if overall == "critical":
        issues.append("Overall health is critical")
    elif overall == "stale":
        issues.append("Data is stale (no recent samples)")

    # Check frame drop rate
    frame_stats = validator_health.get("frame_stats", {})
    drop_rate = frame_stats.get("drop_rate_percent", 0)
    if drop_rate > MAX_DROP_RATE_PCT:
        issues.append(f"Frame drop rate too high: {drop_rate:.1f}%")
    details["drop_rate_percent"] = drop_rate

    # Check individual channel health
    channels = validator_health.get("channels", {})
    unhealthy_channels = []
    for channel_key, channel_data in channels.items():
        health = channel_data.get("health", "unknown")
        if health in ("stale", "critical", "invalid"):
            unhealthy_channels.append(channel_key)

    if unhealthy_channels:
        issues.append(f"{len(unhealthy_channels)} unhealthy channels")
        details["unhealthy_channels"] = unhealthy_channels

    details["healthy_channels"] = validator_health.get("healthy_channels", 0)
    details["total_channels"] = validator_health.get("total_channels", 0)

    if issues:
        return PreflightCheck(
            name="health_thresholds",
            status=CheckStatus.FAILED
            if "critical" in overall else CheckStatus.WARNING,
            message="; ".join(issues),
            fix_suggestion="Ensure dyno is running and data is flowing",
            details=details,
        )

    return PreflightCheck(
        name="health_thresholds",
        status=CheckStatus.PASSED,
        message="All health thresholds met",
        details=details,
    )


def _run_semantic_checks(
    sample_buffer: dict[str, list[float]],
) -> tuple[PreflightCheck, list[MislabelSuspicion]]:
    """
    Check 5: Semantic validation.

    Detects mislabeled/swapped channels by checking value plausibility.
    """
    suspicions: list[MislabelSuspicion] = []
    checks_performed = []

    # Helper to get channel data by matching any of multiple names
    def get_channel_data(names: list[str]) -> tuple[str | None, list[float]]:
        for name in names:
            if name in sample_buffer and sample_buffer[name]:
                return name, sample_buffer[name]
        return None, []

    # Check RPM channel
    rpm_name, rpm_data = get_channel_data(REQUIRED_CHANNEL_GROUPS["rpm"])
    if rpm_data:
        checks_performed.append("rpm_range")
        rpm_min, rpm_max = min(rpm_data), max(rpm_data)
        rpm_mean = statistics.mean(rpm_data)

        # RPM should be in plausible range
        if rpm_max < SEMANTIC_RANGES["rpm"][0] or rpm_min > SEMANTIC_RANGES[
                "rpm"][1]:
            # Values look completely wrong
            if SEMANTIC_RANGES["afr"][0] <= rpm_mean <= SEMANTIC_RANGES["afr"][
                    1]:
                suspicions.append(
                    MislabelSuspicion(
                        channel_name=rpm_name,
                        expected_type="rpm",
                        observed_behavior=f"Values {rpm_min:.1f}-{rpm_max:.1f} look like AFR (expected 500-12000)",
                        confidence=0.9,
                        fix_suggestion=f"Remap RPM in Power Core - current channel has AFR-like values",
                    ))
            else:
                suspicions.append(
                    MislabelSuspicion(
                        channel_name=rpm_name,
                        expected_type="rpm",
                        observed_behavior=f"Values {rpm_min:.1f}-{rpm_max:.1f} outside plausible range",
                        confidence=0.7,
                        fix_suggestion=f"Verify RPM channel mapping in Power Core",
                    ))

        # RPM should not be constant (frozen sensor)
        if len(rpm_data) > 10:
            rpm_stddev = statistics.stdev(rpm_data)
            if rpm_stddev < 1.0:  # Essentially constant
                suspicions.append(
                    MislabelSuspicion(
                        channel_name=rpm_name,
                        expected_type="rpm",
                        observed_behavior=f"RPM appears frozen at {rpm_mean:.0f}",
                        confidence=0.8,
                        fix_suggestion="Check RPM sensor connection",
                    ))

    # Check AFR channel
    afr_name, afr_data = get_channel_data(REQUIRED_CHANNEL_GROUPS["afr"])
    if afr_data:
        checks_performed.append("afr_range")
        afr_min, afr_max = min(afr_data), max(afr_data)
        afr_mean = statistics.mean(afr_data)

        # Check if values look like lambda instead of AFR
        if SEMANTIC_RANGES["lambda"][0] <= afr_mean <= SEMANTIC_RANGES[
                "lambda"][1]:
            # Looks like lambda, not AFR
            suspicions.append(
                MislabelSuspicion(
                    channel_name=afr_name,
                    expected_type="afr",
                    observed_behavior=f"Values {afr_min:.2f}-{afr_max:.2f} look like Lambda (expected 10-20 for AFR)",
                    confidence=0.85,
                    fix_suggestion="Enable Lambda-to-AFR conversion or use AFR channel",
                ))
        elif afr_max < SEMANTIC_RANGES["afr"][0] or afr_min > SEMANTIC_RANGES[
                "afr"][1]:
            # Values outside AFR range
            if SEMANTIC_RANGES["rpm"][0] <= afr_mean <= SEMANTIC_RANGES["rpm"][
                    1]:
                suspicions.append(
                    MislabelSuspicion(
                        channel_name=afr_name,
                        expected_type="afr",
                        observed_behavior=f"Values {afr_min:.1f}-{afr_max:.1f} look like RPM (expected 10-20)",
                        confidence=0.9,
                        fix_suggestion=f"Remap AFR in Power Core - current channel has RPM-like values",
                    ))

    # Check TPS channel (if present)
    tps_channels = RECOMMENDED_CHANNELS.get("tps", [])
    tps_name, tps_data = get_channel_data(tps_channels)
    if tps_data:
        checks_performed.append("tps_range")
        tps_min, tps_max = min(tps_data), max(tps_data)

        if tps_max > 100 or tps_min < 0:
            suspicions.append(
                MislabelSuspicion(
                    channel_name=tps_name,
                    expected_type="tps",
                    observed_behavior=f"Values {tps_min:.1f}-{tps_max:.1f} outside 0-100% range",
                    confidence=0.8,
                    fix_suggestion="Verify TPS channel mapping - values should be 0-100%",
                ))

    # Check Power/Torque/RPM relationship (if all three present)
    power_name, power_data = get_channel_data(
        RECOMMENDED_CHANNELS.get("power", []))
    torque_name, torque_data = get_channel_data(
        RECOMMENDED_CHANNELS.get("torque", []))

    if power_data and torque_data and rpm_data:
        checks_performed.append("power_torque_rpm")
        # Calculate expected power from torque and RPM
        # HP = Torque (ft-lb) * RPM / 5252
        # Use mean values for sanity check
        mean_power = statistics.mean(power_data)
        mean_torque = statistics.mean(torque_data)
        mean_rpm = statistics.mean(rpm_data)

        if mean_rpm > 100 and mean_torque > 0:
            expected_power = mean_torque * mean_rpm / POWER_CONSTANT
            power_diff_pct = (abs(mean_power - expected_power) /
                              max(expected_power, 1) * 100)

            if power_diff_pct > 50:  # More than 50% off
                suspicions.append(
                    MislabelSuspicion(
                        channel_name=f"{power_name}/{torque_name}",
                        expected_type="power_torque_relationship",
                        observed_behavior=(f"Power ({mean_power:.1f}) doesn't match Torque*RPM/5252 "
                                           f"({expected_power:.1f}), {power_diff_pct:.0f}% difference"
                                           ),
                        confidence=0.7,
                        fix_suggestion="Verify Power and Torque channel mappings and units",
                    ))

    # Build result
    if suspicions:
        high_confidence = [s for s in suspicions if s.confidence >= 0.8]
        if high_confidence:
            return (
                PreflightCheck(
                    name="semantic_validation",
                    status=CheckStatus.FAILED,
                    message=f"Detected {len(suspicions)} suspected channel mislabel(s)",
                    fix_suggestion="Review channel mappings in Power Core",
                    details={
                        "checks_performed": checks_performed,
                        "suspicion_count": len(suspicions),
                    },
                ),
                suspicions,
            )
        else:
            return (
                PreflightCheck(
                    name="semantic_validation",
                    status=CheckStatus.WARNING,
                    message=f"Possible channel issues detected (low confidence)",
                    fix_suggestion="Review channel mappings if data looks wrong",
                    details={
                        "checks_performed": checks_performed,
                        "suspicion_count": len(suspicions),
                    },
                ),
                suspicions,
            )

    return (
        PreflightCheck(
            name="semantic_validation",
            status=CheckStatus.PASSED,
            message=f"Semantic checks passed ({len(checks_performed)} checks)",
            details={"checks_performed": checks_performed},
        ),
        [],
    )


# =============================================================================
# Main Preflight Function
# =============================================================================


async def run_preflight(
    provider_id: int | None = None,
    sample_seconds: int = 15,
    mode: str = "blocking",
) -> PreflightResult:
    """
    Run complete preflight check sequence.

    Args:
        provider_id: Optional provider ID to use. If None, auto-discovers.
        sample_seconds: How long to sample data for semantic checks.
        mode: "blocking" (must pass) or "advisory" (warn but allow override)

    Returns:
        PreflightResult with all check results
    """
    from api.services.jetdrive_client import JetDriveConfig, subscribe
    from api.services.jetdrive_validation import get_validator

    config = JetDriveConfig.from_env()
    validator = get_validator()

    checks: list[PreflightCheck] = []
    missing_channels: list[str] = []
    suspicions: list[MislabelSuspicion] = []

    # Check 1: Connectivity
    logger.info(
        f"Preflight: Checking connectivity (provider_id={provider_id})...")
    connectivity_check, provider = await _check_connectivity(
        config, provider_id)
    checks.append(connectivity_check)

    if provider is None:
        # Can't proceed without a provider
        return PreflightResult(
            passed=False,
            provider_id=None,
            provider_name=None,
            provider_host=None,
            checks=checks,
            missing_channels=[],
            suspected_mislabels=[],
            can_override=mode == "advisory",
            mode=mode,
            sample_seconds=sample_seconds,
        )

    # Get available channels from provider
    available_channels = set()
    for chan in provider.channels.values():
        available_channels.add(chan.name)
        available_channels.add(f"chan_{chan.chan_id}")

    # Check 2: Required channels
    logger.info("Preflight: Checking required channels...")
    required_check, missing_groups = _check_required_channels(
        available_channels)
    checks.append(required_check)
    missing_channels.extend(missing_groups)

    # Check 3: Recommended channels
    logger.info("Preflight: Checking recommended channels...")
    recommended_check = _check_recommended_channels(available_channels)
    checks.append(recommended_check)

    # Check 4 & 5: Sample data for health and semantic checks
    logger.info(f"Preflight: Sampling data for {sample_seconds} seconds...")

    # Set up validator for this provider
    validator.set_active_provider(provider.provider_id)
    validator.reset(provider.provider_id)

    # Collect samples for semantic analysis
    sample_buffer: dict[str, list[float]] = {}

    def on_sample(s):
        # Record in validator
        validator.record_sample(s)

        # Buffer for semantic analysis
        if s.channel_name not in sample_buffer:
            sample_buffer[s.channel_name] = []
        sample_buffer[s.channel_name].append(s.value)

    # Create stop event for timed sampling
    stop_event = asyncio.Event()

    async def stop_after_timeout():
        await asyncio.sleep(sample_seconds)
        stop_event.set()

    # Run sampling with timeout
    stop_task = asyncio.create_task(stop_after_timeout())
    try:
        await subscribe(
            provider,
            [],  # All channels
            on_sample,
            config=config,
            stop_event=stop_event,
            recv_timeout=2.0,
        )
    except Exception as e:
        logger.warning(f"Sampling interrupted: {e}")
    finally:
        stop_task.cancel()
        try:
            await stop_task
        except asyncio.CancelledError:
            pass

    # Check 4: Health thresholds
    logger.info("Preflight: Checking health thresholds...")
    health_data = validator.get_all_health(provider.provider_id)
    health_check = _check_health_thresholds(health_data)
    checks.append(health_check)

    # Check 5: Semantic validation
    logger.info("Preflight: Running semantic validation...")
    semantic_check, new_suspicions = _run_semantic_checks(sample_buffer)
    checks.append(semantic_check)
    suspicions.extend(new_suspicions)

    # Clear active provider (preflight complete)
    validator.set_active_provider(None)

    # Determine overall pass/fail
    failed_checks = [c for c in checks if c.status == CheckStatus.FAILED]
    high_confidence_mislabels = [s for s in suspicions if s.confidence >= 0.8]

    passed = len(failed_checks) == 0 and len(high_confidence_mislabels) == 0

    logger.info(f"Preflight complete: {'PASSED' if passed else 'FAILED'}")

    return PreflightResult(
        passed=passed,
        provider_id=provider.provider_id,
        provider_name=provider.name,
        provider_host=provider.host,
        checks=checks,
        missing_channels=missing_channels,
        suspected_mislabels=suspicions,
        can_override=mode == "advisory",
        mode=mode,
        sample_seconds=sample_seconds,
    )
