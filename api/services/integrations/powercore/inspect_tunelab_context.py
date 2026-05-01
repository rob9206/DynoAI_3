# mypy: ignore-errors

# Inspect TuneLab context/table APIs in-place.
# Throwaway diagnostic helper for F1.1 table-name verification.

import clr

clr.AddReference("System")
clr.AddReference("System.Windows.Forms")

from System.Windows.Forms import MessageBox, MessageBoxButtons, MessageBoxIcon  # noqa: E402

APP_TITLE = "DynoAI TuneLab Context Probe"
VE_FRONT_TABLE_CANDIDATES = [
    "Volumetric Efficiency Front",
    "VE Front",
    "Volumetric Efficiency - Front",
    "Volumetric Efficiency Front Cylinder",
]
VE_REAR_TABLE_CANDIDATES = [
    "Volumetric Efficiency Rear",
    "VE Rear",
    "Volumetric Efficiency - Rear",
    "Volumetric Efficiency Rear Cylinder",
]


def _safe_dir(obj):
    try:
        names = [str(x) for x in dir(obj)]
        names.sort()
        return names
    except Exception:
        return []


def _probe_table(name):
    try:
        table = context.GetTable(name)  # noqa: F821
    except Exception as exc:
        return "%s -> ERROR: %s" % (name, str(exc))
    if table is None:
        return "%s -> None" % name

    api_names = _safe_dir(table)
    preview = ", ".join(api_names[:30]) + ("..." if len(api_names) > 30 else "")
    sample = None
    for row_idx, col_idx in ((0, 0), (1, 1)):
        try:
            sample = table.GetValue(row_idx, col_idx)
            break
        except Exception:
            try:
                sample = table[row_idx, col_idx]
                break
            except Exception:
                continue
    return "%s -> OK (sample=%s) APIs: %s" % (name, str(sample), preview)


def Run():
    lines = []
    context_names = _safe_dir(context)  # noqa: F821
    lines.append("context attrs (%d):" % len(context_names))
    lines.append(", ".join(context_names[:80]) + ("..." if len(context_names) > 80 else ""))

    try:
        tune_obj = context.tune  # noqa: F821
    except Exception:
        tune_obj = None
    if tune_obj is not None:
        tune_names = _safe_dir(tune_obj)
        lines.append("")
        lines.append("tune attrs (%d):" % len(tune_names))
        lines.append(", ".join(tune_names[:80]) + ("..." if len(tune_names) > 80 else ""))

    lines.append("")
    lines.append("Front table candidates:")
    for name in VE_FRONT_TABLE_CANDIDATES:
        lines.append(_probe_table(name))

    lines.append("")
    lines.append("Rear table candidates:")
    for name in VE_REAR_TABLE_CANDIDATES:
        lines.append(_probe_table(name))

    MessageBox.Show(
        "\r\n".join(lines),
        APP_TITLE,
        MessageBoxButtons.OK,
        MessageBoxIcon.Information,
    )


Run()
