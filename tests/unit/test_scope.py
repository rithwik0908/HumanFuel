"""Unit tests: central participant-scope resolution and exclusions."""
from aria_rig_calibration.discovery import resolve_participant_scope


def _scope(**kw):
    base = dict(requested_pids=[1, 2, 3], discovered=[3, 4, 5], excluded_pids=[],
                discovery_mode="requested_plus_discovered", discover_all=False)
    base.update(kw)
    return resolve_participant_scope(**base)


def test_requested_only():
    s = _scope(discovery_mode="requested_only")
    assert s["processing_pids"] == [1, 2, 3] and s["reporting_pids"] == [1, 2, 3]


def test_discovered_only():
    s = _scope(discovery_mode="discovered_only")
    assert s["processing_pids"] == [3, 4, 5]


def test_requested_plus_discovered():
    s = _scope(discovery_mode="requested_plus_discovered")
    assert s["processing_pids"] == [1, 2, 3, 4, 5]


def test_discover_all_forces_discovered_only():
    s = _scope(discovery_mode="requested_only", discover_all=True)
    assert s["effective_discovery_mode"] == "discovered_only" and s["processing_pids"] == [3, 4, 5]


def test_exclude_requested_pid():
    s = _scope(discovery_mode="requested_only", excluded_pids=[2])
    assert s["processing_pids"] == [1, 3]


def test_exclude_discovered_pid():
    s = _scope(discovery_mode="discovered_only", excluded_pids=[4])
    assert s["processing_pids"] == [3, 5]


def test_pid99_discovered_without_discover_all():
    # requested_plus_discovered includes a discovered PID99 even without --discover-all.
    s = resolve_participant_scope([1], [99], [], "requested_plus_discovered", False)
    assert 99 in s["processing_pids"]
    # requested_only excludes it.
    s2 = resolve_participant_scope([1], [99], [], "requested_only", False)
    assert 99 not in s2["processing_pids"]


def test_empty_requested_list():
    s = resolve_participant_scope([], [4, 5], [], "requested_plus_discovered", False)
    assert s["processing_pids"] == [4, 5]
    s2 = resolve_participant_scope([], [4, 5], [], "requested_only", False)
    assert s2["processing_pids"] == []


def test_processing_equals_reporting():
    for mode in ("requested_only", "discovered_only", "requested_plus_discovered"):
        s = _scope(discovery_mode=mode, excluded_pids=[3])
        assert s["processing_pids"] == s["reporting_pids"]      # same population always
