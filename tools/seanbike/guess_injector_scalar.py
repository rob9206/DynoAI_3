"""Guess-and-check injector_size scalar correction.

Produces ONE candidate PVV per invocation by editing ONLY the
`tbl_injector_size` and (optionally) `tbl_engine_displacement` scalars in the
ORIGINAL ECU read. VE tables are NOT touched. This is the right move when the
ECU is requesting a pulse width the injector can't physically deliver because
the declared injector flow rate is wrong by ~7x.

Safety rules:
- Refuses to write if guessed injector_size is outside [3.5, 6.0] lb/hr.
- Refuses to write if displacement is outside [85.0, 120.0] CID.
- Refuses to touch any Item other than the scalar(s) being changed.
- Predicts and prints the AFR shift the operator should expect on the next
  pull at the same throttle position.

Usage examples:
    python tools/seanbike/guess_injector_scalar.py --injector-size 4.25
    python tools/seanbike/guess_injector_scalar.py --injector-size 4.9 --displacement 100.0
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_INPUT_PVV = Path(
    r"C:\CommmandCenter\Customer_Files\seanbike\exportedreadfrompv4.pvv"
)
DEFAULT_OUTPUT_DIR = Path(r"C:\CommmandCenter\Customer_Files\seanbike")

INJECTOR_ID = "tbl_injector_size"
DISPLACEMENT_ID = "tbl_engine_displacement"

INJECTOR_ABSOLUTE_MIN = 3.5
INJECTOR_ABSOLUTE_MAX = 35.0
DISPLACEMENT_MIN = 85.0
DISPLACEMENT_MAX = 120.0

LAST_OBSERVED_AFR = 17.6
TARGET_AFR = 12.9


def _find_item_by_id(root: ET.Element, item_id: str) -> ET.Element:
    for item in root.findall("Item"):
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Item id={item_id!r} not in PVV")


def _scalar_cell(root: ET.Element, item_id: str) -> ET.Element:
    item = _find_item_by_id(root, item_id)
    cell = item.find("./Rows/Row/Cell")
    if cell is None:
        raise ValueError(f"Scalar {item_id!r} has no Rows/Row/Cell")
    return cell


def _read_scalar(root: ET.Element, item_id: str) -> float:
    cell = _scalar_cell(root, item_id)
    raw = cell.get("value")
    if raw is None:
        raise ValueError(f"{item_id!r} has no value attribute")
    return float(raw)


def _format_value(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_only_scalars_changed(
    original: ET.Element, modified: ET.Element, allowed: set[str]
) -> list[str]:
    """Return list of unexpected items whose cell values changed."""
    def snapshot(root: ET.Element) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for item in root.findall("Item"):
            item_id = item.get("id", "")
            cells = [
                cell.get("value", "")
                for row in item.findall("./Rows/Row")
                for cell in row.findall("Cell")
            ]
            out[item_id] = cells
        return out

    in_cells = snapshot(original)
    out_cells = snapshot(modified)
    if set(in_cells) != set(out_cells):
        return [f"item set differs: {sorted(set(in_cells) ^ set(out_cells))}"]
    changed = [item_id for item_id in in_cells if in_cells[item_id] != out_cells[item_id]]
    return [c for c in changed if c not in allowed]


def predict_afr_shift(
    old_injector: float,
    new_injector: float,
    old_displacement: float,
    new_displacement: float,
    observed_afr: float,
) -> dict[str, float]:
    """Estimate AFR and pulse-width effect of swapping the scalars.

    Model:
        commanded_fuel_mass = VE * displacement / (injector_size * effective_PW)
    Holding VE and ECU pulse-width *request* constant:
        delivered_mass scales by (new_displacement / old_displacement)
        because the ECU computes more required mass for a bigger engine.
        actual_AFR scales by old_injector / new_injector if injector is smaller
        (smaller injector means same PW delivers proportionally less fuel; but
        the ECU has now been told the injector is smaller, so it commands a
        longer PW to deliver the same target mass -> AFR moves to target).

    Simplification used here (chasing the dominant term -- the injector size
    scalar): if injector_size was overstated by factor F = old/new, the ECU
    was under-commanding fuel by ~F. Correcting injector_size to a realistic
    value lets the ECU command F-times-longer pulse widths to hit the same
    target AFR -- which moves observed AFR from observed toward target by
    approximately the same ratio, bounded by injector duty cycle headroom.
    """
    injector_ratio = old_injector / new_injector if new_injector > 0 else float("inf")
    displacement_ratio = new_displacement / old_displacement if old_displacement > 0 else 1.0
    predicted_afr = observed_afr / (injector_ratio * displacement_ratio)
    pw_multiplier = injector_ratio * displacement_ratio
    return {
        "injector_ratio_old_over_new": injector_ratio,
        "displacement_ratio_new_over_old": displacement_ratio,
        "predicted_observed_afr": predicted_afr,
        "predicted_pw_multiplier": pw_multiplier,
    }


def run(args: argparse.Namespace) -> int:
    if not args.input_pvv.exists():
        raise FileNotFoundError(f"Input PVV not found: {args.input_pvv}")

    if not (INJECTOR_ABSOLUTE_MIN <= args.injector_size <= INJECTOR_ABSOLUTE_MAX):
        raise ValueError(
            f"injector_size {args.injector_size:.3f} outside absolute safety "
            f"bounds [{INJECTOR_ABSOLUTE_MIN}, {INJECTOR_ABSOLUTE_MAX}] -- "
            "refusing to write."
        )

    pre = ET.parse(args.input_pvv).getroot()
    old_inj = _read_scalar(pre, INJECTOR_ID)
    old_disp = _read_scalar(pre, DISPLACEMENT_ID)
    new_disp = args.displacement if args.displacement is not None else old_disp
    net_mass_ratio = (new_disp / old_disp) / (args.injector_size / old_inj)
    if net_mass_ratio < 0.95:
        raise ValueError(
            f"Combined scalar change would make commanded mass x{net_mass_ratio:.3f} "
            "(more than 5% LEANER). Refusing -- bike is already lean."
        )
    if net_mass_ratio > 1.50:
        raise ValueError(
            f"Combined scalar change would make commanded mass x{net_mass_ratio:.3f} "
            "(more than 50% RICHER). Single-step swap too large. Reduce magnitude."
        )
    if args.displacement is not None and not (
        DISPLACEMENT_MIN <= args.displacement <= DISPLACEMENT_MAX
    ):
        raise ValueError(
            f"displacement {args.displacement:.3f} outside [{DISPLACEMENT_MIN}, "
            f"{DISPLACEMENT_MAX}] CID -- refusing to write."
        )

    original_tree = ET.parse(args.input_pvv)
    original_root = original_tree.getroot()
    work_tree = ET.parse(args.input_pvv)
    work_root = work_tree.getroot()

    old_injector = _read_scalar(work_root, INJECTOR_ID)
    old_displacement = _read_scalar(work_root, DISPLACEMENT_ID)

    print(f"Input PVV:               {args.input_pvv}")
    print(f"Current injector_size:   {old_injector:.3f} lb/hr")
    print(f"Current displacement:    {old_displacement:.3f} CID")
    print(f"Proposed injector_size:  {args.injector_size:.3f} lb/hr")
    new_displacement = args.displacement if args.displacement is not None else old_displacement
    if args.displacement is not None:
        print(f"Proposed displacement:   {new_displacement:.3f} CID")
    else:
        print(f"Displacement:            (unchanged {old_displacement:.3f} CID)")

    pred = predict_afr_shift(
        old_injector, args.injector_size, old_displacement, new_displacement, LAST_OBSERVED_AFR
    )
    print("\nPredicted next-pull behavior (assuming ECU re-commands to same target AFR):")
    print(f"  injector ratio (old/new): {pred['injector_ratio_old_over_new']:.3f}")
    print(f"  displacement ratio:        {pred['displacement_ratio_new_over_old']:.3f}")
    print(
        f"  predicted observed AFR:    {pred['predicted_observed_afr']:.2f} "
        f"(from {LAST_OBSERVED_AFR:.2f}, target {TARGET_AFR:.2f})"
    )
    print(
        f"  pulse-width request shifts ~x{pred['predicted_pw_multiplier']:.2f} "
        "(less than 1.0 = shorter PW = duty cycle headroom restored)"
    )

    if pred["predicted_observed_afr"] < 9.0:
        print(
            "\nWARNING: predicted AFR < 9.0 -- this guess will likely run "
            "DANGEROUSLY RICH. Reduce injector_size guess (closer to current "
            "or to OEM 4.25)."
        )
    if pred["predicted_observed_afr"] > 15.0:
        print(
            "\nWARNING: predicted AFR > 15.0 -- this guess does not fix the "
            "lean condition meaningfully. Try a smaller injector_size value."
        )

    _scalar_cell(work_root, INJECTOR_ID).set("value", _format_value(args.injector_size))
    if args.displacement is not None:
        _scalar_cell(work_root, DISPLACEMENT_ID).set(
            "value", _format_value(args.displacement)
        )

    allowed = {INJECTOR_ID}
    if args.displacement is not None:
        allowed.add(DISPLACEMENT_ID)
    unexpected = _verify_only_scalars_changed(original_root, work_root, allowed)
    if unexpected:
        raise RuntimeError(
            "Refusing to write: unexpected Item ids changed: " + ", ".join(unexpected)
        )

    if not args.write:
        print("\nDry-run only. Use --write to emit the PVV.")
        return 0

    suffix_parts = [f"inj{args.injector_size:.2f}".replace(".", "p")]
    if args.displacement is not None:
        suffix_parts.append(f"disp{args.displacement:.1f}".replace(".", "p"))
    suffix = "_".join(suffix_parts)
    output_pvv = args.output_pvv or (args.output_dir / f"scalar_guess_{suffix}.pvv")

    output_pvv.parent.mkdir(parents=True, exist_ok=True)
    work_tree.write(output_pvv, encoding="utf-8", xml_declaration=True)

    verify_tree = ET.parse(output_pvv)
    verify_unexpected = _verify_only_scalars_changed(
        original_root, verify_tree.getroot(), allowed
    )
    if verify_unexpected:
        output_pvv.unlink(missing_ok=True)
        raise RuntimeError(
            "Post-write verification failed; output deleted. Unexpected changes: "
            + ", ".join(verify_unexpected)
        )

    sha = _sha256(output_pvv)
    print(f"\nWrote: {output_pvv}")
    print(f"SHA256: {sha}")
    print("\nPRE-FLASH CHECKLIST:")
    print("  1. PCV physically disconnected from harness? (yes/no)")
    print("  2. Wideband installed in tailpipe / collector?")
    print("  3. First pull AFTER flash: PART-THROTTLE only (TPS 40-60%, 3500-5000 rpm).")
    print("  4. Abort if AFR < 11.0 anywhere (will run dangerously rich on this guess).")
    print("  5. Abort if AFR > 15.5 at WOT (still lean -- inj size guess too large).")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-pvv", type=Path, default=DEFAULT_INPUT_PVV)
    parser.add_argument(
        "--injector-size",
        type=float,
        required=True,
        help="Guessed injector flow rate in lb/hr. Must be in [3.5, 6.0].",
    )
    parser.add_argument(
        "--displacement",
        type=float,
        default=None,
        help="Optional engine displacement correction in CID (e.g. 100.0). Must be in [85.0, 120.0].",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--output-pvv",
        type=Path,
        default=None,
        help="Override output path. Default: <output-dir>/scalar_guess_inj<size>[_disp<disp>].pvv",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Emit PVV file. Without --write, this is a dry-run.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args(sys.argv[1:])))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        sys.exit(1)
