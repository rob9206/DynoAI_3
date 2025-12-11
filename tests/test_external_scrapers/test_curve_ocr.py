from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from external_scrapers import curve_ocr
from external_scrapers.dyno_models import DynoChartMeta


def test_extract_dynostar_overlays_with_synthetic_text(monkeypatch) -> None:
    base_image = Image.new("RGB", (400, 200), "white")
    draw = ImageDraw.Draw(base_image)
    draw.text((10, 160), "Max Power = 121.34 at Engine RPM = 6.09", fill="black")
    draw.text((10, 175), "Max Torque = 132.5 at Engine RPM = 4.22", fill="black")

    out_dir = Path("tmp_test") / "ocr"
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / "chart.jpg"
    base_image.save(img_path)

    captured = {}

    def fake_ocr(image, config=None, lang=None):
        captured["size"] = image.size
        return "Max Power = 121.34 at Engine RPM = 6.09\nMax Torque = 132.5 at Engine RPM = 4.22"

    monkeypatch.setattr(curve_ocr.pytesseract, "image_to_string", fake_ocr)
    stats = curve_ocr.extract_dynostar_overlays(str(img_path))

    assert stats["max_power_hp"] == 121.34
    assert stats["max_power_rpm"] == 6090.0
    assert stats["max_torque_ftlb"] == 132.5
    assert stats["max_torque_rpm"] == 4220.0
    # Ensure the crop was applied (height shrinks)
    assert captured["size"][1] < base_image.size[1]


def test_extract_dynostar_overlays_handles_bad_text(monkeypatch) -> None:
    img_dir = Path("tmp_test") / "ocr_bad"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / "chart.jpg"
    Image.new("RGB", (100, 50)).save(img_path)

    monkeypatch.setattr(
        curve_ocr.pytesseract,
        "image_to_string",
        lambda image, config=None, lang=None: "noise",
    )
    stats = curve_ocr.extract_dynostar_overlays(str(img_path))
    assert all(value is None for value in stats.values())


def test_annotate_meta_with_ocr(monkeypatch) -> None:
    img_dir = Path("tmp_test") / "ocr_meta"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / "chart.jpg"
    Image.new("RGB", (100, 50)).save(img_path)

    monkeypatch.setattr(
        curve_ocr,
        "extract_dynostar_overlays",
        lambda path: {
            "max_power_hp": 100.0,
            "max_power_rpm": 5500.0,
            "max_torque_ftlb": 120.0,
            "max_torque_rpm": 3200.0,
        },
    )

    meta = DynoChartMeta(
        source="fuelmoto",
        id="sample",
        category="Test",
        title="Test",
        page_url="https://example.com",
        image_url=None,
        image_file=str(img_path),
    )
    updated = curve_ocr.annotate_meta_with_ocr([meta])[0]
    assert updated.max_power_hp == 100.0
    assert updated.max_torque_ftlb == 120.0
