# Audio Master Checker

Milestone 1 is a Python CLI for checking mastered audio files. It writes one combined JSON report and one Markdown report for each run. It can also create a safer delivery WAV by applying a negative gain trim and then analyzing the result.

Web UI, upload handling, Caddy, systemd, and HTML output are intentionally deferred.

## Requirements

- Python 3.11+
- `ffmpeg` with `ffprobe` available on `PATH`

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Analyze

```bash
audio-master-checker analyze song.wav
```

Equivalent legacy script:

```bash
python scripts/analyze_audio.py song.wav --out ./reports
```

Multiple files:

```bash
audio-master-checker analyze "test1.wav" "test2.wav" --out ./reports
```

For quicker development checks without codec round-trips:

```bash
audio-master-checker analyze song.wav --out ./reports --no-codec-tests
```

By default, reports are written as:

- `reports/report.json`
- `reports/report.md`

Use `--report-name` to write named report files without changing the output directory:

```bash
audio-master-checker analyze song.wav --out ./reports --report-name song-check
```

This writes:

- `reports/song-check.json`
- `reports/song-check.md`

## Create A Safer Delivery WAV

Apply a negative gain trim without changing the mastering other than lowering level:

```bash
audio-master-checker fix song.wav --trim -1.5
```

This creates a default output name like:

```text
song [-1.5dB delivery].wav
```

Then analyze the fixed delivery file:

```bash
audio-master-checker analyze "song [-1.5dB delivery].wav"
```

Optional fix command settings:

```bash
audio-master-checker fix song.wav --trim -1.5 --output safer.wav --bit-depth 24
```

Name the generated fix report:

```bash
audio-master-checker fix song.wav --trim -1.5 --report-name song-delivery
```

This writes:

- `reports/song-delivery.json`
- `reports/song-delivery.md`

Also write an original-vs-fixed comparison report:

```bash
audio-master-checker fix song.wav --trim -1.5 --report-name song-delivery --compare
```

This writes the fixed-file report plus:

- `reports/song-delivery-compare.json`
- `reports/song-delivery-compare.md`

When the comparison report contains exactly two files, Markdown starts with a Delivery Comparison Summary showing original vs fixed LUFS, true peak, sample peak, codec safety change, and a recommendation.

Without `--report-name`, `--compare` writes:

- `reports/comparison.json`
- `reports/comparison.md`

Supported output bit depths:

- `16` -> 16-bit PCM WAV
- `24` -> 24-bit PCM WAV, the default
- `32f` -> 32-bit float WAV

The fix command preserves sample rate. It does not resample.

## Compare Two Existing Files

Compare any original and fixed delivery WAV directly:

```bash
audio-master-checker compare original.wav "original [-1.5dB delivery].wav" --out ./reports --report-name original-vs-fixed
```

This writes a two-file report with the Delivery Comparison Summary at the top.

## Web UI

Run the FastAPI web UI locally:

```bash
. .venv/bin/activate
uvicorn audio_master_checker.web.app:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

The web UI supports:

- Upload one or more files for analysis.
- Upload one file to create a safer delivery WAV.
- Upload original and fixed files for comparison.
- Download generated Markdown, JSON, and fixed WAV outputs.

Web runs are stored under `web-runs/<job_id>/`.

## Docker

Build and run the web UI with ffmpeg, ffprobe, and libsndfile inside the container:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

The compose file mounts `./web-runs` so generated files persist on the host.

## Report Contents

Each file report includes:

- ffprobe format and stream metadata
- integrated LUFS, true peak dBTP, and loudness range
- sample peak, RMS, crest factor, and source samples over 0 dBFS
- near-ceiling source sample counts:
  - `samples_above_minus_0_1_dbfs`
  - `samples_above_minus_0_5_dbfs`
  - `samples_above_minus_1_0_dbfs`
- MP3 320k, AAC 256k, and Ogg q8 codec stress test results
- codec safety PASS/FAIL
- verdict warnings and positives
- recommended trim estimates when true peak is above `-1.0 dBTP` or codec stress tests clip

Positive peak dB values are rendered with a leading plus sign in Markdown, for example `+0.26 dBFS` or `+1.17 dBTP`.

## Verdict JSON Fields

The JSON report keeps the original fields and adds these verdict fields:

- `codec_safety_pass`
- `recommended_trim_db`
- `safer_trim_db`
- `estimated_lufs_after_safer_trim`
- `estimated_true_peak_after_safer_trim`
- `estimated_sample_peak_after_safer_trim`

Trim estimates are rounded up to the nearest `0.1 dB`:

```python
minimum_trim_db = max(0, true_peak_dbtp - (-1.0))
safer_trim_db = max(0, true_peak_dbtp - (-1.5))
```

## Verify

```bash
.venv/bin/python -m pytest
audio-master-checker analyze "tmp/Mycal - Konocti Sunset [6-11-26 WAV].wav" --out ./reports --report-name konocti-original
audio-master-checker fix "tmp/Mycal - Konocti Sunset [6-11-26 WAV].wav" --trim -1.5 --out ./fixed-reports --report-name konocti-fixed --compare
audio-master-checker compare "tmp/Mycal - Konocti Sunset [6-11-26 WAV].wav" "tmp/Mycal - Konocti Sunset [6-11-26 WAV] [-1.5dB delivery].wav" --out ./reports --report-name konocti-compare
python3 -m json.tool reports/report.json
sed -n '1,220p' reports/report.md
```

If that sample file is not present, generate a small test WAV and run the CLI:

```bash
mkdir -p tmp reports
ffmpeg -y -f lavfi -i sine=frequency=1000:duration=1 -ar 48000 -ac 2 -c:a pcm_s24le tmp/sample.wav
audio-master-checker analyze tmp/sample.wav --out ./reports --report-name sample
audio-master-checker fix tmp/sample.wav --trim -1.5 --out ./fixed-reports --report-name sample-fixed --compare
audio-master-checker compare tmp/sample.wav "tmp/sample [-1.5dB delivery].wav" --out ./reports --report-name sample-compare
```

## Test

```bash
.venv/bin/python -m pytest
```
