"""Project Aria Rig-Calibration Analysis Toolkit.

Locates the rig-calibration interval in Project Aria eye-gaze recordings and characterises where each
configured calibration target appears in gaze space (yaw/pitch angular space, plus depth-scaled
CPF-relative gaze-ray points). It does not classify the full recording and makes no calibration-accuracy
claim without independent video/log validation.

Public entry points:
    from aria_rig_calibration.pipeline import run_pipeline
    from aria_rig_calibration.models import RunOptions
"""
__version__ = "1.1.1"
