"""
JetDrive Channel Mapping Service

Provides persistent channel mappings per provider, allowing:
- Unique provider identification via signature (provider_id + host + channel hash)
- Canonical channel name mapping (RPM, AFR, MAP, etc.)
- Value transforms (Lambda→AFR, Nm→ft-lb, kW→HP)
- Per-run override capability

Usage:
    from api.services.jetdrive_mapping import (
        compute_provider_signature,
        get_mapping,
        save_mapping,
        apply_mapping,
    )

    # Get/create mapping for a provider
    signature = compute_provider_signature(provider)
    mapping = get_mapping(signature)

    # Apply mapping to a sample
    canonical_name, transformed_value = apply_mapping(mapping, sample)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Mapping file location
MAPPING_DIR = Path("config/jetdrive_mappings")

# Canonical channel names (what DynoAI expects)
CANONICAL_CHANNELS = {
    "rpm": "Engine RPM",
    "afr_front": "AFR Front",
    "afr_rear": "AFR Rear",
    "afr_combined": "AFR Combined",
    "map_kpa": "MAP (kPa)",
    "tps": "TPS (%)",
    "torque": "Torque (ft-lb)",
    "power": "Power (HP)",
    "ect": "ECT (°F)",
    "iat": "IAT (°F)",
    "spark": "Spark Advance",
    "knock": "Knock Retard",
    "lambda_front": "Lambda Front",
    "lambda_rear": "Lambda Rear",
}

# Required canonical channels for tuning
REQUIRED_CANONICAL = ["rpm", "afr_front"]  # At least one AFR
RECOMMENDED_CANONICAL = ["map_kpa", "tps", "torque", "power"]

# =============================================================================
# Transform Functions
# =============================================================================


def lambda_to_afr(value: float) -> float:
    """Convert Lambda to AFR (gasoline stoich = 14.7)."""
    return value * 14.7


def afr_to_lambda(value: float) -> float:
    """Convert AFR to Lambda."""
    return value / 14.7


def nm_to_ftlb(value: float) -> float:
    """Convert Newton-meters to foot-pounds."""
    return value * 0.737562


def ftlb_to_nm(value: float) -> float:
    """Convert foot-pounds to Newton-meters."""
    return value / 0.737562


def kw_to_hp(value: float) -> float:
    """Convert kilowatts to horsepower."""
    return value * 1.34102


def hp_to_kw(value: float) -> float:
    """Convert horsepower to kilowatts."""
    return value / 1.34102


def celsius_to_fahrenheit(value: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return value * 9 / 5 + 32


def fahrenheit_to_celsius(value: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (value - 32) * 5 / 9


def identity(value: float) -> float:
    """No transformation (pass-through)."""
    return value


# Transform registry
TRANSFORMS: dict[str, Callable[[float], float]] = {
    "lambda_to_afr": lambda_to_afr,
    "afr_to_lambda": afr_to_lambda,
    "nm_to_ftlb": nm_to_ftlb,
    "ftlb_to_nm": ftlb_to_nm,
    "kw_to_hp": kw_to_hp,
    "hp_to_kw": hp_to_kw,
    "c_to_f": celsius_to_fahrenheit,
    "f_to_c": fahrenheit_to_celsius,
    "identity": identity,
}

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ChannelMapping:
    """Mapping for a single channel."""

    canonical_name: str  # What DynoAI calls it (e.g., "rpm")
    source_id: int  # Channel ID from provider
    source_name: str  # Channel name from provider
    transform: str = "identity"  # Transform function name
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "transform": self.transform,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, canonical_name: str,
                  data: dict[str, Any]) -> "ChannelMapping":
        return cls(
            canonical_name=canonical_name,
            source_id=data["source_id"],
            source_name=data["source_name"],
            transform=data.get("transform", "identity"),
            enabled=data.get("enabled", True),
        )


@dataclass
class MappingConfidence:
    """Confidence score for an auto-detected mapping."""

    canonical_name: str
    source_id: int
    source_name: str
    confidence: float  # 0.0 to 1.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    transform: str = "identity"

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_name": self.canonical_name,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "confidence": round(self.confidence, 2),
            "reasons": self.reasons,
            "warnings": self.warnings,
            "transform": self.transform,
        }


@dataclass
class ProviderMapping:
    """Complete mapping configuration for a provider."""

    version: str = "1.0"
    provider_signature: str = ""
    provider_id: int = 0
    provider_name: str = ""
    host: str = ""
    created_at: str = ""
    updated_at: str = ""
    channels: dict[str, ChannelMapping] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "provider_signature": self.provider_signature,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "host": self.host,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "channels": {
                name: mapping.to_dict()
                for name, mapping in self.channels.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderMapping":
        channels = {}
        for name, ch_data in data.get("channels", {}).items():
            channels[name] = ChannelMapping.from_dict(name, ch_data)

        return cls(
            version=data.get("version", "1.0"),
            provider_signature=data.get("provider_signature", ""),
            provider_id=data.get("provider_id", 0),
            provider_name=data.get("provider_name", ""),
            host=data.get("host", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            channels=channels,
        )

    def get_source_to_canonical_map(self) -> dict[int, str]:
        """Get mapping from source channel ID to canonical name."""
        return {
            m.source_id: m.canonical_name
            for m in self.channels.values() if m.enabled
        }

    def get_missing_required(self) -> list[str]:
        """Get list of missing required canonical channels."""
        mapped = set(self.channels.keys())
        # Need at least one AFR channel
        has_afr = any(
            name.startswith("afr_") or name.startswith("lambda_")
            for name in mapped)
        missing = []
        if "rpm" not in mapped:
            missing.append("rpm")
        if not has_afr:
            missing.append("afr (any)")
        return missing

    def get_missing_recommended(self) -> list[str]:
        """Get list of missing recommended canonical channels."""
        mapped = set(self.channels.keys())
        return [ch for ch in RECOMMENDED_CANONICAL if ch not in mapped]


# =============================================================================
# Provider Signature
# =============================================================================


def compute_provider_signature(provider: Any) -> str:
    """
    Compute a unique signature for a provider configuration.

    The signature includes:
    - provider_id (int)
    - host IP
    - Hash of channel configuration (IDs, names, units)

    If the channel config changes (e.g., new channels enabled in Power Core),
    the signature changes, prompting re-mapping.

    Args:
        provider: JetDriveProviderInfo instance

    Returns:
        Signature string like "4097_192.168.1.50_a1b2c3d4e5f6"
    """
    # Build sorted list of channel info for consistent hashing
    channel_info = sorted(
        [{
            "id": c.chan_id,
            "name": c.name,
            "unit": c.unit if isinstance(c.unit, int) else int(c.unit),
        } for c in provider.channels.values()],
        key=lambda x: x["id"],
    )

    # Hash the channel configuration
    channel_json = json.dumps(channel_info, sort_keys=True)
    channel_hash = hashlib.sha256(channel_json.encode()).hexdigest()[:12]

    # Build signature
    return f"{provider.provider_id}_{provider.host}_{channel_hash}"


def parse_provider_signature(signature: str) -> tuple[int, str, str]:
    """
    Parse a provider signature into its components.

    Returns:
        Tuple of (provider_id, host, channel_hash)
    """
    parts = signature.split("_", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid provider signature: {signature}")

    provider_id = int(parts[0])
    host = parts[1]
    channel_hash = parts[2]

    return provider_id, host, channel_hash


# =============================================================================
# Mapping Persistence
# =============================================================================


def get_mapping_path(signature: str) -> Path:
    """Get the file path for a mapping file."""
    # Sanitize signature for filename
    safe_sig = signature.replace(":", "_").replace("/", "_")
    return MAPPING_DIR / f"{safe_sig}.json"


def ensure_mapping_dir() -> None:
    """Ensure the mapping directory exists."""
    MAPPING_DIR.mkdir(parents=True, exist_ok=True)


def get_mapping(signature: str) -> ProviderMapping | None:
    """
    Load a mapping file for a provider signature.

    Args:
        signature: Provider signature

    Returns:
        ProviderMapping if file exists, None otherwise
    """
    path = get_mapping_path(signature)
    if not path.exists():
        logger.debug(f"No mapping file found for {signature}")
        return None

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return ProviderMapping.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load mapping {path}: {e}")
        return None


def save_mapping(mapping: ProviderMapping) -> bool:
    """
    Save a mapping file.

    Args:
        mapping: ProviderMapping to save

    Returns:
        True if successful, False otherwise
    """
    ensure_mapping_dir()
    path = get_mapping_path(mapping.provider_signature)

    try:
        mapping.updated_at = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(mapping.to_dict(), f, indent=2)
        logger.info(f"Saved mapping to {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save mapping {path}: {e}")
        return False


def delete_mapping(signature: str) -> bool:
    """Delete a mapping file."""
    path = get_mapping_path(signature)
    if path.exists():
        try:
            path.unlink()
            logger.info(f"Deleted mapping {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete mapping {path}: {e}")
            return False
    return True  # Already doesn't exist


def list_mappings() -> list[ProviderMapping]:
    """List all saved mappings."""
    ensure_mapping_dir()
    mappings = []

    for path in MAPPING_DIR.glob("*.json"):
        if path.name.startswith("template_"):
            continue  # Skip templates
        try:
            with open(path, "r") as f:
                data = json.load(f)
            mappings.append(ProviderMapping.from_dict(data))
        except Exception as e:
            logger.warning(f"Failed to load mapping {path}: {e}")

    return mappings


# =============================================================================
# Templates
# =============================================================================

# Built-in templates for common dyno configurations
BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "dynojet_rt150": {
        "name": "Dynojet RT-150",
        "description": "Standard Dynojet RT-150 inertia dyno channel mapping",
        "channels": {
            "rpm": {
                "source_id": 10,
                "source_name": "Digital RPM 1"
            },
            "torque": {
                "source_id": 3,
                "source_name": "Torque"
            },
            "power": {
                "source_id": 4,
                "source_name": "Horsepower"
            },
            "afr_front": {
                "source_id": 15,
                "source_name": "Air/Fuel Ratio 1"
            },
            "afr_rear": {
                "source_id": 16,
                "source_name": "Air/Fuel Ratio 2"
            },
        },
    },
    "dynojet_424x": {
        "name": "Dynojet 424xLC",
        "description": "Dynojet 424 load-control dyno channel mapping",
        "channels": {
            "rpm": {
                "source_id": 10,
                "source_name": "Digital RPM 1"
            },
            "torque": {
                "source_id": 3,
                "source_name": "Torque",
                "transform": "nm_to_ftlb",
            },
            "power": {
                "source_id": 4,
                "source_name": "Power",
                "transform": "kw_to_hp"
            },
            "afr_front": {
                "source_id": 15,
                "source_name": "Air/Fuel Ratio 1"
            },
            "afr_rear": {
                "source_id": 16,
                "source_name": "Air/Fuel Ratio 2"
            },
            "map_kpa": {
                "source_id": 20,
                "source_name": "MAP kPa"
            },
        },
    },
    "mustang_md250": {
        "name": "Mustang MD-250",
        "description": "Mustang Dynamometer MD-250 channel mapping",
        "channels": {
            "rpm": {
                "source_id": 1,
                "source_name": "RPM"
            },
            "torque": {
                "source_id": 2,
                "source_name": "Torque"
            },
            "power": {
                "source_id": 3,
                "source_name": "Power"
            },
            "afr_combined": {
                "source_id": 10,
                "source_name": "AFR"
            },
        },
    },
}


def get_templates() -> list[dict[str, Any]]:
    """Get list of available templates."""
    templates = []

    # Built-in templates
    for template_id, template in BUILTIN_TEMPLATES.items():
        templates.append({
            "id": template_id,
            "name": template["name"],
            "description": template["description"],
            "builtin": True,
            "channel_count": len(template["channels"]),
        })

    # Custom templates from disk
    ensure_mapping_dir()
    for path in MAPPING_DIR.glob("template_*.json"):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            templates.append({
                "id": path.stem,
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "builtin": False,
                "channel_count": len(data.get("channels", {})),
            })
        except Exception as e:
            logger.warning(f"Failed to load template {path}: {e}")

    return templates


def get_template(template_id: str) -> dict[str, Any] | None:
    """Get a specific template by ID."""
    # Check built-in templates
    if template_id in BUILTIN_TEMPLATES:
        return BUILTIN_TEMPLATES[template_id]

    # Check custom templates
    path = MAPPING_DIR / f"template_{template_id}.json"
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load template {path}: {e}")

    return None


def create_mapping_from_template(
    template_id: str,
    provider: Any,
    signature: str,
) -> ProviderMapping | None:
    """
    Create a new mapping from a template.

    Args:
        template_id: Template ID to use
        provider: JetDriveProviderInfo instance
        signature: Provider signature

    Returns:
        New ProviderMapping with template channels applied
    """
    template = get_template(template_id)
    if not template:
        logger.error(f"Template not found: {template_id}")
        return None

    # Create mapping with template channels
    mapping = ProviderMapping(
        provider_signature=signature,
        provider_id=provider.provider_id,
        provider_name=provider.name,
        host=provider.host,
        created_at=datetime.now().isoformat(),
    )

    # Apply template channels
    for canonical_name, ch_data in template.get("channels", {}).items():
        mapping.channels[canonical_name] = ChannelMapping(
            canonical_name=canonical_name,
            source_id=ch_data["source_id"],
            source_name=ch_data["source_name"],
            transform=ch_data.get("transform", "identity"),
            enabled=True,
        )

    return mapping


# =============================================================================
# Mapping Application
# =============================================================================


def apply_transform(value: float, transform_name: str) -> float:
    """
    Apply a transform function to a value.

    Args:
        value: Input value
        transform_name: Name of transform function

    Returns:
        Transformed value
    """
    transform_func = TRANSFORMS.get(transform_name, identity)
    return transform_func(value)


def apply_mapping_to_sample(
    mapping: ProviderMapping,
    channel_id: int,
    channel_name: str,
    value: float,
) -> tuple[str | None, float]:
    """
    Apply mapping to a single sample.

    Args:
        mapping: ProviderMapping to use
        channel_id: Source channel ID
        channel_name: Source channel name
        value: Source value

    Returns:
        Tuple of (canonical_name, transformed_value).
        canonical_name is None if channel is not mapped.
    """
    # Find mapping by source channel ID
    for canonical_name, ch_mapping in mapping.channels.items():
        if ch_mapping.source_id == channel_id and ch_mapping.enabled:
            transformed = apply_transform(value, ch_mapping.transform)
            return canonical_name, transformed

    # No mapping found - return original
    return None, value


# =============================================================================
# Auto-Mapping (Best-Effort)
# =============================================================================

# Unit type mappings for JDUnit enum
# Maps canonical channel names to their expected JDUnit values
CANONICAL_UNIT_TYPES = {
    "rpm": [8],  # JDUnit.EngineSpeed / JDUnit.RPM
    "afr_front": [11],  # JDUnit.AFR
    "afr_rear": [11],  # JDUnit.AFR
    "afr_combined": [11],  # JDUnit.AFR
    "lambda_front": [13],  # JDUnit.Lambda
    "lambda_rear": [13],  # JDUnit.Lambda
    "map_kpa": [7],  # JDUnit.Pressure
    "tps": [16],  # JDUnit.Percentage
    "torque": [5],  # JDUnit.Torque
    "power": [4],  # JDUnit.Power
    "ect": [6],  # JDUnit.Temperature
    "iat": [6],  # JDUnit.Temperature
    "spark": [255],  # JDUnit.NoUnit (often angle/degrees)
    "knock": [255],  # JDUnit.NoUnit (often retard amount)
}

# Heuristics for auto-mapping channels
AUTO_MAP_PATTERNS = {
    "rpm": ["rpm", "engine rpm", "digital rpm", "motor rpm"],
    "afr_front": ["afr 1", "afr front", "air/fuel ratio 1", "a/f 1"],
    "afr_rear": ["afr 2", "afr rear", "air/fuel ratio 2", "a/f 2"],
    "afr_combined": ["afr", "air/fuel", "a/f ratio"],
    "lambda_front": ["lambda 1", "lambda front"],
    "lambda_rear": ["lambda 2", "lambda rear"],
    "map_kpa": ["map", "manifold pressure", "intake manifold"],
    "tps": ["tps", "throttle", "throttle position"],
    "torque": ["torque", "trq"],
    "power": ["power", "hp", "horsepower", "bhp"],
    "ect": ["ect", "coolant temp", "engine temp", "water temp"],
    "iat": ["iat", "intake temp", "air temp"],
    "spark": ["spark", "timing", "ignition advance"],
    "knock": ["knock", "knock retard", "det"],
}


def score_channel_for_canonical(
    channel: Any,
    canonical_name: str,
    all_channels: list[Any],
) -> MappingConfidence:
    """
    Score how well a channel matches a canonical name.

    Uses:
    - Unit type matching (JDUnit enum): +0.5
    - Name pattern matching: +0.3
    - Disambiguation bonus (if no better match exists): +0.2

    Args:
        channel: ChannelInfo instance
        canonical_name: Target canonical name (e.g., "rpm")
        all_channels: All available channels for disambiguation

    Returns:
        MappingConfidence with score and reasoning
    """
    score = 0.0
    reasons = []
    warnings = []
    transform = "identity"

    # Get channel unit (handle both int and IntEnum)
    channel_unit = int(channel.unit) if hasattr(channel, "unit") else 255

    # 1. Unit type match (+0.5)
    expected_units = CANONICAL_UNIT_TYPES.get(canonical_name, [])
    if expected_units and channel_unit in expected_units:
        score += 0.5
        from api.services.jetdrive_client import JDUnit

        try:
            unit_name = JDUnit(channel_unit).name
            reasons.append(f"Unit match ({unit_name})")
        except ValueError:
            reasons.append(f"Unit match (unit={channel_unit})")

        # Special handling for lambda channels - needs transform
        if canonical_name.startswith("lambda_"):
            transform = "lambda_to_afr"
            warnings.append("Lambda channel - auto-converting to AFR")

    # 2. Name pattern match (+0.3)
    patterns = AUTO_MAP_PATTERNS.get(canonical_name, [])
    channel_name_lower = channel.name.lower()
    matched_pattern = None
    for pattern in patterns:
        if pattern in channel_name_lower:
            matched_pattern = pattern
            break

    if matched_pattern:
        score += 0.3
        reasons.append(f"Name pattern match ('{matched_pattern}')")

    # 3. Disambiguation check (+0.2 if this is the best match)
    # Check if any other channel has a higher score for this canonical
    better_match_exists = False
    for other_channel in all_channels:
        if other_channel.chan_id == channel.chan_id:
            continue

        # Quick check: does other channel have better unit match?
        other_unit = int(other_channel.unit) if hasattr(other_channel,
                                                        "unit") else 255
        other_name_lower = other_channel.name.lower()

        other_score = 0.0
        if expected_units and other_unit in expected_units:
            other_score += 0.5

        for pattern in patterns:
            if pattern in other_name_lower:
                other_score += 0.3
                break

        if other_score > score:
            better_match_exists = True
            break

    if not better_match_exists and score > 0:
        score += 0.2
        reasons.append("Best match among available channels")

    # Cap at 1.0
    score = min(score, 1.0)

    # Add warnings based on confidence level
    if score < 0.5:
        warnings.append("Low confidence - manual verification recommended")
    elif score < 0.7:
        warnings.append("Medium confidence - verify before use")

    return MappingConfidence(
        canonical_name=canonical_name,
        source_id=channel.chan_id,
        source_name=channel.name,
        confidence=score,
        reasons=reasons,
        warnings=warnings,
        transform=transform,
    )


def auto_map_channels(provider: Any) -> dict[str, ChannelMapping]:
    """
    Attempt to auto-map channels based on name patterns.

    Legacy function - prefer auto_map_channels_with_confidence() for new code.

    Args:
        provider: JetDriveProviderInfo instance

    Returns:
        Dict of canonical_name -> ChannelMapping for matched channels
    """
    # Use new confidence-based function and convert results
    confidence_mappings = auto_map_channels_with_confidence(provider)

    mappings = {}
    for canonical_name, conf in confidence_mappings.items():
        mappings[canonical_name] = ChannelMapping(
            canonical_name=canonical_name,
            source_id=conf.source_id,
            source_name=conf.source_name,
            transform=conf.transform,
            enabled=True,
        )

    return mappings


def auto_map_channels_with_confidence(
        provider: Any) -> dict[str, MappingConfidence]:
    """
    Auto-map channels with confidence scoring.

    Uses unit-based inference + name pattern matching to detect mappings.

    Args:
        provider: JetDriveProviderInfo instance

    Returns:
        Dict of canonical_name -> MappingConfidence for detected mappings
    """
    all_channels = list(provider.channels.values())
    mappings: dict[str, MappingConfidence] = {}
    used_channel_ids: set[int] = set()

    # Try to map each canonical channel
    for canonical_name in CANONICAL_CHANNELS.keys():
        best_confidence: MappingConfidence | None = None

        # Score all available channels for this canonical name
        for channel in all_channels:
            if channel.chan_id in used_channel_ids:
                continue

            confidence = score_channel_for_canonical(channel, canonical_name,
                                                     all_channels)

            # Keep the best scoring match
            if confidence.confidence > 0 and (best_confidence is None
                                              or confidence.confidence
                                              > best_confidence.confidence):
                best_confidence = confidence

        # Accept mapping if confidence > 0.5 (at least unit match OR name match + disambig)
        if best_confidence and best_confidence.confidence >= 0.5:
            mappings[canonical_name] = best_confidence
            used_channel_ids.add(best_confidence.source_id)
            logger.info(
                f"Auto-mapped {canonical_name} -> {best_confidence.source_name} "
                f"(confidence: {best_confidence.confidence:.2f})")

    return mappings


def get_unmapped_required_channels(mapping: ProviderMapping) -> list[str]:
    """Get list of required canonical channels that are not mapped."""
    mapped = set(mapping.channels.keys())
    unmapped = []

    # Check RPM (always required)
    if "rpm" not in mapped:
        unmapped.append("rpm")

    # Check AFR (need at least one AFR or Lambda channel)
    has_afr = any(
        name.startswith("afr_") or name.startswith("lambda_")
        for name in mapped)
    if not has_afr:
        unmapped.append("afr (any)")

    return unmapped


def get_low_confidence_mappings(
        confidence_map: dict[str, MappingConfidence],
        threshold: float = 0.7) -> list[MappingConfidence]:
    """Get mappings with confidence below threshold."""
    return [
        conf for conf in confidence_map.values() if conf.confidence < threshold
    ]


def create_auto_mapping(provider: Any, signature: str) -> ProviderMapping:
    """
    Create a new mapping with auto-detected channel mappings.

    Args:
        provider: JetDriveProviderInfo instance
        signature: Provider signature

    Returns:
        ProviderMapping with auto-detected channels
    """
    mapping = ProviderMapping(
        provider_signature=signature,
        provider_id=provider.provider_id,
        provider_name=provider.name,
        host=provider.host,
        created_at=datetime.now().isoformat(),
    )

    mapping.channels = auto_map_channels(provider)

    return mapping
