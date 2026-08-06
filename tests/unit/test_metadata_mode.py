"""Unit tests: metadata-mode-dependent configuration validation and clean failures."""
import pytest

from aria_rig_calibration.config import load_study_config, validate_config
from aria_rig_calibration.logging_utils import CollectingLogger
from aria_rig_calibration.metadata import MetadataError, resolve_metadata
from tests.conftest import EXAMPLE_CONFIG


@pytest.fixture
def base_cfg(monkeypatch, tmp_path):
    """Example config with data/output roots resolved so only metadata problems remain."""
    monkeypatch.setenv("ARIA_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ARIA_OUTPUT_ROOT", str(tmp_path))
    return load_study_config(str(EXAMPLE_CONFIG))


def _meta_problems(cfg, mode):
    return [p for p in validate_config(cfg, mode)[1] if "metadata" in p.lower()]


def test_none_requires_nothing(base_cfg):
    base_cfg["metadata"] = {"enabled": False, "online": None, "local": None}
    assert _meta_problems(base_cfg, "none") == []


def test_online_with_document_id_ok(base_cfg):
    base_cfg["metadata"] = {"enabled": True, "online": {"document_id": "DOC"}, "local": None}
    assert _meta_problems(base_cfg, "online") == []


def test_local_with_existing_workbook_ok(base_cfg, tmp_path):
    wb = tmp_path / "t.xlsx"
    wb.write_bytes(b"PK\x03\x04")
    base_cfg["metadata"] = {"enabled": True, "online": None, "local": str(wb)}
    assert _meta_problems(base_cfg, "local") == []


def test_auto_with_online_ok(base_cfg):
    base_cfg["metadata"] = {"enabled": True, "online": {"document_id": "DOC"}, "local": "${ARIA_METADATA_FILE}"}
    assert _meta_problems(base_cfg, "auto") == []


def test_auto_fallback_to_local_ok(base_cfg, tmp_path):
    wb = tmp_path / "t.xlsx"
    wb.write_bytes(b"PK")
    base_cfg["metadata"] = {"enabled": True, "online": {"document_id": "${ARIA_TRACKER_DOCUMENT_ID}"}, "local": str(wb)}
    assert _meta_problems(base_cfg, "auto") == []


def test_auto_with_neither_ok(base_cfg):
    base_cfg["metadata"] = {"enabled": True, "online": {"document_id": "${ARIA_TRACKER_DOCUMENT_ID}"}, "local": "${ARIA_METADATA_FILE}"}
    assert _meta_problems(base_cfg, "auto") == []      # auto never fails on unset vars


def test_online_without_document_id_fails(base_cfg):
    base_cfg["metadata"] = {"enabled": True, "online": {"document_id": "${ARIA_TRACKER_DOCUMENT_ID}"}, "local": None}
    probs = _meta_problems(base_cfg, "online")
    assert probs and "online" in probs[0]


def test_local_with_missing_workbook_fails(base_cfg, tmp_path):
    base_cfg["metadata"] = {"enabled": True, "online": None, "local": str(tmp_path / "nope.xlsx")}
    probs = _meta_problems(base_cfg, "local")
    assert probs and "not found" in probs[0]


def test_resolve_online_without_docid_raises(base_cfg, tmp_path):
    base_cfg["metadata"] = {"enabled": True, "online": {"document_id": "${ARIA_TRACKER_DOCUMENT_ID}"}, "local": None}
    with pytest.raises(MetadataError):
        resolve_metadata(base_cfg, tmp_path, CollectingLogger(), mode="online")


def test_resolve_local_missing_raises(base_cfg, tmp_path):
    base_cfg["metadata"] = {"enabled": True, "online": None, "local": str(tmp_path / "nope.xlsx")}
    with pytest.raises(MetadataError):
        resolve_metadata(base_cfg, tmp_path, CollectingLogger(), mode="local")
