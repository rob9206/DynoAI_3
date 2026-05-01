# api/services/integrations/powercore/dynoai_autotune.py
# DynoAI TuneLab autotune preview bridge (F1).
#
# IronPython 2.7 script loaded by Power Core TuneLab.
# Preview/export only: no PutTable writes in this release.
# mypy: ignore-errors
# fmt: off
# isort: skip_file
# autopep8: off
#
# IMPORTANT FOR AUTOFORMATTERS:
# Do not reorder these imports. The CLR / System.* imports must follow
# clr.AddReference(), and the optional-import fallbacks below are flat
# top-level statements on purpose. A previous autoformat pass split a single
# `try: ... except:` block across CLR imports and produced a P0 IndentationError
# that prevented the script from loading inside Power Core. Keep the structure
# below: each fallback is its own self-contained `try/except`, and the json
# fallback uses a single-line guarded assignment that no formatter will break.

import re

import clr

clr.AddReference("System")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

# json: prefer stdlib, fall back to None on stripped IronPython distributions.
# Single-line guarded form so isort/black/yapf cannot split a `try:` block.
try: import json as _py_json  # noqa: E701,E401
except Exception: _py_json = None  # noqa: E701,E722

# CLR namespaces -- IronPython 2.7 sometimes exposes these without the System.
# prefix on legacy Power Core builds, so each block is its own try/except.
try:
    from System import DateTime, Environment, Guid
except Exception:
    from DateTime import DateTime  # type: ignore[no-redef]
    from Environment import Environment  # type: ignore[no-redef]
    from Guid import Guid  # type: ignore[no-redef]

try:
    from System.Diagnostics import Process, ProcessStartInfo
except Exception:
    from Diagnostics import Process, ProcessStartInfo  # type: ignore[no-redef]

try:
    from System.Drawing import Color, Point, Size
except Exception:
    from Drawing import Color, Point, Size  # type: ignore[no-redef]

try:
    from System.IO import Directory, File, Path
except Exception:
    from IO import Directory, File, Path  # type: ignore[no-redef]

try:
    from System.Windows.Forms import (
        Button,
        DialogResult,
        Form,
        FormBorderStyle,
        FormStartPosition,
        GroupBox,
        Label,
        MessageBox,
        MessageBoxButtons,
        MessageBoxIcon,
    )
except Exception:
    from Windows.Forms import (  # type: ignore[no-redef]
        Button,
        DialogResult,
        Form,
        FormBorderStyle,
        FormStartPosition,
        GroupBox,
        Label,
        MessageBox,
        MessageBoxButtons,
        MessageBoxIcon,
    )

from tunelab import ConfigurableChannelProvider


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_REPO_ROOT = r"C:\Dev\DynoAI_3"
DEFAULT_PYTHON = r"C:\Dev\DynoAI_3\.venv\Scripts\python.exe"
BRIDGE_VERSION = "v1.0.0"
APP_TITLE = "DynoAI Autotune (Preview) " + BRIDGE_VERSION
APP_TITLE_SHORT = "DynoAI Autotune"
WARN_THRESHOLD_PCT = 10.0
CLI_TIMEOUT_SECONDS = 60
APPLY_TIMEOUT_SECONDS = 120
VE_FRONT_TABLE_NAME = "Volumetric Efficiency Front"
VE_REAR_TABLE_NAME = "Volumetric Efficiency Rear"
APPLY_MAX_ADJUST_PCT = 15.0

# CLI <-> IronPython mode constants. Must mirror tools/autotune/tunelab_entrypoint.py.
# Previously referenced as bare globals in `_perform_apply` without being defined,
# producing NameError before the apply dialog could render.
MODE_DUAL = "dual_cylinder"
MODE_SINGLE_FRONT = "single_cylinder_front"
MODE_SINGLE_REAR = "single_cylinder_rear"
MODE_CHOICES = (MODE_DUAL, MODE_SINGLE_FRONT, MODE_SINGLE_REAR)


_RUN_SLUG_INVALID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_run_slug(run_id):
    """Sanitize run_id to a filesystem-safe segment.

    Mirrors tools.autotune.tunelab_entrypoint._safe_run_slug so a single
    run_id sanitizer is applied on both sides of the CLI boundary. Strips
    `..`, slashes, and any non [A-Za-z0-9._-] characters; collapses runs of
    invalid characters into a single underscore. Returns "run" if the
    result is empty so we never produce a zero-length path segment.
    """
    if run_id is None:
        return "run"
    text = str(run_id).strip()
    if not text:
        return "run"
    slug = _RUN_SLUG_INVALID_RE.sub("_", text)
    slug = slug.strip("_")
    if not slug or slug in (".", ".."):
        return "run"
    return slug

VE_FRONT_TABLE_CANDIDATES = [
    VE_FRONT_TABLE_NAME,
    "VE Front",
    "Volumetric Efficiency - Front",
    "Volumetric Efficiency Front Cylinder",
]
VE_REAR_TABLE_CANDIDATES = [
    VE_REAR_TABLE_NAME,
    "VE Rear",
    "Volumetric Efficiency - Rear",
    "Volumetric Efficiency Rear Cylinder",
]

