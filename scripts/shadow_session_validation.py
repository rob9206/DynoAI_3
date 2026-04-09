"""
Shadow validation: run representative v3 sessions and validate seed metadata.

Exercises three seeding scenarios:
    1. calibration_library  — twin_cam with matching entries in library
    2. template             — config that won't match library (empty) but has templates
    3. default              — no library, no templates

Reports seed_source, calibration_seed, and seed_warning for each.

Usage::

    python scripts/shadow_session_validation.py
    python scripts/shadow_session_validation.py --output-path output/shadow_validation.json
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("shadow_validation")
logger.setLevel(logging.INFO)


def _run_session(
    label: str,
    config_dict: Dict[str, Any],
    templates_dir: Path,
    calibration_library_dir: Path,
    calibration_policy: Dict[str, Any],
) -> Dict[str, Any]:
    from dynoai_v3.session_orchestrator import TuningSession
    from dynoai_v3.template_library import HardwareConfig

    config = HardwareConfig.from_dict(config_dict)

    session = TuningSession(
        config,
        templates_dir=templates_dir,
        calibration_library_dir=calibration_library_dir,
        calibration_top_n=calibration_policy.get("top_n", 5),
        calibration_min_similarity=calibration_policy.get("min_similarity", 0.55),
        calibration_min_matches=calibration_policy.get("min_matches", 1),
    )

    init = session.initialize(skip_template_seed=False)

    result = {
        "label": label,
        "session_id": init.session_id,
        "engine_family": init.engine_family,
        "seed_source": init.seed_source,
        "seed_warning": init.seed_warning,
        "calibration_seed_used": init.calibration_seed.get("used", False) if init.calibration_seed else False,
        "calibration_seed_match_count": init.calibration_seed.get("match_count", 0) if init.calibration_seed else 0,
        "calibration_seed_matches": init.calibration_seed.get("matches", []) if init.calibration_seed else [],
        "estimated_pulls": init.estimated_pulls,
        "template_match": (
            {
                "template_id": init.template_match.template_id,
                "similarity_score": init.template_match.similarity_score,
            }
            if init.template_match
            else None
        ),
    }
    return result


def validate() -> Dict[str, Any]:
    templates_dir = ROOT_DIR / "data" / "v3_templates"
    calibration_library_dir = ROOT_DIR / "data" / "calibration_library"
    empty_dir = Path(tempfile.mkdtemp(prefix="dynoai_empty_"))

    policy = {"top_n": 5, "min_similarity": 0.55, "min_matches": 1}

    scenarios: List[Dict[str, Any]] = []

    # Scenario 1: tc_103 slip_on — should hit calibration library via family alias
    logger.info("Scenario 1: calibration_library seed (tc_103 slip_on)")
    s1 = _run_session(
        label="calibration_library_seed",
        config_dict={
            "engine_family": "tc_103",
            "displacement_ci": 103,
            "cam_spec": "1690",
            "exhaust_type": "slip_on",
        },
        templates_dir=templates_dir,
        calibration_library_dir=calibration_library_dir,
        calibration_policy=policy,
    )
    scenarios.append(s1)

    # Scenario 2: tc_96 stock — calibration library has stock twin_cam entries
    logger.info("Scenario 2: calibration_library seed (tc_96 stock)")
    s2 = _run_session(
        label="calibration_library_stock",
        config_dict={
            "engine_family": "tc_96",
            "displacement_ci": 0,
            "cam_spec": "stock",
            "exhaust_type": "stock",
        },
        templates_dir=templates_dir,
        calibration_library_dir=calibration_library_dir,
        calibration_policy=policy,
    )
    scenarios.append(s2)

    # Scenario 3: empty calibration library — should fall to template or default
    logger.info("Scenario 3: default/template seed (empty calibration library)")
    s3 = _run_session(
        label="default_or_template_seed",
        config_dict={
            "engine_family": "tc_103",
            "displacement_ci": 103,
            "cam_spec": "stock",
            "exhaust_type": "stock",
        },
        templates_dir=templates_dir,
        calibration_library_dir=empty_dir,
        calibration_policy=policy,
    )
    scenarios.append(s3)

    # Scenario 4: Very high min_similarity — should trigger warning/fallback
    logger.info("Scenario 4: high threshold (min_similarity=0.99)")
    s4 = _run_session(
        label="high_threshold_fallback",
        config_dict={
            "engine_family": "tc_103",
            "displacement_ci": 103,
            "cam_spec": "1690",
            "exhaust_type": "slip_on",
        },
        templates_dir=templates_dir,
        calibration_library_dir=calibration_library_dir,
        calibration_policy={"top_n": 5, "min_similarity": 0.99, "min_matches": 1},
    )
    scenarios.append(s4)

    # Validate expected behavior
    checks: List[Dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str = ""):
        checks.append({"check": name, "passed": passed, "detail": detail})
        status = "PASS" if passed else "FAIL"
        logger.info("  [%s] %s %s", status, name, f"— {detail}" if detail else "")

    # Scenario 1 checks
    check(
        "s1_seed_source_is_calibration_library",
        s1["seed_source"] == "calibration_library",
        f"actual={s1['seed_source']}",
    )
    check(
        "s1_has_calibration_matches",
        s1["calibration_seed_match_count"] > 0,
        f"matches={s1['calibration_seed_match_count']}",
    )
    check(
        "s1_calibration_seed_used",
        s1["calibration_seed_used"] is True,
        f"used={s1['calibration_seed_used']}",
    )
    check(
        "s1_no_seed_warning",
        s1["seed_warning"] == "",
        f"warning={s1['seed_warning']!r}",
    )

    # Scenario 2 checks
    check(
        "s2_seed_source_is_calibration_library",
        s2["seed_source"] == "calibration_library",
        f"actual={s2['seed_source']}",
    )
    check(
        "s2_has_calibration_matches",
        s2["calibration_seed_match_count"] > 0,
        f"matches={s2['calibration_seed_match_count']}",
    )

    # Scenario 3 checks — empty library → should be template or default
    check(
        "s3_seed_source_not_calibration",
        s3["seed_source"] in ("template", "default"),
        f"actual={s3['seed_source']}",
    )
    check(
        "s3_no_calibration_matches",
        s3["calibration_seed_match_count"] == 0,
        f"matches={s3['calibration_seed_match_count']}",
    )

    # Scenario 4 checks — very high threshold
    check(
        "s4_seed_source_not_calibration",
        s4["seed_source"] in ("template", "default"),
        f"actual={s4['seed_source']}",
    )

    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)

    report = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": scenarios,
        "checks": checks,
        "summary": {"passed": passed, "total": total, "all_passed": passed == total},
    }
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Shadow validation for v3 session seeding")
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()

    report = validate()

    if args.output_path:
        out = Path(args.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        logger.info("Report written to %s", out)

    summary = report["summary"]
    logger.info("")
    logger.info("Shadow validation: %d/%d checks passed", summary["passed"], summary["total"])
    if not summary["all_passed"]:
        logger.error("SOME CHECKS FAILED — review report for details")
        for c in report["checks"]:
            if not c["passed"]:
                logger.error("  FAIL: %s — %s", c["check"], c["detail"])
        return 1
    logger.info("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
