# Repository review (Phase 1)

## Summary
The toolkit is scientifically sound and its So Pedestrian outputs are validated, but the repository
was shaped for one developer's machine and foregrounds the R→Python migration history. The
supervisor-release cleanup makes it portable, privacy-safe, installable, and neutral in framing while
preserving the validated calibration method exactly.

## Strengths (preserve)
- Deterministic, well-defined sliding-window method with an auditable all-windows table.
- Two-layer config design (generic engine + study profiles).
- Administrative no-data accounting that never guesses status.
- Existing pytest coverage of the scientific crux (score, tie-break, blocks, timestamp inference).

## Weaknesses addressed by this cleanup
1. **Portability** — absolute `E:\rithwikS2026` paths in configs, tests, and the run script; the
   installed CLI located `scripts/run_analysis.py` via `runpy`. → env-var expansion + CLI overrides +
   orchestration moved into `aria_rig_calibration.pipeline`.
2. **Privacy** — full tracker workbook loaded and retained; unverified "never read" claims. →
   retain-only sanitised fields, delete the workbook snapshot unless explicitly requested, enforce
   `forbidden_tokens`, expanded `.gitignore`, `docs/privacy.md`.
3. **Accuracy** — depth mis-described as QC-only; unverified integrity/Excel claims. → corrected depth
   docs, real SHA-256 source-integrity checks, structural + privacy Excel validation.
4. **Generality** — fixed three-target indexing in "generic" modules; a non-functional two-target
   example. → loop/`itertools.combinations` generalisation to N≥2 with byte-identical three-target
   output; example study fixed.
5. **Maintainability** — one dense semicolon-heavy `main()`. → split into small typed stages in
   `pipeline.py`; docstrings and type hints across modules.
6. **Config hygiene** — several declared-but-unused keys. → removed or implemented; added validation.
7. **Framing** — README led with R/parity numbers. → supervisor-facing README; history moved to
   `docs/internal/validation_history.md`; comparison scripts moved to `tools/internal_validation/`.
8. **CI / tests** — no CI; a test needed the private dataset. → portable default suite + opt-in
   `local_parity`; GitHub Actions matrix.

## Non-negotiable invariant
The So Pedestrian selected windows, scores, target centres, confidence, review flags, and participant
statuses must not change. Verified after refactor against the reference run (see
`supervisor_release_validation.md`).
