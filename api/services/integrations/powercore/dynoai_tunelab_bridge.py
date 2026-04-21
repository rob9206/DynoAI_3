# api/services/integrations/powercore/dynoai_tunelab_bridge.py
# DynoAI <-> Power Core TuneLab bridge
#
# IronPython 2.7 script. Uses tabs (matching shipped easylab.py / tunelab.py
# in the Power Core install directory) and Python 2 syntax.
#
# Phase 4: full end-to-end wiring + log auto-detection. Reads the most
# recently loaded file from `channels.GetFileHandles()`, finds the RPM channel
# by alias, and pre-fills the HP-Peak-RPM / TQ-Peak-RPM fields with the
# observed peak RPM. Also opportunistically checks for Power/Torque channels
# (usually absent from ECU logs). HP/TQ values remain manual entry.
#
# Installation:
#   Power Core -> Tools -> TuneLab -> Manage Scripts -> Add -> select this file

import clr
from System.Diagnostics import Process, ProcessStartInfo
from System.Drawing import Point, Size
from System.IO import File, Path
from System.Windows.Forms import (
    Button,
    CheckBox,
    ComboBox,
    ComboBoxStyle,
    DialogResult,
    Form,
    FormBorderStyle,
    FormStartPosition,
    Label,
    MessageBox,
    MessageBoxButtons,
    MessageBoxIcon,
    TextBox,
)
from tunelab import ConfigurableChannelProvider

clr.AddReference("System")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_REPO_ROOT = r"C:\Dev\DynoAI_3"
DEFAULT_PYTHON = r"C:\Dev\DynoAI_3\.venv\Scripts\python.exe"
BRIDGE_VERSION = "v1.0.3"
APP_TITLE = "DynoAI WinPEP Bridge " + BRIDGE_VERSION
APP_TITLE_SHORT = "DynoAI Bridge " + BRIDGE_VERSION
DEFAULT_FAMILY = "M8"
DEFAULT_DISPLACEMENT = 114.0
DEFAULT_RPM_POINTS = 400
FAMILIES = ["M8", "TwinCam", "Sportbike", "Generic"]

# Channel name aliases for auto-detection. TuneLab GetChannelByName returns
# None when a name isn't found; we walk the list and take the first hit.
RPM_CHANNEL_ALIASES = ["RPM", "Engine RPM", "Engine Speed"]
HP_CHANNEL_ALIASES = ["Power", "RWHP", "Engine Horsepower", "HP", "Horsepower"]
TQ_CHANNEL_ALIASES = ["Torque", "RWTQ", "Engine Torque", "TQ"]

# ---------------------------------------------------------------------------
# TuneLab channel auto-detection
# ---------------------------------------------------------------------------


def _try_channel(file_handle, aliases):
    """Return the first channel matching any alias, or None."""
    for name in aliases:
        try:
            ch = channels.GetChannelByName(name, file_handle)
            if ch is not None:
                return ch
        except Exception:
            continue
    return None


def auto_detect():
    """Pre-fill defaults from the most recently loaded file only.

    ECU logs generally don't carry HP/TQ channels - those come from the
    dyno - so we count on peak RPM from the RPM trace and opportunistically
    capture HP/TQ if a dyno run happens to be loaded.
    """
    result = {}
    try:
        file_handles = list(channels.GetFileHandles())
        if not file_handles:
            return result
        fh = file_handles[-1]

        rpm_ch = _try_channel(fh, RPM_CHANNEL_ALIASES)
        hp_ch = _try_channel(fh, HP_CHANNEL_ALIASES)
        tq_ch = _try_channel(fh, TQ_CHANNEL_ALIASES)

        if rpm_ch is None:
            return result

        peak_rpm = 0.0
        for s in rpm_ch.GetAllSamples():
            if s.Value > peak_rpm:
                peak_rpm = s.Value

        if peak_rpm > 0:
            result["peak_rpm"] = peak_rpm
            result["hp_peak_rpm_default"] = peak_rpm
            result["tq_peak_rpm_default"] = peak_rpm

        if hp_ch is not None:
            best_v = 0.0
            best_t = 0
            for s in hp_ch.GetAllSamples():
                if s.Value > best_v:
                    best_v = s.Value
                    best_t = s.TimeMillis
            if best_v > 0:
                result["max_hp"] = best_v
                result["hp_peak_rpm_default"] = rpm_ch.GetValueAtTime(best_t)

        if tq_ch is not None:
            best_v = 0.0
            best_t = 0
            for s in tq_ch.GetAllSamples():
                if s.Value > best_v:
                    best_v = s.Value
                    best_t = s.TimeMillis
            if best_v > 0:
                result["max_tq"] = best_v
                result["tq_peak_rpm_default"] = rpm_ch.GetValueAtTime(best_t)

    except Exception as exc:
        pass
    return result


