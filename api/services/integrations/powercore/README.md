# DynoAI ↔ Power Core Bridge

This folder contains a TuneLab/IronPython script that lets you trigger the
DynoAI synthetic WinPEP generator directly from inside **Dynojet Power Core**.

## Files

| File | Purpose |
| --- | --- |
| `dynoai_tunelab_bridge.py` | WinForms-based TuneLab script. Prompts for run metadata, then shells out to `python -m synthetic.winpep8_cli` inside your DynoAI repo. |

## Installation Steps

1. **Edit Script Defaults (optional)**  
   Update `DEFAULT_REPO_ROOT` / `DEFAULT_PYTHON` near the top of
   `dynoai_tunelab_bridge.py` if your DynoAI checkout or virtualenv lives
   elsewhere.

2. **Copy into Power Core**  
   Place the script inside the Power Core install directory, e.g.:
   ```
   C:\Program Files (x86)\Dynojet Power Core\DynoAI_TuneLab.py
   ```

3. **Register with TuneLab**  
   Launch Power Core → Tools → TuneLab → Manage Scripts → *Add* → pick the file.
   It will now appear in the TuneLab Scripts list.

4. **Configure DynoAI environment**  
   Ensure your DynoAI repo (`DEFAULT_REPO_ROOT`) is accessible and that running
   the CLI manually works:
   ```powershell
   cd C:\Dev\DynoAI_3
   python -m synthetic.winpep8_cli --help
   ```

## Usage

1. In Power Core, open the logs/tables you want.
2. Run the “DynoAI WinPEP Synth” TuneLab script.
3. Fill in the dialog (run id, family, displacement, peak HP/TQ, etc.).
4. Click **Generate Synthetic Run**.  
   The script calls DynoAI, writes `runs/<run_id>/run.csv`, and displays the CLI
   output. Import the CSV into WinPEP / Control Center as usual.

## Notes

- The script does not yet auto-read peaks from the currently loaded log. You can
  extend it by accessing `tunelab.context`/`channels` if you want tighter
  coupling.
- Any errors from the DynoAI CLI will be displayed in a WinForms message box.
- Feel free to customize the dialog (extra fields, presets, etc.) before copying
  it into Power Core.

