Yes — this is very doable. I’d build it as a **Python/FastAPI audio analysis web tool** behind Caddy. Use `ffmpeg/ffprobe` for loudness/codec tests, and Python `soundfile + numpy` for sample peak, crest factor, over-sample counts, and report formatting.

Here’s a Codex-ready plan.

# Codex Plan: Audio Mastering Analyzer Web Tool

## Goal

Build a self-hosted web tool for analyzing mastered WAV files before upload to DistroKid/streaming platforms.

The tool should accept one or more audio files and produce a report like:

* Format
* Bit depth / codec
* Sample rate
* Channels
* Integrated LUFS
* True peak dBTP
* Sample peak dBFS
* Loudness range LU
* Crest factor dB
* Samples over 0 dB
* Codec stress tests:

  * MP3 320k
  * AAC 256k
  * Ogg Vorbis q8
* Verdict:

  * safe / caution / hot
  * target loudness comparison
  * true-peak safety
  * codec over warning

The output should be viewable as HTML and downloadable as Markdown and JSON.

## Target Report Style

Example output:

```text
Richmond Park Master Test 2

Metric                       Result
Format                       32-bit float / 48 kHz
Integrated loudness          -10.57 LUFS
True peak                    -0.93 dBTP
Sample peak                  -1.47 dBFS
Loudness range               3.9 LU
Crest factor                 12.5 dB
Samples over 0 dB            0

Codec Stress Test

Codec        Sample Peak After Decode    True Peak After Decode    Over-0 Samples
MP3 320k     -1.28 dBFS                  -0.93 dBTP                0
AAC 256k     -1.03 dBFS                  -0.85 dBTP                0
Ogg q8       -1.04 dBFS                  -0.87 dBTP                0

Verdict:
This is usable. It is close to the target loudness range of -10 to -11 LUFS.
True peak is slightly above strict -1.0 dBTP but codec tests produced no clipping.
```

## Architecture

Use:

```text
Caddy HTTPS reverse proxy
        ↓
FastAPI app
        ↓
ffmpeg / ffprobe / Python analysis
        ↓
HTML / Markdown / JSON report
```

Recommended stack:

```text
Python 3.11+
FastAPI
uvicorn
jinja2
python-multipart
soundfile
numpy
pydantic
ffmpeg installed system-wide
```

Optional later:

```text
Docker
SQLite job history
Celery/RQ background queue
Charts using matplotlib or plain SVG
```

## Repository Layout

Create repo:

```text
audio-master-checker/
  app/
    main.py
    analyzer.py
    codec_tests.py
    loudness.py
    reports.py
    verdict.py
    templates/
      index.html
      report.html
    static/
      style.css
  scripts/
    analyze_audio.py
  tests/
    test_metrics.py
    test_verdict.py
  requirements.txt
  README.md
  Caddyfile.example
  systemd/
    audio-master-checker.service
```

## Core Features

### 1. Upload Page

Route:

```text
GET /
```

Show simple form:

* Upload WAV/AIFF/FLAC/MP3
* Optional comparison upload:

  * Test 1
  * Test 2
  * Original
  * Master
* Button: Analyze

Route:

```text
POST /analyze
```

Accept one or multiple files.

Store each upload in a temporary job directory:

```text
/tmp/audio-master-checker/<job_id>/
```

Use sanitized filenames.

Reject files larger than configurable max size, for example 500 MB.

### 2. File Format Detection

Use `ffprobe`:

```bash
ffprobe -v error -show_streams -show_format -of json input.wav
```

Extract:

* codec name
* sample rate
* channels
* bits per sample
* bitrate
* duration
* format name

Map codecs to friendly labels:

```text
pcm_s16le → 16-bit PCM
pcm_s24le → 24-bit PCM
pcm_f32le → 32-bit float
```

### 3. Loudness / True Peak

Use ffmpeg `loudnorm` first pass:

```bash
ffmpeg -hide_banner -nostats -i input.wav \
  -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json \
  -f null -
```

Parse stderr JSON fields:

```text
input_i       → integrated LUFS
input_tp      → true peak dBTP
input_lra     → loudness range LU
input_thresh
target_offset
```

Important: only use this for measurement. Do not normalize the file.

### 4. Sample Peak / RMS / Crest / Over Samples

Use Python:

```python
import soundfile as sf
import numpy as np

audio, sr = sf.read(path, always_2d=True, dtype="float64")
abs_audio = np.abs(audio)

sample_peak = np.max(abs_audio)
sample_peak_dbfs = 20 * np.log10(sample_peak)

rms = np.sqrt(np.mean(audio ** 2))
rms_dbfs = 20 * np.log10(rms)

crest_factor_db = sample_peak_dbfs - rms_dbfs

samples_over_0 = int(np.sum(abs_audio > 1.0))
samples_gt_minus_0_1 = int(np.sum(abs_audio > db_to_linear(-0.1)))
samples_gt_minus_0_5 = int(np.sum(abs_audio > db_to_linear(-0.5)))
samples_gt_minus_1_0 = int(np.sum(abs_audio > db_to_linear(-1.0)))
```

Use helper:

```python
def db_to_linear(db: float) -> float:
    return 10 ** (db / 20)
```

### 5. Codec Stress Tests

For each uploaded file, create lossy versions and decode them back to float WAV.

#### MP3 320k

```bash
ffmpeg -y -i input.wav -codec:a libmp3lame -b:a 320k temp_mp3_320.mp3
ffmpeg -y -i temp_mp3_320.mp3 -c:a pcm_f32le temp_mp3_320_decoded.wav
```

#### AAC 256k

