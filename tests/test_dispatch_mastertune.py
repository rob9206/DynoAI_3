"""Regression tests for MasterTune dispatcher window filtering."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_dispatch_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "dispatch_mastertune.py"
    spec = spec_from_file_location("dispatch_mastertune_under_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dispatch_mastertune = _load_dispatch_module()


class TestShouldIgnoreWindowTitle:
    """Ensure terminal windows are never mistaken for MasterTune."""

    @staticmethod
    def test_ignores_command_prompt_titles():
        title = 'Command Prompt - python dispatch_mastertune.py --window-title-re "MasterTune2-HD.*"'
        assert dispatch_mastertune._should_ignore_window_title(title) is True

    @staticmethod
    def test_ignores_powershell_titles():
        title = "Windows PowerShell - python scripts/dispatch_mastertune.py --resume"
        assert dispatch_mastertune._should_ignore_window_title(title) is True

    @staticmethod
    def test_keeps_real_mastertune_titles():
        title = "MasterTune2-HD - Advanced Mode Active"
        assert dispatch_mastertune._should_ignore_window_title(title) is False
