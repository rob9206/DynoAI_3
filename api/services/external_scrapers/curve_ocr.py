from __future__ import annotations

import re
from dataclasses import replace
from typing import Dict, List

from PIL import Image

from external_scrapers import get_stdout_logger
from external_scrapers.dyno_models import DynoChartMeta

try:
    import pytesseract  # type: ignore
except ImportError:  # pragma: no cover - exercised in environments without binary

    class _MissingPytesseract:
        def image_to_string(self, *args, **kwargs):
            raise RuntimeError("pytesseract is not installed")

    pytesseract = _MissingPytesseract()  # type: ignore

logger = get_stdout_logger(__name__)


def extract_dynostar_overlays(
    image_path: str, crop_ratio: float = 0.24
) -> Dict[str, float | None]:
    """
    OCR the bottom band of a dyno chart for max power/torque overlays.
    """
    results: Dict[str, float | None] = {
        "max_power_hp": None,
        "max_power_rpm": None,
        "max_torque_ftlb": None,
        "max_torque_rpm": None,
    }
    try:
        img = Image.open(image_path)
    except Exception as exc:
        logger.warning("Could not open image %s: %s", image_path, exc)
        return results

    width, height = img.size
    crop_top = int(height * (1 - crop_ratio))
    overlay = img.crop((0, crop_top, width, height))

    try:
        text = pytesseract.image_to_string(overlay, config="--psm 6", lang="eng")
    except Exception as exc:  # pragma: no cover - depends on tesseract availability
        logger.warning("OCR failed for %s: %s", image_path, exc)
        return results

    power_match = re.search(
        r"Max\s*Power\s*=\s*([0-9.]+).*?RPM\s*=\s*([0-9.]+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    torque_match = re.search(
        r"Max\s*Torque\s*=\s*([0-9.]+).*?RPM\s*=\s*([0-9.]+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if power_match:
        results["max_power_hp"] = float(power_match.group(1))
        results["max_power_rpm"] = float(power_match.group(2)) * 1000
    if torque_match:
        results["max_torque_ftlb"] = float(torque_match.group(1))
        results["max_torque_rpm"] = float(torque_match.group(2)) * 1000

    logger.info(
        "OCR parsed for %s -> HP: %s @ %s, TQ: %s @ %s",
        image_path,
        results["max_power_hp"],
        results["max_power_rpm"],
        results["max_torque_ftlb"],
        results["max_torque_rpm"],
    )
    return results


def annotate_meta_with_ocr(meta_list: List[DynoChartMeta]) -> List[DynoChartMeta]:
    """
    Fill missing peak values for charts with available image files using OCR.
    """
    updated: List[DynoChartMeta] = []
    for meta in meta_list:
        needs_power = meta.max_power_hp is None or meta.max_power_rpm is None
        needs_torque = meta.max_torque_ftlb is None or meta.max_torque_rpm is None
        if not meta.image_file or (not needs_power and not needs_torque):
            updated.append(meta)
            continue

        stats = extract_dynostar_overlays(meta.image_file)
        updated_meta = replace(
            meta,
            max_power_hp=meta.max_power_hp or stats["max_power_hp"],
            max_power_rpm=meta.max_power_rpm or stats["max_power_rpm"],
            max_torque_ftlb=meta.max_torque_ftlb or stats["max_torque_ftlb"],
            max_torque_rpm=meta.max_torque_rpm or stats["max_torque_rpm"],
        )
        updated.append(updated_meta)
    return updated


__all__ = ["extract_dynostar_overlays", "annotate_meta_with_ocr"]
