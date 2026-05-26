"""PVV (PowerVision XML) shared I/O for surgical tools.

This package centralizes the parsing + mutation primitives that every
patch generator in `dynoai/tools/` needs:

  - Read a table (axes + values + cell element refs) by Item id.
  - Read a scalar (single-cell Item) by Item id.
  - Mutate a table's cell values from a numpy array.
  - Serialize the tree back to disk with locked-in encoding/declaration
    parameters so output bytes are deterministic across callers.
  - Diff all cells across two roots and surface a GateFailure if any
    non-approved Item id changed.
  - Compute SHA-256 of an output file for the manifest.

Why this lives here rather than in api/services/integrations/powercore:
  - `surgical_pvv_writer.py` over there is multiplier-based for VE
    correction patches only. The tools in dynoai/tools/ have heterogeneous
    policies (additive spark pulls, GP posterior means, graft from donor).
    They share the *plumbing*, not the patch math.
  - Keeping the plumbing in dynoai/ aligns with the "math + calibration
    stays in dynoai" rule from AGENTS.md.

Byte-stability contract (do not change without re-pinning every SHA test):
  - `tree.write(path, encoding="utf-8", xml_declaration=True)` is the only
    serialization path. Adding pretty-print, changing encoding, or
    re-ordering attributes would shift every tool's output SHA.
  - `format_value` uses .4f-then-rstrip("0")-then-rstrip(".") to match the
    seanbike reference outputs exactly. Even a switch to `g` formatting
    would break SHA reproducibility.
"""

from dynoai.pvv.io import (
    TableData,
    collect_item_cells,
    find_item_by_id,
    format_value,
    mutate_scalar,
    mutate_table_cells,
    parse_scalar,
    parse_table,
    sha256,
    verify_integrity_or_cleanup,
    write_xml_tree,
)
from dynoai.pvv.surface_view import (
    load_ve_surfaces,
    ve_surface_from_pvv,
    ve_table_to_surface,
)

__all__ = [
    "TableData",
    "collect_item_cells",
    "find_item_by_id",
    "format_value",
    "load_ve_surfaces",
    "mutate_scalar",
    "mutate_table_cells",
    "parse_scalar",
    "parse_table",
    "sha256",
    "ve_surface_from_pvv",
    "ve_table_to_surface",
    "verify_integrity_or_cleanup",
    "write_xml_tree",
]
