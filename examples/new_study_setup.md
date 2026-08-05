# Adding a new Aria study (no engine edits)

The engine (`src/aria_rig_calibration/`) is generic. A new study is added purely by configuration.

## Steps
1. **Copy the template:** duplicate `studies/example_study/` to `studies/<your_study>/`.
2. **`study_config.yml`** — set `extends: ../../config/default_config.yml`, your `study_id`, and
   `input.roots` (use `${ARIA_DATA_ROOT}` or a local path). Point `outputs.root` at `${ARIA_OUTPUT_ROOT}`.
   Copy to `study_config.local.yml` (git-ignored) for your machine.
3. **`target_config.yml`** — set target `id`s, `display_name`s, `color`s, and **temporal order**.
4. **`metadata_mapping.yml`** — map tracker columns to the de-identified fields, or disable metadata
   (`metadata.enabled: false` / `--metadata-mode none`). **Never** map name/email/phone/payment/
   scheduling columns; the `forbidden_tokens` guard will refuse to export them.
5. **`participant_status_mapping.yml`** — map your tracker's status strings to the canonical
   `administrative_no_data_*` statuses. Unmapped/blank → `..._status_unknown` (never guessed).

## Run
```powershell
$S = "studies\<your_study>\study_config.local.yml"
aria-rig-calibration --study-config $S --discover-all
```

## Target count
The engine is written generically for **`N ≥ 2`** equal-duration targets (block metrics loop over the
targets and pairwise separations use every target pair). However, only the **three-target**
configuration is **validated** against the reference outputs. Using two or four+ targets is supported
by the code but is a **generalisation beyond the validated baseline** and should be validated for your
study before relying on it. The three-target So Pedestrian output (including the `block_1/2/3_samples`
columns) is unchanged by the generalisation.
