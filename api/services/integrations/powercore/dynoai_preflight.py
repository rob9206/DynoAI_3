# api/services/integrations/powercore/dynoai_preflight.py
# DynoAI pre-flight safety check for dyno pulls (Feature 5 of roadmap).
#
# IronPython 2.7 script. Tabs. Py2 syntax. No os/re/subprocess.

import clr
from System.Windows.Forms import MessageBox, MessageBoxButtons, MessageBoxIcon
from tunelab import ConfigurableChannelProvider

clr.AddReference("System.Windows.Forms")

BRIDGE_VERSION = "v1.0.0"
APP_TITLE = "DynoAI Pre-flight " + BRIDGE_VERSION

# Safety thresholds
MIN_BATTERY = 12.5
MIN_AFR = 10.0
MAX_AFR = 20.0
MIN_ENGINE_TEMP = 160.0
MAX_ENGINE_TEMP = 260.0
MAX_INTAKE_TEMP = 150.0

# Channel aliases
BATTERY_ALIASES = ["B+", "VBatt", "Battery", "Battery Voltage"]
AFR_F_ALIASES = ["WBO2 F", "AFR 1", "Air/Fuel Ratio 1", "AFR Front", "AFR F"]
AFR_R_ALIASES = ["WBO2 R", "AFR 2", "Air/Fuel Ratio 2", "AFR Rear", "AFR R"]
ET_ALIASES = ["ET", "Engine Temp", "ECT", "Coolant Temp", "Engine Temperature"]
IAT_ALIASES = ["IAT", "Intake Air Temp", "Intake Temperature"]


def _try_channel(file_handle, aliases):
    """Return first channel matching any alias, or None."""
    for name in aliases:
        try:
            ch = channels.GetChannelByName(name, file_handle)
            if ch is not None:
                return ch
        except Exception:
            continue
    return None


def _latest_value(channel):
    """Return the latest sample Value from a channel, or None."""
    if channel is None:
        return None
    try:
        last = None
        for s in channel.GetAllSamples():
            last = s
        if last is None:
            return None
        return last.Value
    except Exception:
        return None


class CheckResult(object):
    def __init__(self, name, status, detail):
        self.name = name
        self.status = status
        self.detail = detail


def check_battery(fh):
    ch = _try_channel(fh, BATTERY_ALIASES)
    if ch is None:
        return CheckResult("Battery voltage", "SKIP", "channel not found")
    v = _latest_value(ch)
    if v is None:
        return CheckResult("Battery voltage", "SKIP", "no samples")
    if v < MIN_BATTERY:
        return CheckResult(
            "Battery voltage",
            "FAIL",
            "%.2fV (below %.1fV threshold)" % (v, MIN_BATTERY),
        )
    return CheckResult("Battery voltage", "PASS", "%.2fV" % v)


def check_afr(fh, aliases, label):
    ch = _try_channel(fh, aliases)
    if ch is None:
        return CheckResult("AFR %s" % label, "SKIP", "channel not found")
    v = _latest_value(ch)
    if v is None:
        return CheckResult("AFR %s" % label, "SKIP", "no samples")
    if v < MIN_AFR or v > MAX_AFR:
        return CheckResult(
            "AFR %s" % label,
            "FAIL",
            "%.2f (outside %.1f-%.1f range)" % (v, MIN_AFR, MAX_AFR),
        )
    return CheckResult("AFR %s" % label, "PASS", "%.2f" % v)


def check_engine_temp(fh):
    ch = _try_channel(fh, ET_ALIASES)
    if ch is None:
        return CheckResult("Engine temp", "SKIP", "channel not found")
    v = _latest_value(ch)
    if v is None:
        return CheckResult("Engine temp", "SKIP", "no samples")
    if v < MIN_ENGINE_TEMP:
        return CheckResult(
            "Engine temp",
            "FAIL",
            "%.0f F (cold, warm up above %.0f F first)" % (v, MIN_ENGINE_TEMP),
        )
    if v > MAX_ENGINE_TEMP:
        return CheckResult(
            "Engine temp",
            "FAIL",
            "%.0f F (overheating, cool down below %.0f F)" % (v, MAX_ENGINE_TEMP),
        )
    return CheckResult("Engine temp", "PASS", "%.0f F" % v)