RPM_CHANNEL_ALIASES = [
    "Engine RPM",
    "RPM",
    "Engine Speed",
    "EngineSpeed",
    "RPM (Engine)",
    "Engine",
]
MAP_CHANNEL_ALIASES = [
    "MAP kPa",
    "MAP",
    "MAP_kPa",
    "MAP (kPa)",
    "MAP Front",
    "MAP Rear",
    "Manifold Pressure",
    "Manifold Absolute Pressure",
    "Intake Manifold Pressure",
    "MAP Pressure",
    "MAP (Engine)",
    "Intake MAP",
]
AFR_F_ALIASES = [
    "WBO2 AFR Front",
    "AFR Front",
    "AFR F",
    "AFR 1",
    "AFR #1",
    "AFR_1",
    "AFR 1F",
    "AFR F1",
    "AFR1",
    "AFR Meas F",
    "A/F Ratio 1",
    "A/F 1",
    "A/F F",
    "Air/Fuel Ratio 1",
    "Air/Fuel Ratio F",
    "Air Fuel Ratio 1",
    "WBO2 F",
    "WBO2F",
    "WBO2 #1",
    "WB O2 F",
    "Wideband F",
    "Wideband 1",
    "Wideband AFR 1",
    "Wideband AFR F",
    "DLG-1 AFR F",
    "DLG AFR F",
    "LC-1 AFR F",
    "LC-2 AFR F",
    "LC2 AFR F",
    "LC1 AFR F",
    "Innovate AFR F",
]
AFR_R_ALIASES = [
    "WBO2 AFR Rear",
    "AFR Rear",
    "AFR R",
    "AFR 2",
    "AFR #2",
    "AFR_2",
    "AFR 2R",
    "AFR R2",
    "AFR2",
    "AFR Meas R",
    "A/F Ratio 2",
    "A/F 2",
    "A/F R",
    "Air/Fuel Ratio 2",
    "Air/Fuel Ratio R",
    "Air Fuel Ratio 2",
    "WBO2 R",
    "WBO2R",
    "WBO2 #2",
    "WB O2 R",
    "Wideband R",
    "Wideband 2",
    "Wideband AFR 2",
    "Wideband AFR R",
    "DLG-1 AFR R",
    "DLG AFR R",
    "LC-1 AFR R",
    "LC-2 AFR R",
    "LC2 AFR R",
    "LC1 AFR R",
    "Innovate AFR R",
]
# Lambda aliases — distinct from AFR aliases. Lambda values are 0-2; they
# MUST be converted to AFR by the CLI (tools.autotune.tunelab_entrypoint
# calls api.services.jetdrive.jetdrive_mapping.lambda_to_afr).
AFR_F_LAMBDA_ALIASES = [
    "WBO2 LAMBDA Front",
    "Lambda Front",
    "Lambda F",
    "Lambda 1",
    "AT Lambda 1",
    "LC-1 Lambda F",
    "LC-2 Lambda F",
    "Wideband Lambda F",
    "Wideband Lambda 1",
]
AFR_R_LAMBDA_ALIASES = [
    "WBO2 LAMBDA Rear",
    "Lambda Rear",
    "Lambda R",
    "Lambda 2",
    "AT Lambda 2",
    "LC-1 Lambda R",
    "LC-2 Lambda R",
    "Wideband Lambda R",
    "Wideband Lambda 2",
]
AFR_F_VOLT_ALIASES = [
    "LC2 Volts Petrol AFR1",
    "LC-2 Volts Petrol AFR1",
    "LC2 Volts AFR1",
    "LC-2 Volts AFR1",
    "LC1 Volts AFR1",
    "WBO2 F Volts",
    "WBO2 Volts F",
    "Wideband Volts F",
    "Wideband Volts 1",
    "Innovate Volts F",
    "Innovate Volts 1",
    "AFR Volts F",
    "AFR Volts 1",
]
AFR_R_VOLT_ALIASES = [
    "LC2 Volts Petrol AFR2",
    "LC-2 Volts Petrol AFR2",
    "LC2 Volts AFR2",
    "LC-2 Volts AFR2",
    "LC1 Volts AFR2",
    "WBO2 R Volts",
    "WBO2 Volts R",
    "Wideband Volts R",
    "Wideband Volts 2",
    "Innovate Volts R",
    "Innovate Volts 2",
    "AFR Volts R",
    "AFR Volts 2",
]
TPS_ALIASES = [
    "TPS",
    "TP",
    "Throttle Position",
    "Throttle",
    "Throttle Position Sensor",
]

