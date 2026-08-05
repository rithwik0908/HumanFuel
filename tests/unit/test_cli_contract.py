"""Unit tests: the CLI parser matches the documented interface (no removed flags remain)."""
from aria_rig_calibration.cli import build_parser


def _option_strings():
    strings = set()
    for action in build_parser()._actions:
        strings.update(action.option_strings)
    return strings


def test_documented_flags_exist():
    opts = _option_strings()
    for flag in ["--study-config", "--pids", "--trials", "--discover-all", "--metadata-mode",
                 "--metadata-file", "--retain-metadata-snapshot", "--data-root", "--output-root",
                 "--validate-only", "--run-id", "--overwrite"]:
        assert flag in opts, f"missing documented flag {flag}"


def test_removed_flags_absent():
    opts = _option_strings()
    for flag in ["--mode", "--offline-metadata", "--refresh-metadata"]:
        assert flag not in opts, f"removed flag still present: {flag}"


def test_metadata_mode_choices():
    for action in build_parser()._actions:
        if "--metadata-mode" in action.option_strings:
            assert set(action.choices) == {"auto", "online", "local", "none"}
            return
    raise AssertionError("--metadata-mode not found")