# ---------------------------------------------------------------------------
# Utility: tolerant decode for process output text/bytes (IronPython 2.7)
# ---------------------------------------------------------------------------


def _decode(data):
    """Decode process output into a string, tolerating mixed encodings."""
    if data is None:
        return ""
    try:
        # IronPython 2.7
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
    """Prefer the repo venv's python.exe; fall back to PATH python."""
    if File.Exists(DEFAULT_PYTHON):
        return DEFAULT_PYTHON
    return "python"


# ---------------------------------------------------------------------------
# CLI wiring (.NET ProcessStartInfo - subprocess is unavailable in TuneLab)
# ---------------------------------------------------------------------------


def _quote_arg(arg):
    """Minimal Windows-safe argument quoting for ProcessStartInfo.Arguments."""
    s = str(arg)
    if s == "":
        return '""'
    if '"' in s:
        s = s.replace('"', '\\"')
    if (" " in s) or ("\t" in s):
        return '"' + s + '"'
    return s


def run_cli(values):
    """Invoke synthetic WinPEP8 CLI. Returns (rc, stdout_str, stderr_str)."""
    # NOTE: TuneLab IronPython does not ship Python's subprocess module.
    # Use native .NET process launch APIs instead.
    args = [
        "-m",
        "tools.synthetic.winpep8_cli",
        "peaks",
        "--run-id",
        values["run_id"],
        "--family",
        values["family"],
        "--displacement-ci",
        str(values["displacement_ci"]),
        "--max-hp",
        str(values["max_hp"]),
        "--hp-peak-rpm",
        str(values["hp_peak_rpm"]),
        "--max-tq",
        str(values["max_tq"]),
        "--tq-peak-rpm",
        str(values["tq_peak_rpm"]),
        "--rpm-points",
        str(values["rpm_points"]),
    ]
    if values.get("dry_run"):
        args.append("--dry-run")

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
    proc.WaitForExit()

    return proc.ExitCode, _decode(raw_out), _decode(raw_err)


def _extract_output_path(stdout):
    """Parse the 'output:' line emitted by winpep8_cli _handle_peaks."""
    if not stdout:
        return None
    for line in stdout.splitlines():
        trimmed = line.strip()
        if trimmed.lower().startswith("output:"):
            return trimmed.split(":", 1)[1].strip()
    return None


def show_result(rc, stdout, stderr):
    """Success or failure dialog with Open Folder shortcut on success."""
    if rc == 0:
        out_path = _extract_output_path(stdout)
        if out_path and File.Exists(out_path):
            msg = "Success.\n\nFile:\n%s\n\nOpen containing folder?" % out_path
            result = MessageBox.Show(
                msg,
                APP_TITLE_SHORT,
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information,
            )
            if result == DialogResult.Yes:
                try:
                    Process.Start("explorer.exe", Path.GetDirectoryName(out_path))
                except Exception as exc:
                    MessageBox.Show(
                        "Could not open folder:\n%s" % str(exc),
                        APP_TITLE_SHORT,
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning,
                    )
        else:
            # CLI succeeded but we couldn't find an output: line - show raw.
            MessageBox.Show(
                stdout if stdout else "CLI reported success.",
                APP_TITLE_SHORT + " (success)",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information,
            )
    else:
        body = "CLI failed (rc=%d)" % rc
        if stderr:
            body += "\n\nstderr:\n" + stderr
        if stdout:
            body += "\n\nstdout:\n" + stdout
        MessageBox.Show(
            body,
            APP_TITLE_SHORT + " (error)",
            MessageBoxButtons.OK,
            MessageBoxIcon.Error,
        )


# ---------------------------------------------------------------------------
# WinForms input dialog
# ---------------------------------------------------------------------------


