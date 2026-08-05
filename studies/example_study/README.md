# Example study profile

A minimal template showing how to reuse the toolkit for a **different** Project Aria study without
editing any code in `R/`.

It differs from So Pedestrian in: input root, target names/order (`screen_left → screen_right`),
target count (2), trial indices (0–2), and metadata disabled.

Run:
```
Rscript scripts\run_analysis.R --study-config studies\example_study\study_config.yml --discover-all
```
See `examples/new_study_setup.md` for the step-by-step. Note: the validated legacy baseline assumes
exactly **three** fixed-duration blocks; a different `expected_count` is a generalization beyond that
baseline and should be interpreted accordingly.