# Broad probe list for diagnostics when strict aliases fail.
DIAG_PROBE_NAMES = (
    RPM_CHANNEL_ALIASES
    + MAP_CHANNEL_ALIASES
    + AFR_F_ALIASES
    + AFR_R_ALIASES
    + AFR_F_VOLT_ALIASES
    + AFR_R_VOLT_ALIASES
    + TPS_ALIASES
    + [
        "B+",
        "VBatt",
        "Battery",
        "Battery Voltage",
        "ET",
        "Engine Temp",
        "ECT",
        "Coolant Temp",
        "Engine Temperature",
        "IAT",
        "Intake Air Temp",
        "Intake Temperature",
        "Vehicle Speed",
        "Gear",
        "Spark Advance",
        "Ignition Timing",
        "Injector Duty",
        "Injector Pulse Width",
        "Fuel Pressure",
        "Oil Pressure",
        "Oil Temp",
        "Knock",
        "Knock Retard",
        "Horsepower",
        "HP",
        "Torque",
        "TQ",
    ]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode(data):
    """Decode process output into a string, tolerating mixed encodings."""
    if data is None:
        return ""
    try:
        if isinstance(data, unicode):
            return data
    except NameError:
        pass
    if isinstance(data, str):
        try:
            return data.decode("utf-8")
        except Exception:
            try:
                return data.decode("cp1252", "replace")
            except Exception:
                return data
    return data


def _resolve_python():
    if File.Exists(DEFAULT_PYTHON):
        return DEFAULT_PYTHON
    return "python"


def _quote_arg(arg):
    s = str(arg)
    if s == "":
        return '""'
    if '"' in s:
        s = s.replace('"', '\\"')
    if (" " in s) or ("\t" in s):
        return '"' + s + '"'
    return s


def run_cli(args, timeout_seconds):
    """Run the Python CLI via .NET ProcessStartInfo."""
    psi = ProcessStartInfo()
    psi.FileName = _resolve_python()
    psi.Arguments = " ".join([_quote_arg(a) for a in args])
    psi.WorkingDirectory = DEFAULT_REPO_ROOT
    psi.UseShellExecute = False
    psi.RedirectStandardOutput = True
    psi.RedirectStandardError = True
    psi.CreateNoWindow = True

    proc = Process()
    proc.StartInfo = psi
    proc.Start()

    raw_out = proc.StandardOutput.ReadToEnd()
    raw_err = proc.StandardError.ReadToEnd()
    if not proc.WaitForExit(int(timeout_seconds * 1000)):
        try:
            proc.Kill()
        except Exception:
            pass
        return 124, _decode(raw_out), "[F1][ERR] cli_timeout"

    return proc.ExitCode, _decode(raw_out), _decode(raw_err)


def _extract_summary_path(stdout):
    if not stdout:
        return None
    for line in stdout.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("[F1][OK] summary="):
            return trimmed.split("=", 1)[1].strip()
    return None


def _extract_f1_error(stderr):
    if not stderr:
        return None
    for line in stderr.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("[F1][ERR]"):
            return trimmed
    return None


def _try_channel(file_handle, aliases):
    for name in aliases:
        try:
            ch = channels.GetChannelByName(name, file_handle)  # noqa: F821
            if ch is not None:
                return ch
        except Exception:
            continue
    return None


def _list_channel_names(file_handle):
    """Best-effort enumeration of channel names in a loaded file.

    First tries several real TuneLab enumeration APIs (which vary by build).
    If none exist, falls back to probing DIAG_PROBE_NAMES via GetChannelByName
    so the user can still see which common channels are present.
    """
    names = []
    seen = set()

    def _add(value):
        try:
            s = str(value)
        except Exception:
            return
        if not s or s in seen:
            return
        seen.add(s)
        names.append(s)

    candidates = [
        lambda: getattr(file_handle, "Channels", None),
        lambda: getattr(file_handle, "ChannelNames", None),
        lambda: channels.GetChannels(file_handle),  # noqa: F821
        lambda: channels.GetAllChannels(file_handle),  # noqa: F821
        lambda: channels.GetChannelNames(file_handle),  # noqa: F821
        lambda: channels.ListChannels(file_handle),  # noqa: F821
    ]

    for getter in candidates:
        try:
            result = getter()
        except Exception:
            continue
        if result is None:
            continue
        try:
            for item in result:
                name_attr = getattr(item, "Name", None) or getattr(item, "name", None)
                if name_attr is not None:
                    _add(name_attr)
                else:
                    _add(item)
        except Exception:
            continue

    if names:
        return names

    # Fallback: actively probe known names via GetChannelByName.
    for name in DIAG_PROBE_NAMES:
        try:
            ch = channels.GetChannelByName(name, file_handle)  # noqa: F821
        except Exception:
            ch = None
        if ch is not None:
            _add(name)

    return names


def _describe_file_handle(file_handle):
    """Return a short human string describing a loaded file handle."""
    for attr in ["FilePath", "Path", "FileName", "Name"]:
        try:
            value = getattr(file_handle, attr)
        except Exception:
            value = None
        if value:
            return str(value)
    return str(file_handle)


def _read_samples(channel):
    samples = []
    if channel is None:
        return samples
    for sample in channel.GetAllSamples():
        try:
            t_ms = int(sample.TimeMillis)
            value = float(sample.Value)
        except Exception:
            continue
        samples.append((t_ms, value))
    return samples


def _value_at_or_before(samples, target_ms, idx_hint):
    """Step forward through a sorted sample list and return latest <= target."""
    if not samples:
        return None, idx_hint
    idx = idx_hint
    if idx < 0:
        idx = 0
    while (idx + 1) < len(samples) and samples[idx + 1][0] <= target_ms:
        idx += 1
    if samples[idx][0] > target_ms:
        return None, idx
    return samples[idx][1], idx


def _create_temp_dir():
    temp_dir = Path.Combine(
        Path.GetTempPath(), "dynoai_autotune_" + Guid.NewGuid().ToString("N")
    )
    Directory.CreateDirectory(temp_dir)
    return temp_dir


def _safe_delete_dir(path_value):
    if not path_value:
        return
    try:
        if Directory.Exists(path_value):
            Directory.Delete(path_value, True)
    except Exception:
        pass


def _sanitize_name(raw):
    if not raw:
        return "loaded_log"
    chars = []
    for ch in str(raw):
        if ch.isalnum() or ch in ("-", "_"):
            chars.append(ch)
        else:
            chars.append("_")
    value = "".join(chars).strip("_")
    if not value:
        return "loaded_log"
    return value


def _derive_log_stem(file_handle):
    for attr in ["FilePath", "Path", "FileName", "Name"]:
        try:
            value = getattr(file_handle, attr)
        except Exception:
            value = None
        if value:
            try:
                stem = Path.GetFileNameWithoutExtension(str(value))
            except Exception:
                stem = str(value)
            if stem:
                return _sanitize_name(stem)
    return "loaded_log"


def _build_run_id(file_handle):
    date_part = DateTime.Now.ToString("yyyyMMdd")
    stem = _derive_log_stem(file_handle)
    return "auto/%s/%s" % (date_part, stem)


def _estimate_map_from_rpm(rpm_value):
    try:
        rpm = float(rpm_value)
    except Exception:
        return 60.0
    if rpm < 2000:
        return 35.0
    if rpm < 3500:
        return 50.0
    if rpm < 5000:
        return 65.0
    return 80.0


def _resolve_afr_or_voltage(
    file_handle, afr_aliases, volt_aliases, lambda_aliases=None
):
    """Resolve AFR input: prefer AFR-unit, fall back to voltage, then Lambda.

    Returns (channel, column_name). ``column_name`` is:
        - None when the channel is an AFR-unit channel (caller uses canonical
          "AFR Meas F/R" header).
        - A raw voltage alias when a voltage wideband channel is selected
          (CLI converts via wideband_rescale.canonicalize_wideband_sample).
        - A raw lambda alias when only Lambda is available (CLI converts via
          jetdrive_mapping.lambda_to_afr).
    """
    afr_ch = _try_channel(file_handle, afr_aliases)
    if afr_ch is not None:
        return afr_ch, None

    for name in volt_aliases:
        try:
            ch = channels.GetChannelByName(name, file_handle)  # noqa: F821
        except Exception:
            ch = None
        if ch is not None:
            return ch, name

    if lambda_aliases:
        for name in lambda_aliases:
            try:
                ch = channels.GetChannelByName(name, file_handle)  # noqa: F821
            except Exception:
                ch = None
            if ch is not None:
                return ch, name

    return None, None


def _resolve_channels(file_handle):
    """Probe all required channels without raising.

    Returns a dict with resolved channels and voltage-mode names. Callers
    decide how to handle missing sides (dual vs single-cylinder).
    """
    rpm_ch = _try_channel(file_handle, RPM_CHANNEL_ALIASES)
    map_ch = _try_channel(file_handle, MAP_CHANNEL_ALIASES)
    afr_f_ch, front_volt_name = _resolve_afr_or_voltage(
        file_handle, AFR_F_ALIASES, AFR_F_VOLT_ALIASES, AFR_F_LAMBDA_ALIASES
    )
    afr_r_ch, rear_volt_name = _resolve_afr_or_voltage(
        file_handle, AFR_R_ALIASES, AFR_R_VOLT_ALIASES, AFR_R_LAMBDA_ALIASES
    )
    tps_ch = _try_channel(file_handle, TPS_ALIASES)
    return {
        "rpm_ch": rpm_ch,
        "map_ch": map_ch,
        "afr_f_ch": afr_f_ch,
        "afr_r_ch": afr_r_ch,
        "tps_ch": tps_ch,
        "front_volt_name": front_volt_name,
        "rear_volt_name": rear_volt_name,
    }


def _raise_channel_error(file_handle, missing, found_afr_f, found_afr_r):
    """Build the diagnostic error dialog for missing required channels."""
    available = _list_channel_names(file_handle)
    file_desc = _describe_file_handle(file_handle)
    nl = "\r\n"

    if available:
        preview = ", ".join(available[:40])
        extra_lines = [
            "",
            "Selected file: " + file_desc,
            "Detected channels (%d):" % len(available),
            preview + ("..." if len(available) > 40 else ""),
        ]
    else:
        extra_lines = [
            "",
            "Selected file: " + file_desc,
            "No known channels resolved via GetChannelByName or",
            "enumeration APIs. Check that the correct log is loaded",
            "in Data Center.",
        ]

    extra = nl.join(extra_lines)

    if ("AFR Front" in missing) or ("AFR Rear" in missing):
        raise RuntimeError(
            "Cannot find any AFR channel in the loaded log."
            + nl
            + "Missing: "
            + ", ".join(missing)
            + extra
        )
    raise RuntimeError("Missing required channels: " + ", ".join(missing) + extra)


def _channel_score(file_handle):
    score = 0
    rpm_ch = _try_channel(file_handle, RPM_CHANNEL_ALIASES)
    map_ch = _try_channel(file_handle, MAP_CHANNEL_ALIASES)
    afr_f_ch, front_raw_name = _resolve_afr_or_voltage(
        file_handle, AFR_F_ALIASES, AFR_F_VOLT_ALIASES, AFR_F_LAMBDA_ALIASES
    )
    afr_r_ch, rear_raw_name = _resolve_afr_or_voltage(
        file_handle, AFR_R_ALIASES, AFR_R_VOLT_ALIASES, AFR_R_LAMBDA_ALIASES
    )
    if rpm_ch is not None:
        score += 1
    if map_ch is not None:
        score += 1
    # Prefer AFR-unit channels over voltage/lambda (which need conversion).
    if afr_f_ch is not None:
        score += 2 if front_raw_name is None else 1
    if afr_r_ch is not None:
        score += 2 if rear_raw_name is None else 1
    return score


def _select_best_file_handle(file_handles):
    if not file_handles:
        return None
    # Prefer the file that actually carries dual-cylinder AFR + RPM signals.
    best_handle = None
    best_score = -1
    for fh in file_handles:
        score = _channel_score(fh)
        if score > best_score:
            best_score = score
            best_handle = fh
    return best_handle if best_handle is not None else file_handles[-1]


def _export_loaded_log_csv(file_handle, csv_path):
    """Export loaded channels to a DynoAI-format CSV. Returns (rows, mode).

    mode is one of "dual", "single_front", "single_rear". When a cylinder's
    AFR channel is missing or has no samples, its column is simply omitted
    from the CSV and the CLI gets --single-cylinder on the remaining side.
    """
    resolved = _resolve_channels(file_handle)
    rpm_ch = resolved["rpm_ch"]
    map_ch = resolved["map_ch"]
    afr_f_ch = resolved["afr_f_ch"]
    afr_r_ch = resolved["afr_r_ch"]
    tps_ch = resolved["tps_ch"]
    front_volt_name = resolved["front_volt_name"]
    rear_volt_name = resolved["rear_volt_name"]

    missing = []
    if rpm_ch is None:
        missing.append("RPM")
    if afr_f_ch is None and afr_r_ch is None:
        missing.append("AFR Front")
        missing.append("AFR Rear")
    if missing:
        _raise_channel_error(
            file_handle, missing, afr_f_ch is not None, afr_r_ch is not None
        )

    rpm_samples = _read_samples(rpm_ch)
    map_samples = _read_samples(map_ch)
    afr_f_samples = _read_samples(afr_f_ch) if afr_f_ch is not None else []
    afr_r_samples = _read_samples(afr_r_ch) if afr_r_ch is not None else []
    tps_samples = _read_samples(tps_ch)

    if not rpm_samples:
        raise RuntimeError("RPM channel has no samples.")

    front_has_data = bool(afr_f_samples)
    rear_has_data = bool(afr_r_samples)

    if not front_has_data and not rear_has_data:
        missing = []
        if afr_f_ch is None:
            missing.append("AFR Front")
        else:
            missing.append("AFR Front (no samples)")
        if afr_r_ch is None:
            missing.append("AFR Rear")
        else:
            missing.append("AFR Rear (no samples)")
        _raise_channel_error(file_handle, missing, False, False)

    if front_has_data and rear_has_data:
        mode = "dual"
    elif front_has_data:
        mode = "single_front"
    else:
        mode = "single_rear"

    # Preserve the raw voltage channel name so the CLI can detect and
    # convert via api.services.jetdrive.wideband_rescale (single point of
    # conversion). For AFR-unit channels we use the canonical column name.
    front_col = front_volt_name or "AFR Meas F"
    rear_col = rear_volt_name or "AFR Meas R"

    map_idx = 0
    afr_f_idx = 0
    afr_r_idx = 0
    tps_idx = 0
    row_count = 0

    with open(csv_path, "wb") as handle:
        header = ["timestamp_ms", "Engine RPM", "MAP kPa"]
        if front_has_data:
            header.append(front_col)
        if rear_has_data:
            header.append(rear_col)
        if tps_samples:
            header.append("TPS")
        handle.write((",".join(header) + "\n"))

        for t_ms, rpm_value in rpm_samples:
            if map_samples:
                map_value, map_idx = _value_at_or_before(map_samples, t_ms, map_idx)
            else:
                map_value = _estimate_map_from_rpm(rpm_value)
            if map_value is None:
                continue

            row_values = [
                t_ms,
                "%.3f" % rpm_value,
                "%.3f" % map_value,
            ]

            if front_has_data:
                afr_f_value, afr_f_idx = _value_at_or_before(
                    afr_f_samples, t_ms, afr_f_idx
                )
                if afr_f_value is None:
                    continue
                row_values.append("%.3f" % afr_f_value)
            if rear_has_data:
                afr_r_value, afr_r_idx = _value_at_or_before(
                    afr_r_samples, t_ms, afr_r_idx
                )
                if afr_r_value is None:
                    continue
                row_values.append("%.3f" % afr_r_value)
            if tps_samples:
                tps_value, tps_idx = _value_at_or_before(tps_samples, t_ms, tps_idx)
                row_values.append("" if tps_value is None else ("%.3f" % tps_value))

            handle.write(",".join([str(v) for v in row_values]) + "\n")
            row_count += 1

    if row_count == 0:
        raise RuntimeError("No aligned rows could be exported from loaded channels.")

    return row_count, mode


def _dotnet_to_python(value):
    """Recursively convert .NET Dictionary/List to native Python dict/list.

    ``JavaScriptSerializer.DeserializeObject`` returns .NET containers:
        JSON object -> System.Collections.Generic.Dictionary[str, object]
        JSON array  -> object[]
        primitives  -> mapped to IronPython native types

    These .NET containers do not support ``.get``, have different truthy
    semantics, and break downstream code expecting dicts/lists. Convert
    eagerly at the deserialize boundary so every caller is on Python types.
    """
    if value is None:
        return None

    # Bool first (bool is also an int in IronPython; keep it a Python bool).
    if isinstance(value, bool):
        return bool(value)

    # String types: return as-is; do NOT iterate char-by-char.
    try:
        if isinstance(value, unicode):  # noqa: F821 - IronPython 2.7
            return value
    except NameError:
        pass
    if isinstance(value, str):
        return value

    # Dict-like: .NET Dictionary has a ``Keys`` collection.
    try:
        keys = value.Keys
    except Exception:
        keys = None
    if keys is not None:
        result = {}
        try:
            for key in keys:
                result[str(key)] = _dotnet_to_python(value[key])
            return result
        except Exception:
            # Fall through to iterable handling on unexpected shape.
            pass

    # Sequence-like: object[], List[object], any IEnumerable.
    try:
        items = [_dotnet_to_python(item) for item in value]
        return items
    except TypeError:
        pass

    # Numeric primitive or any pass-through value.
    return value


def _load_summary(summary_path):
    raw_text = File.ReadAllText(summary_path)

    # Prefer Python json when available.
    if _py_json is not None:
        try:
            return _py_json.loads(raw_text)
        except Exception:
            pass

    # TuneLab IronPython builds can omit json; fall back to .NET serializer.
    try:
        clr.AddReference("System.Web.Extensions")
        from System.Web.Script.Serialization import JavaScriptSerializer

        serializer = JavaScriptSerializer()
        raw_value = serializer.DeserializeObject(raw_text)
        return _dotnet_to_python(raw_value)
    except Exception as exc:
        raise RuntimeError("Unable to parse correction_summary.json: %s" % str(exc))


def _to_metric(value, decimals):
    try:
        return ("%." + str(decimals) + "f") % float(value)
    except Exception:
        return str(value)


def _safe_get(mapping, key, default=None):
    """Read a key from either a Python dict or a .NET Dictionary.

    After ``_load_summary`` runs the ``_dotnet_to_python`` conversion this
    should always hit the Python dict path, but keeping a fallback makes
    the dialog code robust against any future deserializer regression.
    """
    if mapping is None:
        return default
    try:
        return mapping.get(key, default)
    except AttributeError:
        pass
    try:
        if mapping.ContainsKey(key):
            return mapping[key]
    except Exception:
        pass
    try:
        return mapping[key]
    except Exception:
        return default


def _json_dumps(value):
    if _py_json is not None:
        try:
            return _py_json.dumps(value)
        except Exception:
            pass
    try:
        clr.AddReference("System.Web.Extensions")
        from System.Web.Script.Serialization import JavaScriptSerializer

        serializer = JavaScriptSerializer()
        return serializer.Serialize(value)
    except Exception:
        return str(value)


def _format_axis_value(value):
    try:
        as_float = float(value)
    except Exception:
        return str(value)
    if int(as_float) == as_float:
        return str(int(as_float))
    text = "%.3f" % as_float
    return text.rstrip("0").rstrip(".")


def _coerce_float(value):
    text = str(value).strip()
    if text.startswith("'"):
        text = text[1:]
    return float(text)


def _parse_ve_csv(csv_path):
    if not File.Exists(csv_path):
        raise RuntimeError("Missing CSV: %s" % csv_path)

    with open(csv_path, "r") as handle:
        lines = handle.readlines()
    if not lines:
        raise RuntimeError("Empty CSV: %s" % csv_path)

    header_parts = [p.strip() for p in lines[0].strip().split(",")]
    if len(header_parts) < 2:
        raise RuntimeError("Invalid VE CSV header: %s" % csv_path)

    map_axis = [_coerce_float(v) for v in header_parts[1:]]
    rpm_axis = []
    grid = []
    for line in lines[1:]:
        raw = line.strip()
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 2:
            continue
        rpm_axis.append(_coerce_float(parts[0]))
        row = []
        for idx in range(1, len(map_axis) + 1):
            if idx < len(parts) and parts[idx] != "":
                row.append(_coerce_float(parts[idx]))
            else:
                row.append(0.0)
        grid.append(row)
    if not rpm_axis:
        raise RuntimeError("No VE rows in CSV: %s" % csv_path)
    return rpm_axis, map_axis, grid


def _write_ve_csv(csv_path, rpm_axis, map_axis, grid):
    with open(csv_path, "wb") as handle:
        header = ["RPM"] + [_format_axis_value(v) for v in map_axis]
        handle.write((",".join(header) + "\n"))
        for rpm, row in zip(rpm_axis, grid):
            values = ["%.6f" % float(v) for v in row]
            handle.write((_format_axis_value(rpm) + "," + ",".join(values) + "\n"))


def _table_get_value(table_obj, row_idx, col_idx):
    accessors = [
        lambda t, r, c: t.GetValue(r, c),
        lambda t, r, c: t.get_Item(r, c),
        lambda t, r, c: t[r, c],
    ]
    for accessor in accessors:
        try:
            value = accessor(table_obj, row_idx, col_idx)
            return float(value)
        except Exception:
            continue
    try:
        return float(table_obj[row_idx][col_idx])
    except Exception as exc:
        raise RuntimeError(
            "Unable to read table cell (%d,%d): %s" % (row_idx, col_idx, str(exc))
        )


def _table_set_value(table_obj, row_idx, col_idx, value):
    setters = [
        lambda t, r, c, v: t.SetValue(r, c, v),
        lambda t, r, c, v: t.set_Item(r, c, v),
        lambda t, r, c, v: t.SetCell(r, c, v),
    ]
    for setter in setters:
        try:
            setter(table_obj, row_idx, col_idx, value)
            return
        except Exception:
            continue
    try:
        table_obj[row_idx, col_idx] = value
        return
    except Exception:
        pass
    try:
        table_obj[row_idx][col_idx] = value
        return
    except Exception as exc:
        raise RuntimeError(
            "Unable to write table cell (%d,%d): %s" % (row_idx, col_idx, str(exc))
        )


def _extract_table_grid(table_obj, rows, cols):
    last_error = None
    for base_index in (0, 1):
        try:
            grid = []
            for r in range(rows):
                row = []
                for c in range(cols):
                    row.append(
                        _table_get_value(table_obj, r + base_index, c + base_index)
                    )
                grid.append(row)
            return grid, base_index
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError("Unable to read table grid: %s" % str(last_error))


def _apply_grid_to_table(table_obj, grid, base_index):
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            _table_set_value(table_obj, r + base_index, c + base_index, float(value))


def _context_probe_lines():
    try:
        names = [str(name) for name in dir(context)]  # noqa: F821
    except Exception:
        names = []
    if not names:
        return "context members unavailable"
    names.sort()
    return ", ".join(names[:80]) + ("..." if len(names) > 80 else "")


def _resolve_table_from_candidates(candidates, expected_rows, expected_cols):
    attempts = []
    for name in candidates:
        try:
            table_obj = context.GetTable(name)  # noqa: F821
            if table_obj is None:
                attempts.append("%s: returned None" % name)
                continue
            _, base_index = _extract_table_grid(table_obj, expected_rows, expected_cols)
            return table_obj, name, base_index
        except Exception as exc:
            attempts.append("%s: %s" % (name, str(exc)))
    detail = "\r\n".join(attempts) if attempts else "No candidates attempted."
    raise RuntimeError(
        "Could not resolve VE table from candidates.\r\n"
        "Candidates: %s\r\n%s\r\ncontext: %s"
        % (", ".join(candidates), detail, _context_probe_lines())
    )


def _extract_apply_paths(stdout):
    if not stdout:
        return None
    pattern = re.compile(
        r"^\[F1\]\[OK\]\s+apply_front=(\S+)\s+apply_rear=(\S+)\s+session_log=(\S+)\s*$"
    )
    for line in stdout.splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1), match.group(2), match.group(3)
    return None


