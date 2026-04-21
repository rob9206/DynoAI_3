"""
DynoAI v3.0 — Template Library
================================

Every completed tune is stored with its hardware configuration signature
and full calibration data.  When a new bike arrives, the system finds the
closest match and uses it as the GP surrogate's prior — giving the session
a massive head start.

Competitive Moat:
    Every tune Thunderhorse completes adds a template.  After 50 tunes,
    you have a library no competitor can replicate.  After 200, the system
    knows what an M8 114 with Bassani 2-into-1 and S&S 475 cams should
    look like before the first pull.

Author: Thunderhorse Tuning / DynoAI
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hardware configuration
# ---------------------------------------------------------------------------
@dataclass
class HardwareConfig:
    """
    Hardware configuration for a motorcycle build.

    engine_family and displacement_ci are required.  Other fields
    contribute to similarity scoring when matching templates.
    """
    # Required
    engine_family: str = ""
    displacement_ci: int = 0

    # Cam
    cam_spec: str = "stock"

    # Exhaust
    exhaust_type: str = "stock"
    exhaust_brand: str = "stock"

    # Induction
    air_cleaner: str = "stock"
    throttle_body_mm: int = 55

    # Compression
    compression_ratio: float = 10.0
    head_work: str = "stock"

    # Injectors
    injector_size: str = "stock"

    # Context
    fuel_type: str = "pump_93"
    altitude_ft: int = 0
    tune_platform: str = "pv"

    # Optional grid override (from PVV import or wizard)
    rpm_bins: Optional[List[float]] = None
    map_bins: Optional[List[float]] = None

    def signature(self) -> str:
        """
        Deterministic, filesystem-safe signature string.

        No ``/``, ``\\``, or spaces.  Suitable for filenames and index keys.
        """
        parts = [
            self.engine_family,
            str(self.displacement_ci),
            self.cam_spec,
            self.exhaust_type,
        ]
        raw = "_".join(parts)
        # Replace any non-filesystem-safe characters
        safe = (
            raw.replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "_")
            .replace("&", "and")
        )
        # Append a short hash for uniqueness on optional fields
        full = json.dumps(asdict(self), sort_keys=True)
        short_hash = hashlib.sha256(full.encode()).hexdigest()[:8]
        return f"{safe}_{short_hash}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HardwareConfig":
        # Only keep fields that belong to HardwareConfig
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Template match result
# ---------------------------------------------------------------------------
@dataclass
class TemplateMatch:
    """Result of a template library search."""
    template_id: str
    config: HardwareConfig
    calibration: Dict[str, Any]
    similarity_score: float     # 0.0 - 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        """A match is usable if similarity >= 0.5."""
        return self.similarity_score >= 0.5


# ---------------------------------------------------------------------------
# Similarity scoring weights
# ---------------------------------------------------------------------------
_SIMILARITY_WEIGHTS = {
    "cam_spec": 0.30,
    "exhaust_type": 0.20,
    "air_cleaner": 0.15,
    "compression_ratio": 0.15,
    "throttle_body_mm": 0.10,
    "fuel_type": 0.10,
}


def _string_similarity(query_val: str, stored_val: str) -> float:
    """Fuzzy string similarity for cam_spec/exhaust_type matching.

    Returns 0.0–1.0 credit fraction:
      1.0 = exact match
      0.6 = query token found inside the stored free-text value
      0.3 = "stock" vs "stock" substring inside a longer description
      0.0 = no relation detected
    """
    q = query_val.lower().strip()
    s = stored_val.lower().strip()
    if q == s:
        return 1.0

    # Normalise underscores/hyphens to spaces for token matching
    q_norm = q.replace("_", " ").replace("-", " ")
    s_norm = s.replace("_", " ").replace("-", " ")

    if q_norm == s_norm:
        return 1.0

    # Token-in-string: e.g. query="se_255" matches stored="1690 with se 255 cams …"
    q_tokens = q_norm.split()
    if len(q_tokens) >= 2:
        joined = " ".join(q_tokens)
        if joined in s_norm:
            return 0.7

    # Single meaningful token: e.g. query="open" matches stored="open pipe …"
    for token in q_tokens:
        if len(token) >= 3 and token in s_norm:
            return 0.4

    # Both "stock" — partial credit even if stored has extra text
    if "stock" in q_norm and "stock" in s_norm:
        return 0.5

    return 0.0


def _compute_similarity(query: HardwareConfig, stored: HardwareConfig) -> float:
    """
    Weighted similarity score between two hardware configs.

    engine_family is a MUST-MATCH gate (handled by caller).
    displacement_ci is a MUST-MATCH gate (handled by caller).

    Returns 0.0 - 1.0 where 1.0 is exact match.
    """
    score = 0.0
    total_weight = 0.0

    for field_name, weight in _SIMILARITY_WEIGHTS.items():
        total_weight += weight
        q_val = getattr(query, field_name)
        s_val = getattr(stored, field_name)

        if isinstance(q_val, float):
            # Numeric comparison — compression_ratio
            if abs(q_val - s_val) < 0.1:
                score += weight       # Exact
            elif abs(q_val - s_val) <= 0.5:
                score += weight * 0.7  # Close
            elif abs(q_val - s_val) <= 1.0:
                score += weight * 0.3  # Partial
            # else: 0 contribution
        elif isinstance(q_val, int):
            # Numeric comparison — throttle_body_mm
            if q_val == s_val:
                score += weight
            elif abs(q_val - s_val) <= 2:
                score += weight * 0.7
            elif abs(q_val - s_val) <= 4:
                score += weight * 0.3
        else:
            # String comparison with fuzzy matching
            credit = _string_similarity(str(q_val), str(s_val))
            score += weight * credit

    if total_weight > 0:
        return score / total_weight
    return 0.0


# ---------------------------------------------------------------------------
# Template library
# ---------------------------------------------------------------------------
class TemplateLibrary:
    """
    Stores and retrieves hardware-matched calibration templates.

    Storage is a directory of JSON files organized by engine family:
        storage_dir/
            index.json
            m8_114/
                <template_id>.json
            revmax_1250/
                <template_id>.json
    """

    def __init__(self, storage_dir: Path):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"
        self._index: List[Dict[str, Any]] = self._load_index()

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------
    def store_template(
        self,
        config: HardwareConfig,
        calibration: Dict[str, Any],
        operator: Optional[str] = None,
    ) -> str:
        """
        Store a completed calibration as a template.

        Args:
            config: Hardware configuration
            calibration: Calibration data (VE tables, spark maps, etc.)
            operator: Operator name

        Returns:
            template_id string
        """
        template_id = str(uuid.uuid4())[:12]

        # Build template record
        record = {
            "template_id": template_id,
            "config": config.to_dict(),
            "calibration": calibration,
            "metadata": {
                "created": time.time(),
                "operator": operator or "unknown",
                "signature": config.signature(),
            },
        }

        # Store in family subdirectory
        family_dir = self._dir / config.engine_family
        family_dir.mkdir(parents=True, exist_ok=True)
        template_path = family_dir / f"{template_id}.json"

        with open(template_path, "w") as f:
            json.dump(record, f, indent=2)

        # Update index
        self._index.append({
            "template_id": template_id,
            "engine_family": config.engine_family,
            "displacement_ci": config.displacement_ci,
            "signature": config.signature(),
            "config": config.to_dict(),
            "path": str(template_path.relative_to(self._dir)),
        })
        self._save_index()

        logger.info(
            "Template stored: %s (%s, %s)",
            template_id, config.engine_family, config.signature(),
        )
        return template_id

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------
    def find_nearest(self, query: HardwareConfig) -> Optional[TemplateMatch]:
        """
        Find the closest matching template for a hardware config.

        engine_family is a MUST-MATCH — returns None if no templates
        exist for the same family.

        Returns:
            TemplateMatch or None if no match found
        """
        best_score = -1.0
        best_entry: Optional[Dict[str, Any]] = None

        for entry in self._index:
            # Gate 1: engine_family must match
            if entry["engine_family"] != query.engine_family:
                continue

            stored_config = HardwareConfig.from_dict(entry["config"])
            score = _compute_similarity(query, stored_config)

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is None:
            return None

        # Load full template
        template_path = self._dir / best_entry["path"]
        with open(template_path, "r") as f:
            record = json.load(f)

        return TemplateMatch(
            template_id=best_entry["template_id"],
            config=HardwareConfig.from_dict(record["config"]),
            calibration=record["calibration"],
            similarity_score=best_score,
            metadata=record.get("metadata", {}),
        )

    # ------------------------------------------------------------------
    # Count
    # ------------------------------------------------------------------
    def count(self, engine_family: Optional[str] = None) -> int:
        """
        Count templates in the library.

        Args:
            engine_family: If provided, count only for that family
        """
        if engine_family is None:
            return len(self._index)
        return sum(
            1 for e in self._index if e["engine_family"] == engine_family
        )

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------
    def _load_index(self) -> List[Dict[str, Any]]:
        if self._index_path.exists():
            with open(self._index_path, "r") as f:
                return json.load(f)
        return []

    def _save_index(self) -> None:
        with open(self._index_path, "w") as f:
            json.dump(self._index, f, indent=2)
