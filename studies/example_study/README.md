# Example study profile

A minimal template showing how to reuse the toolkit for a **different** Project Aria study without
editing the engine.

It differs from So Pedestrian in: input root, target names (`target_left → target_centre →
target_right`), trial indices (0–2), and metadata disabled.

Run:
```powershell
aria-rig-calibration --study-config studies\example_study\study_config.local.yml --discover-all
```
See `../../examples/new_study_setup.md` for the step-by-step. The engine supports `N >= 2` targets, but
only the three-target configuration is validated; using a different target count should be interpreted
accordingly.