def _append_apply_audit_log(
    summary, file_desc, front_table_name, rear_table_name, session_log_path
):
    logs_dir = Path.Combine(DEFAULT_REPO_ROOT, "logs")
    Directory.CreateDirectory(logs_dir)
    audit_path = Path.Combine(logs_dir, "autotune_applied.log")
    backup_path = Path.Combine(Path.GetDirectoryName(session_log_path), "snapshots")
    record = {
        "ts": DateTime.UtcNow.ToString("o"),
        "run_id": _safe_get(summary, "run_id", ""),
        "mode": _safe_get(summary, "mode", ""),
        "max_pct": _safe_get(summary, "overall_max_pct", 0.0),
        "backup_path": backup_path,
        "tables_written": [front_table_name, rear_table_name],
        "operator": str(Environment.UserName),
        "log_file": file_desc,
        "session_log": session_log_path,
    }
    payload = _json_dumps(record)
    with open(audit_path, "a") as handle:
        handle.write(payload + "\n")
    return audit_path


def _axes_match(expected_axis, actual_axis, epsilon=1e-6):
    if len(expected_axis) != len(actual_axis):
        return False
    for expected, actual in zip(expected_axis, actual_axis):
        try:
            if abs(float(expected) - float(actual)) > epsilon:
                return False
        except Exception:
            if str(expected) != str(actual):
                return False
    return True


