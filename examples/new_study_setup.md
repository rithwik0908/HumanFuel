# Adding a new Aria study (no engine edits)

The engine (`src/aria_rig_calibration/`) is generic. A new study is added purely by configuration.

## Steps
1. **Copy the template:** duplicate `studies/example_study/` to `studies/<your_study>/`.
2. **`study_config.yml`** — set `extends: ../../config/default_config.yml`, your `study_id`, and
   `input_roots` (where the participant folders live). Point `results_root` at a `_python` results
   directory.
3. **`target_config.yml`** — set target `id`s, human names, and **temporal order**. The legacy method
   assumes **exactly three fixed-duration blocks**; keep three targets to stay on the validated
   baseline (see the limitation below).
4. **`metadata_mapping.yml`** — map tracker columns to non-identifying fields, or set metadata to
   disabled if you have none. **Never** map name/email/phone/payment/scheduling fields.
5. **`participant_status_mapping.yml`** — map your tracker's administrative status strings to the
   canonical `administrative_no_data_*` statuses. Unmapped/blank → `..._status_unknown` (never guessed).

## Run
```powershell
$S = 'studies\<your_study>\study_config.yml'
python scripts\run_analysis.py --study-config $S --discover-all --refresh-metadata
```

## Limitation
The legacy scoring is hard-wired to **three 5 s blocks over a 15 s window**. A different target count
or timing is a **generalization beyond the validated baseline** and would need its own validation — it
is not covered by the 85/85 (original Python) or 125/125 (R PID1–37) parity evidence.