class BridgeDialog(Form):
    """WinForms input dialog for bridge parameters."""

    def __init__(self, defaults):
        self.values = None
        self._build_form(defaults or {})

    def _build_form(self, defaults):
        self.Text = APP_TITLE
        self.Size = Size(430, 540)
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimizeBox = False
        self.MaximizeBox = False

        y = 15
        label_w = 150
        input_x = 170
        input_w = 230
        row_h = 32

        # Run ID
        self._add_label("Run ID (relative):", 15, y, label_w)
        self.tb_run_id = self._add_textbox(
            input_x, y, input_w, defaults.get("run_id", "")
        )
        y += row_h

        # Engine Family
        self._add_label("Engine Family:", 15, y, label_w)
        self.cb_family = ComboBox()
        self.cb_family.Location = Point(input_x, y)
        self.cb_family.Size = Size(input_w, 23)
        self.cb_family.DropDownStyle = ComboBoxStyle.DropDownList
        for f in FAMILIES:
            self.cb_family.Items.Add(f)
        self.cb_family.SelectedItem = defaults.get("family", DEFAULT_FAMILY)
        self.Controls.Add(self.cb_family)
        y += row_h

        # Displacement
        self._add_label("Displacement (ci):", 15, y, label_w)
        self.tb_displacement = self._add_textbox(
            input_x, y, input_w, defaults.get("displacement_ci", DEFAULT_DISPLACEMENT)
        )
        y += row_h

        # Peak HP
        self._add_label("Peak HP:", 15, y, label_w)
        self.tb_max_hp = self._add_textbox(
            input_x, y, input_w, defaults.get("max_hp", "")
        )
        y += row_h

        # HP Peak RPM
        self._add_label("HP Peak RPM:", 15, y, label_w)
        self.tb_hp_peak_rpm = self._add_textbox(
            input_x, y, input_w, defaults.get("hp_peak_rpm_default", "")
        )
        y += row_h

        # Peak TQ
        self._add_label("Peak TQ (lb-ft):", 15, y, label_w)
        self.tb_max_tq = self._add_textbox(
            input_x, y, input_w, defaults.get("max_tq", "")
        )
        y += row_h

        # TQ Peak RPM
        self._add_label("TQ Peak RPM:", 15, y, label_w)
        self.tb_tq_peak_rpm = self._add_textbox(
            input_x, y, input_w, defaults.get("tq_peak_rpm_default", "")
        )
        y += row_h

        # RPM Points
        self._add_label("RPM Points:", 15, y, label_w)
        self.tb_rpm_points = self._add_textbox(
            input_x, y, input_w, defaults.get("rpm_points", DEFAULT_RPM_POINTS)
        )
        y += row_h

        # Dry run checkbox
        self.cb_dry_run = CheckBox()
        self.cb_dry_run.Text = "Dry run (preview only, no file written)"
        self.cb_dry_run.Location = Point(15, y)
        self.cb_dry_run.Size = Size(385, 24)
        self.cb_dry_run.Checked = bool(defaults.get("dry_run", False))
        self.Controls.Add(self.cb_dry_run)
        y += row_h + 8

        # Buttons
        btn_generate = Button()
        btn_generate.Text = "Generate"
        btn_generate.Location = Point(200, y)
        btn_generate.Size = Size(95, 32)
        btn_generate.Click += self._on_generate
        self.Controls.Add(btn_generate)

        btn_cancel = Button()
        btn_cancel.Text = "Cancel"
        btn_cancel.Location = Point(305, y)
        btn_cancel.Size = Size(95, 32)
        btn_cancel.Click += self._on_cancel
        self.Controls.Add(btn_cancel)

        # Hook Enter/Escape keys to buttons
        self.AcceptButton = btn_generate
        self.CancelButton = btn_cancel

    def _add_label(self, text, x, y, w):
        lbl = Label()
        lbl.Text = text
        lbl.Location = Point(x, y + 4)
        lbl.Size = Size(w, 20)
        self.Controls.Add(lbl)
        return lbl

    def _add_textbox(self, x, y, w, value):
        tb = TextBox()
        tb.Location = Point(x, y)
        tb.Size = Size(w, 23)
        if value is None or value == "":
            tb.Text = ""
        else:
            tb.Text = str(value)
        self.Controls.Add(tb)
        return tb

    def _on_generate(self, sender, args):
        parsed = self._validate_and_parse()
        if parsed is not None:
            self.values = parsed
            self.DialogResult = DialogResult.OK
            self.Close()

    def _on_cancel(self, sender, args):
        self.values = None
        self.DialogResult = DialogResult.Cancel
        self.Close()

    def _parse_positive_float(self, text, field_name):
        try:
            v = float(text)
        except ValueError:
            self._err("%s must be a number." % field_name)
            return None
        if v <= 0:
            self._err("%s must be positive." % field_name)
            return None
        return v

    def _sanitize_run_id(self, raw):
        """Convert pasted paths to a safe relative run_id when possible."""
        run_id = raw.strip().replace("\\", "/")
        if not run_id:
            return None

        # If the user pasted a CSV path, trim the filename.
        if run_id.lower().endswith(".csv"):
            parts = run_id.rsplit("/", 1)
            run_id = parts[0] if len(parts) > 1 else ""

        # If the user pasted an absolute path containing /runs/, keep the suffix.
        lower = run_id.lower()
        marker = "/runs/"
        idx = lower.find(marker)
        if idx >= 0:
            run_id = run_id[idx + len(marker):]

        run_id = run_id.strip("/")
        if not run_id:
            return None

        return run_id

    def _validate_and_parse(self):
        # Run ID: must be project-relative, no ".." segments.
        # We also accept pasted absolute paths and strip down to the /runs/ suffix.
        raw_run_id = self.tb_run_id.Text.strip()
        if not raw_run_id:
            self._err("Run ID is required.")
            return None

        normalized = self._sanitize_run_id(raw_run_id)
        if not normalized:
            self._err("Run ID is required.")
            return None

        if ".." in normalized.split("/"):
            self._err("Run ID cannot contain '..' path segments.")
            return None
        if (len(normalized) > 1 and normalized[1] == ":") or normalized.startswith("/"):
            self._err(
                "Run ID must be relative (e.g. test/powercore_smoke), not a full path."
            )
            return None

        disp = self._parse_positive_float(self.tb_displacement.Text, "Displacement")
        if disp is None:
            return None
        max_hp = self._parse_positive_float(self.tb_max_hp.Text, "Peak HP")
        if max_hp is None:
            return None
        hp_rpm = self._parse_positive_float(self.tb_hp_peak_rpm.Text, "HP Peak RPM")
        if hp_rpm is None:
            return None
        max_tq = self._parse_positive_float(self.tb_max_tq.Text, "Peak TQ")
        if max_tq is None:
            return None
        tq_rpm = self._parse_positive_float(self.tb_tq_peak_rpm.Text, "TQ Peak RPM")
        if tq_rpm is None:
            return None

        try:
            rpm_points = int(self.tb_rpm_points.Text)
        except ValueError:
            self._err("RPM Points must be an integer.")
            return None
        if rpm_points < 50 or rpm_points > 2000:
            self._err("RPM Points must be between 50 and 2000.")
            return None

        family = (
            str(self.cb_family.SelectedItem)
            if self.cb_family.SelectedItem
            else DEFAULT_FAMILY
        )

        return {
            "run_id": normalized,
            "family": family,
            "displacement_ci": disp,
            "max_hp": max_hp,
            "hp_peak_rpm": hp_rpm,
            "max_tq": max_tq,
            "tq_peak_rpm": tq_rpm,
            "rpm_points": rpm_points,
            "dry_run": self.cb_dry_run.Checked,
        }

    def _err(self, msg):
        MessageBox.Show(
            msg, "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning
        )