class PreviewDialog(Form):
    def __init__(self, summary, preview_dir):
        self.summary = summary
        self.preview_dir = preview_dir
        self.action = None
        self._build_form()

    def _build_form(self):
        self.Text = APP_TITLE
        self.Size = Size(560, 430)
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimizeBox = False
        self.MaximizeBox = False

        banner = Label()
        banner.Location = Point(15, 12)
        banner.Size = Size(520, 52)
        mode = str(_safe_get(self.summary, "mode", "dual_cylinder"))
        safety = _safe_get(self.summary, "safety", {}) or {}
        apply_blocked = bool(_safe_get(safety, "apply_blocked", False))
        warn_threshold = float(
            _safe_get(safety, "warn_threshold_pct", WARN_THRESHOLD_PCT)
        )
        over_warn = bool(_safe_get(self.summary, "over_warn_threshold"))
        if apply_blocked and mode == MODE_DUAL:
            banner.Text = "APPLY BLOCKED: safety gates must pass before write-back."
            banner.ForeColor = Color.Red
        elif over_warn:
            banner.Text = (
                "WARNING: max correction exceeds %.0f%%. Review before any apply."
                % warn_threshold
            )
            banner.ForeColor = Color.DarkOrange
        elif mode == "single_cylinder_front":
            banner.Text = (
                "Single-wideband log (front). Only front correction will be exported. "
                "Rear is unchanged."
            )
            banner.ForeColor = Color.DarkOrange
        elif mode == "single_cylinder_rear":
            banner.Text = (
                "Single-wideband log (rear). Only rear correction will be exported. "
                "Front is unchanged."
            )
            banner.ForeColor = Color.DarkOrange
        else:
            banner.Text = "Preview only. Review outputs before any manual flash."
            banner.ForeColor = Color.DarkGreen
        self.Controls.Add(banner)

        front_group = self._build_cylinder_group(
            "Front (VE F)", _safe_get(self.summary, "front"), 15
        )
        rear_group = self._build_cylinder_group(
            "Rear (VE R)", _safe_get(self.summary, "rear"), 285
        )
        self.Controls.Add(front_group)
        self.Controls.Add(rear_group)

        # Footer details
        footer = Label()
        footer.Location = Point(15, 315)
        footer.Size = Size(520, 40)
        footer.Text = "run_id: %s\nsummary schema: v%s" % (
            _safe_get(self.summary, "run_id", "unknown"),
            _safe_get(self.summary, "schema_version", "?"),
        )
        self.Controls.Add(footer)

        show_apply = mode == MODE_DUAL
        if show_apply:
            btn_apply = Button()
            btn_apply.Text = "Apply to Loaded Tune"
            btn_apply.Location = Point(95, 360)
            btn_apply.Size = Size(140, 30)
            btn_apply.Enabled = not apply_blocked
            btn_apply.Click += self._on_apply
            self.Controls.Add(btn_apply)

            if apply_blocked:
                reasons = _safe_get(safety, "apply_blocked_reasons", []) or []
                messages = []
                for reason in reasons:
                    if isinstance(reason, dict):
                        msg = str(_safe_get(reason, "message", "")).strip()
                        if msg:
                            messages.append(msg)
                reason_label = Label()
                reason_label.Location = Point(15, 340)
                reason_label.Size = Size(520, 20)
                reason_label.ForeColor = Color.Red
                reason_label.Text = "Blocked: %s" % (
                    "; ".join(messages) if messages else "Unknown safety reason."
                )
                self.Controls.Add(reason_label)

        btn_export = Button()
        btn_export.Text = "Export Only"
        btn_export.Location = Point(245, 360)
        btn_export.Size = Size(90, 30)
        btn_export.Click += self._on_export
        self.Controls.Add(btn_export)

        btn_open = Button()
        btn_open.Text = "Open Folder"
        btn_open.Location = Point(345, 360)
        btn_open.Size = Size(90, 30)
        btn_open.Click += self._on_open_folder
        self.Controls.Add(btn_open)

        btn_cancel = Button()
        btn_cancel.Text = "Cancel"
        btn_cancel.Location = Point(445, 360)
        btn_cancel.Size = Size(90, 30)
        btn_cancel.Click += self._on_cancel
        self.Controls.Add(btn_cancel)

        self.AcceptButton = btn_export
        self.CancelButton = btn_cancel

    def _build_cylinder_group(self, title, section, x):
        group = GroupBox()
        group.Text = title
        group.Location = Point(x, 70)
        group.Size = Size(255, 230)

        if section is None:
            na_label = Label()
            na_label.Location = Point(10, 30)
            na_label.Size = Size(235, 60)
            na_label.Text = (
                "Not computed.\n"
                "This cylinder had no wideband samples\n"
                "in the loaded log."
            )
            na_label.ForeColor = Color.Gray
            group.Controls.Add(na_label)
            return group

        self._add_metric(
            group, "zones_adjusted", _safe_get(section, "zones_adjusted"), 30
        )
        self._add_metric(
            group,
            "max_correction_pct",
            _to_metric(_safe_get(section, "max_pct", 0.0), 2),
            60,
        )
        self._add_metric(
            group,
            "min_correction_pct",
            _to_metric(_safe_get(section, "min_pct", 0.0), 2),
            90,
        )
        self._add_metric(
            group, "clipped_zones", _safe_get(section, "clipped_zones"), 120
        )
        self._add_metric(
            group,
            "mean_afr_error",
            _to_metric(_safe_get(section, "mean_afr_error", 0.0), 3),
            150,
        )
        self._add_metric(
            group,
            "mean_ve_delta_pct",
            _to_metric(_safe_get(section, "mean_ve_delta_pct", 0.0), 3),
            180,
        )

        return group

    def _add_metric(self, group, name, value, y):
        label = Label()
        label.Location = Point(10, y)
        label.Size = Size(230, 24)
        label.Text = "%s: %s" % (name, value)
        group.Controls.Add(label)

    def _on_export(self, sender, args):
        self.action = "export"
        self.DialogResult = DialogResult.OK
        self.Close()

    def _on_apply(self, sender, args):
        self.action = "apply"
        self.DialogResult = DialogResult.OK
        self.Close()

    def _on_open_folder(self, sender, args):
        try:
            Process.Start("explorer.exe", self.preview_dir)
        except Exception as exc:
            MessageBox.Show(
                "Could not open folder:\n%s" % str(exc),
                APP_TITLE_SHORT,
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )

    def _on_cancel(self, sender, args):
        self.action = "cancel"
        self.DialogResult = DialogResult.Cancel
        self.Close()