def check_intake_temp(fh):
    ch = _try_channel(fh, IAT_ALIASES)
    if ch is None:
        return CheckResult("Intake temp", "SKIP", "channel not found")
    v = _latest_value(ch)
    if v is None:
        return CheckResult("Intake temp", "SKIP", "no samples")
    if v > MAX_INTAKE_TEMP:
        return CheckResult(
            "Intake temp",
            "WARN",
            "%.0f F (heat-soaked, accuracy impacted)" % v,
        )
    return CheckResult("Intake temp", "PASS", "%.0f F" % v)


def run_checks(fh):
    return [
        check_battery(fh),
        check_afr(fh, AFR_F_ALIASES, "Front"),
        check_afr(fh, AFR_R_ALIASES, "Rear"),
        check_engine_temp(fh),
        check_intake_temp(fh),
    ]


def format_results(results):
    lines = []
    has_fail = False
    has_warn = False

    for r in results:
        if r.status == "FAIL":
            prefix = "[FAIL]"
            has_fail = True
        elif r.status == "WARN":
            prefix = "[WARN]"
            has_warn = True
        elif r.status == "SKIP":
            prefix = "[SKIP]"
        else:
            prefix = "[OK]  "
        lines.append("%s %s: %s" % (prefix, r.name, r.detail))

    afr_results = [r for r in results if r.name.startswith("AFR")]
    afr_pass = [r for r in afr_results if r.status == "PASS"]
    afr_skip = [r for r in afr_results if r.status == "SKIP"]

    if afr_results and len(afr_skip) == len(afr_results):
        has_fail = True
        lines.append("[FAIL] AFR: no wideband channels available - cannot tune safely")
    elif len(afr_pass) >= 1 and len(afr_skip) >= 1:
        lines.append(
            "[SKIP] AFR: one bank unavailable; proceeding with available sensor"
        )

    if has_fail:
        verdict = "NOT READY - do not pull"
        icon = MessageBoxIcon.Error
    elif has_warn:
        verdict = "READY with warnings - proceed with caution"
        icon = MessageBoxIcon.Warning
    else:
        verdict = "READY FOR PULL"
        icon = MessageBoxIcon.Information

    body = verdict + "\n\n" + "\n".join(lines)
    return body, icon


class DynoAIPreflight(ConfigurableChannelProvider):
    """TuneLab script: pre-flight safety check before a dyno pull."""

    def Run(self):
        try:
            if not context.EnsureFiles():
                MessageBox.Show(
                    "No log file loaded in Data Center.\n\n"
                    "Load a log first, then re-run pre-flight.",
                    APP_TITLE,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning,
                )
                return

            try:
                file_handles = list(channels.GetFileHandles())
                if not file_handles:
                    MessageBox.Show(
                        "No file handles available.",
                        APP_TITLE,
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning,
                    )
                    return

                fh = file_handles[-1]
                results = run_checks(fh)
                body, icon = format_results(results)
                MessageBox.Show(body, APP_TITLE, MessageBoxButtons.OK, icon)
            finally:
                try:
                    context.FreeFiles()
                except Exception:
                    pass

        except Exception as exc:
            MessageBox.Show(
                "Pre-flight error:\n%s" % str(exc),
                APP_TITLE,
                MessageBoxButtons.OK,
                MessageBoxIcon.Error,
            )


# Registration for TuneLab variants
preflight = DynoAIPreflight()
correction = preflight

_executed = False


def _execute_once():
    global _executed
    if _executed:
        return
    _executed = True
    preflight.Run()


def Run():
    _execute_once()


def PerformCorrection():
    _execute_once()


_execute_once()