def show_dialog(defaults):
    """Show the input form. Returns values dict on Generate, None on Cancel."""
    form = BridgeDialog(defaults or {})
    result = form.ShowDialog()
    if result == DialogResult.OK:
        return form.values
    return None


# ---------------------------------------------------------------------------
# TuneLab entry point
# ---------------------------------------------------------------------------


class DynoAIWinPEPBridge(ConfigurableChannelProvider):
    """TuneLab bridge: synthesizes a WinPEP8 CSV via the DynoAI CLI."""

    def _do_bridge(self, have_files):
        defaults = auto_detect() if have_files else {}
        values = show_dialog(defaults)
        if values is None:
            return  # user cancelled
        rc, stdout, stderr = run_cli(values)
        show_result(rc, stdout, stderr)

    def Run(self):
        try:
            have_files = False
            try:
                have_files = bool(context.EnsureFiles())
            except Exception:
                # If TuneLab can't load files, fall back to manual entry.
                have_files = False
            try:
                self._do_bridge(have_files)
            finally:
                if have_files:
                    try:
                        context.FreeFiles()
                    except Exception:
                        pass
        except Exception as exc:
            MessageBox.Show(
                "Bridge error:\n%s" % str(exc),
                APP_TITLE_SHORT,
                MessageBoxButtons.OK,
                MessageBoxIcon.Error,
            )


# Explicit registration for TuneLab variants that expect a module-level object.
# The generated scripts in this repo use the `correction = <Class>()` pattern.
bridge = DynoAIWinPEPBridge()
correction = bridge

# Compatibility entrypoints for TuneLab variants that invoke a module-level
# callable rather than a provider object's Run() method.
_bridge_executed = False


def _execute_bridge_once():
    """Run bridge once per script evaluation regardless of invocation style."""
    global _bridge_executed
    if _bridge_executed:
        return
    _bridge_executed = True
    bridge.Run()


def Run():
    _execute_bridge_once()


def PerformCorrection():
    _execute_bridge_once()


# Some TuneLab builds evaluate script top-level like built-in correction files
# and do not invoke class Run() automatically. Execute once at module scope to
# cover that behavior.
_execute_bridge_once()