def show_preview(summary, preview_dir):
    dialog = PreviewDialog(summary, preview_dir)
    dialog.ShowDialog()
    return dialog.action


def _copy_export_outputs(summary, summary_path, extra_files=None):
    run_id = str(_safe_get(summary, "run_id") or "").replace("\\", "/").strip("/")
    if not run_id:
        raise RuntimeError("Summary missing run_id; cannot resolve export destination.")

    # Sanitize each path segment so a hostile or accidentally-malformed
    # run_id (".." or absolute paths) cannot escape DEFAULT_REPO_ROOT/runs.
    raw_parts = [part for part in run_id.split("/") if part.strip()]
    safe_parts = [_safe_run_slug(part) for part in raw_parts]
    safe_parts = [part for part in safe_parts if part and part not in (".", "..")]
    if not safe_parts:
        raise RuntimeError("Summary run_id resolves to empty segments after sanitization.")

    dest_dir = Path.Combine(DEFAULT_REPO_ROOT, "runs")
    for part in safe_parts:
        dest_dir = Path.Combine(dest_dir, part)
    dest_dir = Path.Combine(dest_dir, "corrections")
    Directory.CreateDirectory(dest_dir)

    summary_dir = Path.GetDirectoryName(summary_path)
    files_to_copy = [summary_path]
    for side in ("front", "rear"):
        section = _safe_get(summary, side)
        if not section:
            continue
        csv_name = str(_safe_get(section, "csv", ""))
        if not csv_name:
            continue
        files_to_copy.append(Path.Combine(summary_dir, csv_name))
    pvv_name = str(_safe_get(summary, "pvv_patch", ""))
    if pvv_name:
        files_to_copy.append(Path.Combine(summary_dir, pvv_name))
    if extra_files:
        for extra in extra_files:
            if extra:
                files_to_copy.append(extra)

    for src in files_to_copy:
        if not src or not File.Exists(src):
            raise RuntimeError("Expected output file missing: %s" % src)
        dest = Path.Combine(dest_dir, Path.GetFileName(src))
        File.Copy(src, dest, True)

    return dest_dir


