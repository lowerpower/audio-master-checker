# Changelog

All notable project changes will be tracked here going forward.

## 2026-06-17

### Added

- Added FastAPI web UI under `audio_master_checker/web/`.
- Added upload flows for analyze, safer delivery fix, and original-vs-fixed compare.
- Added HTML report rendering from generated Markdown.
- Added download links for Markdown, JSON, and fixed WAV outputs.
- Added Dockerfile, `docker-compose.yml`, and `.dockerignore` for containerized web UI runs with ffmpeg/ffprobe and libsndfile.
- Added web route tests with analyzer/fix behavior mocked.

### Changed

- Added web dependencies to `requirements.txt` and `pyproject.toml`.
- Updated README with local web and Docker run instructions.

### Verified

- Ran `.venv/bin/python -m pytest`: 47 tests passed.

## 2026-06-14

### Added

- Added `--report-name` to `audio-master-checker analyze`.
- Added `--report-name` to `audio-master-checker fix`.
- Added `--compare` to `audio-master-checker fix` to write an additional original-vs-fixed comparison report.
- Added `audio-master-checker compare original.wav fixed.wav` for direct two-file comparison reports.
- Added Delivery Comparison Summary to two-file Markdown reports, including original/fixed metric deltas, codec safety change, and a recommendation.
- Added shared report path naming helper so default reports remain `report.json` and `report.md`, while named reports write `<name>.json` and `<name>.md`.
- Added tests for default report names, named report output, suffix handling, path-like name rejection, analyze integration, fix integration, fix comparison reports, and delivery comparison recommendations, and direct compare command output.

### Changed

- Updated `README.md` with named report examples for both analyze and fix workflows.

## 2026-06-13

### Added

- Added `audio-master-checker` CLI with subcommands:
  - `audio-master-checker analyze ...`
  - `audio-master-checker fix ...`
- Added `fix` command to create safer delivery WAV files by applying a negative gain trim with ffmpeg.
- Added default fixed-file naming, for example:
  - `song [-1.5dB delivery].wav`
- Added fix command options:
  - `--trim`
  - `--output`
  - `--bit-depth`
  - `--out`
  - `--timeout`
  - `--no-codec-tests`
- Added output bit-depth support:
  - `16` -> `pcm_s16le`
  - `24` -> `pcm_s24le`
  - `32f` -> `pcm_f32le`
- Added automatic post-fix analysis and report writing after creating a fixed WAV.
- Added short fix summary output including created path, applied gain, original true peak, estimated true peak, measured true peak, measured LUFS, codec safety, and report path.
- Added package CLI entry point in `pyproject.toml` for `pip install -e .`.
- Added local executable launcher: `./audio-master-checker`.
- Added tests for fix filename generation, bit-depth codec selection, ffmpeg command construction, positive trim rejection, and fix command analysis flow.

### Changed

- Updated `scripts/analyze_audio.py` to delegate to the new `analyze` subcommand while preserving the old script workflow.
- Updated `README.md` with `analyze` and `fix` examples plus editable-install setup.

### Verified

- Ran unit tests: `32 passed`.
- Smoke-tested analyze command on `tmp/sample.wav`.
- Smoke-tested fix command on `tmp/sample.wav` with `--trim -1.5` and `--no-codec-tests`.
- Validated generated fix report JSON with `python3 -m json.tool`.

## 2026-06-12

### Added

- Added near-ceiling source sample counts:
  - `samples_above_minus_0_1_dbfs`
  - `samples_above_minus_0_5_dbfs`
  - `samples_above_minus_1_0_dbfs`
- Added codec safety PASS/FAIL reporting.
- Added recommended trim estimates:
  - `recommended_trim_db`
  - `safer_trim_db`
  - `estimated_lufs_after_safer_trim`
  - `estimated_true_peak_after_safer_trim`
  - `estimated_sample_peak_after_safer_trim`
- Added Recommended Action section to Markdown reports.
- Added summary block below each file heading:
  - Status
  - Codec Safety
  - Recommended safer trim, when applicable
- Added tests for report formatting, trim estimates, codec safety, and near-ceiling counts.

### Changed

- Improved Markdown report terminal rendering.
- Shortened Codec Stress Test headers:
  - `Decoded sample peak`
  - `Decoded true peak`
  - `Over samples`
- Positive peak values now render with leading plus signs, for example `+0.26 dBFS` and `+1.17 dBTP`.
- Crest factor now renders without a leading plus sign.
- Trim recommendations now use reduction wording instead of positive gain wording.
- Recommended Action now says:
  - `In Audacity or a DAW, apply Amplify/Gain of **-1.5 dB** to create the safer delivery version.`
- Markdown sample counts now use thousands separators in tables and verdict bullets.
- Codec stress table headers were shortened for `glow` and normal terminal readability.

### Verified

- Ran unit tests after report formatting changes.
- Regenerated the Konocti Markdown report and verified summary, codec table, verdict bullets, and Recommended Action rendering.

## 2026-06-11

### Added

- Implemented Milestone 1 CLI audio analyzer.
- Added Python package `audio_master_checker`.
- Added ffmpeg/ffprobe wrappers using subprocess list arguments with `shell=False`.
- Added ffprobe metadata extraction.
- Added loudnorm measurement parsing for integrated LUFS, true peak dBTP, and LRA.
- Added Python sample metrics using `soundfile` and `numpy`:
  - sample peak linear
  - sample peak dBFS
  - RMS linear
  - RMS dBFS
  - crest factor dB
  - samples over 0 dBFS
- Added codec stress tests:
  - MP3 320k
  - AAC 256k
  - Ogg Vorbis q8
- Added verdict rules for loudness, true peak, source clipping, and codec clipping.
- Added JSON and Markdown report generation.
- Added multi-file comparison table.
- Added CLI script: `scripts/analyze_audio.py`.
- Added unit tests for metrics, verdicts, reports, and ffmpeg wrapper behavior.
- Added `requirements.txt`, `pytest.ini`, and initial `README.md`.

### Verified

- Ran initial unit test suite successfully.
- Generated a sample WAV with ffmpeg.
- Ran the analyzer CLI against the sample WAV and generated JSON/Markdown reports.
