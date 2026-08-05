#!/usr/bin/env python
"""Thin wrapper so ``python scripts/run_analysis.py ...`` behaves like the installed
``aria-rig-calibration`` command. All logic lives in the installed package."""
from aria_rig_calibration.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