class _ErrorViewForm(Form):
    """Read-only scrollable error dialog so long channel lists stay visible."""

    def __init__(self, body):
        self.Text = APP_TITLE_SHORT + " (error)"
        self.Size = Size(720, 460)
        self.FormBorderStyle = FormBorderStyle.Sizable
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimizeBox = False
        self.MaximizeBox = True

        try:
            from System.Windows.Forms import (
                DockStyle,
                ScrollBars,
            )
            from System.Windows.Forms import TextBox as _TextBox
        except Exception:
            from Windows.Forms import DockStyle, ScrollBars
            from Windows.Forms import TextBox as _TextBox

        tb = _TextBox()
        tb.Multiline = True
        tb.ReadOnly = True
        tb.ScrollBars = ScrollBars.Vertical
        tb.WordWrap = True
        tb.Dock = DockStyle.Fill
        tb.Text = body
        self.Controls.Add(tb)

        btn_close = Button()
        btn_close.Text = "Close"
        btn_close.Dock = DockStyle.Bottom
        btn_close.Height = 34
        btn_close.Click += self._on_close
        self.Controls.Add(btn_close)
        self.AcceptButton = btn_close
        self.CancelButton = btn_close

    def _on_close(self, sender, args):
        self.DialogResult = DialogResult.OK
        self.Close()


def _show_error_dialog(body):
    try:
        rendered = body.replace("\r\n", "\n").replace("\n", "\r\n")
    except Exception:
        rendered = body
    try:
        form = _ErrorViewForm(rendered)
        form.ShowDialog()
    except Exception:
        # Fallback to a plain MessageBox if the custom form can't be built.
        MessageBox.Show(
            rendered,
            APP_TITLE_SHORT,
            MessageBoxButtons.OK,
            MessageBoxIcon.Error,
        )


def _show_cli_error(exit_code, stdout, stderr):
    f1_error = _extract_f1_error(stderr)
    body = "CLI failed (rc=%d)." % exit_code
    if f1_error:
        body += "\n\n%s" % f1_error
    if stderr:
        body += "\n\nstderr:\n%s" % stderr
    if stdout:
        body += "\n\nstdout:\n%s" % stdout
    MessageBox.Show(
        body,
        APP_TITLE_SHORT + " (error)",
        MessageBoxButtons.OK,
        MessageBoxIcon.Error,
    )


# ---------------------------------------------------------------------------
# TuneLab entrypoint
# ---------------------------------------------------------------------------