```bash
ffmpeg -y -i input.wav -codec:a aac -b:a 256k temp_aac_256.m4a
ffmpeg -y -i temp_aac_256.m4a -c:a pcm_f32le temp_aac_256_decoded.wav
```

#### Ogg Vorbis q8

```bash
ffmpeg -y -i input.wav -codec:a libvorbis -q:a 8 temp_ogg_q8.ogg
ffmpeg -y -i temp_ogg_q8.ogg -c:a pcm_f32le temp_ogg_q8_decoded.wav
```

Then run the same measurement functions on each decoded WAV:

* sample peak dBFS
* true peak dBTP
* samples over 0 dB

### 6. Verdict Rules

Implement `verdict.py`.

Suggested thresholds:

```python
TARGET_LUFS_MIN = -11.5
TARGET_LUFS_MAX = -9.5

STRICT_TRUE_PEAK = -1.0
SAFE_TRUE_PEAK = -1.5

def make_verdict(metrics, codec_results):
    warnings = []
    positives = []

    lufs = metrics.integrated_lufs
    tp = metrics.true_peak_dbtp
    overs = metrics.samples_over_0

    if -11.5 <= lufs <= -9.5:
        positives.append("Loudness is in the modern loud master range.")
    elif lufs > -9.5:
        warnings.append("Very loud master; may be heavily limited.")
    elif lufs < -12.5:
        warnings.append("Conservative/quiet compared with loud commercial masters.")

    if tp <= -1.0:
        positives.append("True peak is at or below the usual -1.0 dBTP streaming safety target.")
    elif tp <= -0.7:
        warnings.append("True peak is slightly above strict -1.0 dBTP but close.")
    else:
        warnings.append("True peak is hot; consider lowering output ceiling or trimming gain.")

    if overs > 0:
        warnings.append("File contains samples over 0 dBFS.")
    else:
        positives.append("No samples over 0 dBFS in the source file.")

    codec_over_count = sum(1 for c in codec_results if c.samples_over_0 > 0)
    if codec_over_count == 0:
        positives.append("Codec stress tests produced no over-0 samples.")
    else:
        warnings.append("One or more codec stress tests produced over-0 samples.")

    if not warnings:
        status = "safe"
    elif tp <= -0.7 and codec_over_count == 0:
        status = "usable with minor caution"
    else:
        status = "caution"

    return status, positives, warnings
```

### 7. Comparison Mode

If multiple files are uploaded, generate a comparison table.

Example:

```text
Metric             Test 1        Test 2
Format             32f / 48 kHz  32f / 48 kHz
LUFS               -11.94        -10.57
True peak          -1.11         -0.93
Sample peak        -1.47         -1.47
LRA                4.0           3.9
Crest              13.9          12.5
Samples over 0     0             0
```

Also show:

```text
Test 2 is 1.37 LUFS louder than Test 1.
Test 2 has 0.18 dB less true-peak headroom than Test 1.
Both files passed codec stress tests.
```

### 8. Output Formats

For each job, write:

```text
report.html
report.md
report.json
```

Routes:

```text
GET /report/{job_id}
GET /report/{job_id}.md
GET /report/{job_id}.json
```

HTML should be simple and mobile-friendly.

Markdown should be paste-ready for sending to a mastering friend.

JSON should include all raw metrics.

### 9. CLI Tool

Also create a CLI so the analyzer can run without the website:

```bash
python scripts/analyze_audio.py "file1.wav" "file2.wav" --out ./reports/
```

CLI should produce the same Markdown and JSON.

This is useful for testing before building the web UI.

### 10. Caddy Hosting

Example Caddyfile:

```caddyfile
mastercheck.mycal.net {
    reverse_proxy 127.0.0.1:8099

    request_body {
        max_size 600MB
    }
}
```

Run app with systemd on localhost only:

```text
127.0.0.1:8099
```

### 11. systemd Service

Create:

```text
/etc/systemd/system/audio-master-checker.service
```

Example:

```ini
[Unit]
Description=Audio Master Checker
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/audio-master-checker
Environment="PATH=/opt/audio-master-checker/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/audio-master-checker/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8099
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 12. Security Requirements

* Do not shell-interpolate filenames.
* Always call subprocess with list args.
* Store uploads in unique temp directories.
* Sanitize display filenames.
* Limit file size.
* Limit file extensions.
* Set subprocess timeouts.
* Delete old jobs after configurable retention, for example 24 hours.
* Do not expose uploaded files publicly except through the generated report pages.
* Run service as non-root.
* Caddy terminates HTTPS.

### 13. First Milestone

Build CLI-only version first.

Acceptance criteria:

```bash
python scripts/analyze_audio.py "Richmond Park Master Test 2 32f.wav"
```

Should output:

* JSON report
* Markdown report
* format info
* LUFS
* true peak
* sample peak
* loudness range
* crest factor
* codec stress results
* verdict

### 14. Second Milestone

Build minimal web UI.

Acceptance criteria:

* Upload one WAV
* Show report page
* Download Markdown
* Download JSON

### 15. Third Milestone

Build comparison mode.

Acceptance criteria:

* Upload two WAVs
* Show side-by-side comparison
* Show deltas
* Show verdict explaining which is safer/louder/hotter

### 16. Fourth Milestone

Polish

Add:

* drag-and-drop upload
* progress status
* job history
* cleanup task
* optional password protection via Caddy basic auth
* optional charts:

  * waveform preview
  * loudness comparison
  * codec peak comparison

I’d have Codex build the **CLI first**, because once that is accurate, the website is mostly just upload/report plumbing.