class DynoAIAutotune(ConfigurableChannelProvider):
    def _perform_apply(self, summary, summary_path, temp_dir, file_handle):
        mode = str(_safe_get(summary, "mode", MODE_DUAL))
        if mode != MODE_DUAL:
            raise RuntimeError(
                "Apply is only supported in dual-cylinder mode. Current mode: %s" % mode
            )

        confirm = MessageBox.Show(
            "Apply dual-cylinder corrections to the loaded tune?\r\n\r\n"
            "A snapshot will be saved to runs/<run_id>/snapshots/ before writing.\r\n"
            "Recommended: save a manual Power Core backup first (File -> Save As).",
            APP_TITLE_SHORT,
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning,
        )
        if confirm != DialogResult.Yes:
            return None

        grid = _safe_get(summary, "grid", {}) or {}
        rpm_axis = _safe_get(grid, "rpm_axis", []) or []
        map_axis = _safe_get(grid, "map_axis", []) or []
        if not rpm_axis or not map_axis:
            raise RuntimeError("Summary grid axes are missing; cannot apply.")

        expected_rows = len(rpm_axis)
        expected_cols = len(map_axis)
        front_table, front_table_name, _ = _resolve_table_from_candidates(
            VE_FRONT_TABLE_CANDIDATES, expected_rows, expected_cols
        )
        rear_table, rear_table_name, _ = _resolve_table_from_candidates(
            VE_REAR_TABLE_CANDIDATES, expected_rows, expected_cols
        )

        front_grid, front_index_base = _extract_table_grid(
            front_table, expected_rows, expected_cols
        )
        rear_grid, rear_index_base = _extract_table_grid(
            rear_table, expected_rows, expected_cols
        )

        front_base_csv = Path.Combine(temp_dir, "VE_Front_Base.csv")
        rear_base_csv = Path.Combine(temp_dir, "VE_Rear_Base.csv")
        _write_ve_csv(front_base_csv, rpm_axis, map_axis, front_grid)
        _write_ve_csv(rear_base_csv, rpm_axis, map_axis, rear_grid)

        apply_args = [
            "-m",
            "tools.autotune.tunelab_entrypoint",
            "apply",
            "--run-id",
            str(_safe_get(summary, "run_id", "")),
            "--output-dir",
            temp_dir,
            "--base-front",
            front_base_csv,
            "--base-rear",
            rear_base_csv,
            "--mode",
            MODE_DUAL,
            "--max-adjust-pct",
            str(APPLY_MAX_ADJUST_PCT),
        ]
        rc, stdout, stderr = run_cli(apply_args, timeout_seconds=APPLY_TIMEOUT_SECONDS)
        if rc != 0:
            _show_cli_error(rc, stdout, stderr)
            return None

        parsed_paths = _extract_apply_paths(stdout)
        if not parsed_paths:
            raise RuntimeError(
                "Apply CLI output parse failed.\r\nstdout:\r\n%s" % stdout
            )
        apply_front_csv, apply_rear_csv, session_log_path = parsed_paths
        if not File.Exists(apply_front_csv) or not File.Exists(apply_rear_csv):
            raise RuntimeError(
                "Apply CLI succeeded but expected applied CSVs are missing.\r\n"
                "front=%s\r\nrear=%s" % (apply_front_csv, apply_rear_csv)
            )

        front_rpm, front_map, front_applied_grid = _parse_ve_csv(apply_front_csv)
        rear_rpm, rear_map, rear_applied_grid = _parse_ve_csv(apply_rear_csv)
        if (
            not _axes_match(rpm_axis, front_rpm)
            or not _axes_match(map_axis, front_map)
            or not _axes_match(rpm_axis, rear_rpm)
            or not _axes_match(map_axis, rear_map)
        ):
            raise RuntimeError(
                "Applied CSV axes do not match preview grid. "
                "Check table shape compatibility before retrying."
            )
        if (
            len(front_applied_grid) != expected_rows
            or len(rear_applied_grid) != expected_rows
        ):
            raise RuntimeError("Applied CSV row count mismatch with preview grid.")
        if (
            front_applied_grid
            and len(front_applied_grid[0]) != expected_cols
            or rear_applied_grid
            and len(rear_applied_grid[0]) != expected_cols
        ):
            raise RuntimeError("Applied CSV column count mismatch with preview grid.")

        _apply_grid_to_table(front_table, front_applied_grid, front_index_base)
        _apply_grid_to_table(rear_table, rear_applied_grid, rear_index_base)
        context.PutTable(front_table)  # noqa: F821
        context.PutTable(rear_table)  # noqa: F821

        audit_path = _append_apply_audit_log(
            summary=summary,
            file_desc=_describe_file_handle(file_handle),
            front_table_name=front_table_name,
            rear_table_name=rear_table_name,
            session_log_path=session_log_path,
        )

        export_dir = _copy_export_outputs(
            summary,
            summary_path,
            extra_files=[apply_front_csv, apply_rear_csv],
        )
        MessageBox.Show(
            "Apply complete.\r\n\r\n"
            "Updated tables:\r\n- %s\r\n- %s\r\n\r\n"
            "session_log: %s\r\n"
            "audit_log: %s\r\n"
            "exports: %s\r\n\r\n"
            "Review and flash using Power Core's native File menu."
            % (
                front_table_name,
                rear_table_name,
                session_log_path,
                audit_path,
                export_dir,
            ),
            APP_TITLE_SHORT,
            MessageBoxButtons.OK,
            MessageBoxIcon.Information,
        )
        return True

    def _execute_preview_once(self):
        have_files = False
        temp_dir = None
        try:
            have_files = bool(context.EnsureFiles())  # noqa: F821
        except Exception:
            have_files = False

        if not have_files:
            MessageBox.Show(
                "No log file loaded in Data Center.\n\nLoad a log first, then re-run autotune preview.",
                APP_TITLE_SHORT,
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        try:
            file_handles = list(channels.GetFileHandles())  # noqa: F821
            if not file_handles:
                MessageBox.Show(
                    "No file handles available from TuneLab.",
                    APP_TITLE_SHORT,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning,
                )
                return
            file_handle = _select_best_file_handle(file_handles)
            if file_handle is None:
                MessageBox.Show(
                    "No usable file handle found in Data Center.",
                    APP_TITLE_SHORT,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning,
                )
                return

            run_id = _build_run_id(file_handle)
            temp_dir = _create_temp_dir()
            input_csv = Path.Combine(temp_dir, "tunelab_input.csv")
            _row_count, detected_mode = _export_loaded_log_csv(file_handle, input_csv)

            args = [
                "-m",
                "tools.autotune.tunelab_entrypoint",
                "preview",
                "--log-csv",
                input_csv,
                "--output-dir",
                temp_dir,
                "--run-id",
                run_id,
            ]
            if detected_mode == "single_front":
                args.extend(["--single-cylinder", "front"])
            elif detected_mode == "single_rear":
                args.extend(["--single-cylinder", "rear"])

            rc, stdout, stderr = run_cli(args, timeout_seconds=CLI_TIMEOUT_SECONDS)
            if rc != 0:
                _show_cli_error(rc, stdout, stderr)
                return

            summary_path = _extract_summary_path(stdout)
            if not summary_path or not File.Exists(summary_path):
                MessageBox.Show(
                    "CLI succeeded but summary path could not be parsed.\n\nstdout:\n%s"
                    % stdout,
                    APP_TITLE_SHORT + " (parse error)",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error,
                )
                return

            summary = _load_summary(summary_path)
            action = show_preview(summary, Path.GetDirectoryName(summary_path))
            if action == "apply":
                self._perform_apply(summary, summary_path, temp_dir, file_handle)
                return
            if action != "export":
                return

            export_dir = _copy_export_outputs(summary, summary_path)
            msg = (
                "Export complete.\n\nSaved files to:\n%s\n\nOpen folder now?"
                % export_dir
            )
            result = MessageBox.Show(
                msg,
                APP_TITLE_SHORT,
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information,
            )
            if result == DialogResult.Yes:
                try:
                    Process.Start("explorer.exe", export_dir)
                except Exception:
                    pass

        except Exception as exc:
            _show_error_dialog("Autotune preview error:\n%s" % str(exc))
        finally:
            if have_files:
                try:
                    context.FreeFiles()  # noqa: F821
                except Exception:
                    pass
            _safe_delete_dir(temp_dir)

    def Run(self):
        self._execute_preview_once()


autotune = DynoAIAutotune()
correction = autotune

_autotune_executed = False


def _execute_autotune_once():
    global _autotune_executed
    if _autotune_executed:
        return
    _autotune_executed = True
    autotune.Run()


def Run():
    _execute_autotune_once()


def PerformCorrection():
    _execute_autotune_once()


_execute_autotune_once()
