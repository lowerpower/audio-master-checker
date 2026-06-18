Proposed Plan


  # Milestone 1 Plan: CLI Audio Analyzer

  ## Summary

  Build a Python CLI that accepts one or more audio files and writes JSON plus Markdown reports. The CLI will use ffprobe for format metadata, ffmpeg loudnorm for LUFS / true peak / LRA, Python
  soundfile + numpy for sample-level metrics, and ffmpeg round-trips for MP3 320, AAC 256, and Ogg q8 codec stress tests.

  No web app, uploads, Caddy, systemd, or HTML output in Milestone 1.

  ## File-By-File Plan

  ### requirements.txt

  Add runtime and test dependencies:

  - numpy
  - soundfile
  - pytest

  Do not add FastAPI/web dependencies yet.

  ### audio_master_checker/__init__.py

  Create package marker and expose a version string, for example __version__ = "0.1.0".

  ### audio_master_checker/ffmpeg_tools.py

  Implement subprocess-only wrappers using list args and shell=False.

  Responsibilities:

  - Locate required binaries with shutil.which("ffmpeg") and shutil.which("ffprobe").
  - Raise a clear error if either is missing.
  - Run commands with timeout support.
  - Capture stdout/stderr.
  - Parse ffprobe -v error -show_streams -show_format -of json <path>.
  - Run loudnorm measurement with:

  ffmpeg -hide_banner -nostats -i <input> -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -

  - Extract loudnorm JSON from stderr and return integrated LUFS, true peak dBTP, and LRA.

  ### audio_master_checker/metrics.py

  Implement Python audio metrics.

  Responsibilities:

  - Load audio with soundfile.read(path, always_2d=True, dtype="float64").
  - Compute:
      - sample peak linear
      - sample peak dBFS
      - RMS linear
      - RMS dBFS
      - crest factor dB
      - samples over 0 dBFS, using abs(sample) > 1.0

  - Handle silent files without math crashes by returning -inf for dB values where appropriate.
  - Keep helpers like linear_to_db() and db_to_linear() pure and easy to test.

  ### audio_master_checker/codecs.py

  Implement codec stress tests.

  Responsibilities:

  - For each source file, create a temporary working directory.
  - Encode and decode:
      - MP3 320: libmp3lame, -b:a 320k
      - AAC 256: native aac, -b:a 256k
      - Ogg q8: libvorbis, -q:a 8

  - Decode each lossy file back to pcm_f32le WAV.
  - For each decoded file, collect:
      - sample peak dBFS
      - true peak dBTP via loudnorm
      - samples over 0 dBFS

  - Return structured codec result objects.
  - Use subprocess list args only.

  ### audio_master_checker/verdict.py

  Implement verdict rules.

  Use these defaults from DESIGN.md:

  - Target loudness range: -11.5 <= LUFS <= -9.5
  - Quiet warning: < -12.5 LUFS
  - Very loud warning: > -9.5 LUFS
  - Strict true peak target: <= -1.0 dBTP
  - Minor true peak caution: <= -0.7 dBTP
  - Source samples over 0 dBFS are a warning.
  - Any codec stress test with over-0 samples is a warning.

  Return a structured verdict:

  - status: safe, usable with minor caution, or caution
  - positives: list of strings
  - warnings: list of strings

  ### audio_master_checker/reports.py

  Implement JSON and Markdown report generation.

  Responsibilities:

  - Build a JSON-serializable report object per file.
  - Include:
      - source filename
      - ffprobe format info
      - loudnorm metrics
      - Python sample metrics
      - codec stress results
      - verdict

  - For multiple input files, output one combined JSON report containing a files array.
  - Markdown should include one section per file with:
      - format table
      - loudness/sample metric table
      - codec stress test table
      - verdict text

  - For multiple files, add a simple comparison table for core metrics.

  ### audio_master_checker/analyzer.py

  Coordinate full analysis.

  Responsibilities:

  - Validate input paths exist and are files.
  - Require ffmpeg/ffprobe before starting.
  - For each file:
      - collect ffprobe info
      - collect loudnorm metrics
      - collect Python sample metrics
      - run codec stress tests
      - generate verdict

  - Return the combined report data structure.
  - Keep orchestration thin so unit tests can mock ffmpeg calls.

  ### scripts/analyze_audio.py

  Create the CLI entrypoint.

  CLI behavior:

  python scripts/analyze_audio.py file1.wav file2.wav --out ./reports

  Arguments:

  - positional files: one or more audio files
  - --out: output directory, default ./reports
  - --timeout: subprocess timeout, default 300
  - --no-codec-tests: optional test/debug flag to skip codec stress tests

  Output files:

  - report.json
  - report.md

  Behavior:

  - Create output directory if needed.
  - Exit nonzero with a clear message if ffmpeg/ffprobe is missing or analysis fails.
  - Print paths to generated reports on success.

  ### tests/test_metrics.py

  Unit tests for pure metric helpers.

  Test cases:

  - linear_to_db(1.0) == 0
  - linear_to_db(0.5) is approximately -6.02
  - silence returns -inf dB values without crashing
  - sample peak, RMS, crest factor, and over-0 counts are correct for small arrays

  ### tests/test_verdict.py

  Unit tests for verdict rules.

  Test cases:

  - safe loudness, true peak below -1.0, no source overs, no codec overs returns safe
  - LUFS above -9.5 creates loudness warning
  - true peak above -0.7 creates hot true peak warning
  - source samples over 0 creates warning
  - any codec over-0 samples creates codec warning
  - minor true peak issue with no codec overs returns usable with minor caution

  ### tests/test_reports.py

  Unit tests for report formatting.

  Test cases:

  - JSON report contains expected top-level files array
  - Markdown contains source filename, metric table, codec table, and verdict section
  - Multiple files produce a comparison section

  ### tests/test_ffmpeg_tools.py

  Keep practical and mostly mocked.

  Test cases:

  - missing ffmpeg or ffprobe raises a clear dependency error
  - subprocess calls are made with list args
  - ffprobe JSON parsing extracts stream and format info
  - loudnorm stderr JSON parsing works with typical ffmpeg output around it

  ### README.md

  Add install/run docs for Milestone 1 only.

  Include:

  - System dependency: ffmpeg with ffprobe
  - Python setup:

  python3 -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt

  - Run example:

  python scripts/analyze_audio.py "master.wav" --out ./reports

  - Multi-file example:

  python scripts/analyze_audio.py "test1.wav" "test2.wav" --out ./reports

  - Test command:

  pytest

  - Note that web UI is planned later and intentionally not included yet.

  ## Acceptance Tests

  ### CLI Single File

  Given a valid audio file:

  python scripts/analyze_audio.py "master.wav" --out ./reports

  Expected:

  - exits with status 0
  - creates ./reports/report.json
  - creates ./reports/report.md
  - JSON includes ffprobe format info
  - JSON includes integrated LUFS, true peak dBTP, and LRA
  - JSON includes sample peak dBFS, RMS dBFS, crest factor dB, and samples over 0
  - JSON includes MP3 320, AAC 256, and Ogg q8 codec stress results
  - Markdown includes metric table, codec stress table, and verdict

  ### CLI Multiple Files

  Given two valid audio files:

  python scripts/analyze_audio.py "test1.wav" "test2.wav" --out ./reports

  Expected:

  - exits with status 0
  - JSON contains two file report entries
  - Markdown contains separate sections for both files
  - Markdown contains a comparison table for core metrics

  ### Missing Dependencies

  If ffmpeg or ffprobe is unavailable:

  - CLI exits nonzero
  - error message names the missing dependency
  - no partial success is reported

  ### Invalid Input

  Given a nonexistent file:

  python scripts/analyze_audio.py "missing.wav"

  Expected:

  - exits nonzero
  - error message identifies the missing file
  - no report is written

  ### No Shell Execution

  Verification:

  - tests confirm subprocess calls receive list arguments
  - implementation does not use shell=True

  ### Unit Test Suite

  Run:

  pytest

  Expected:

  - metric helper tests pass
  - verdict rule tests pass
  - report formatting tests pass
  - ffmpeg wrapper parsing tests pass

  ## Assumptions

  - Python package name will be audio_master_checker.
  - Reports are combined into one report.json and one report.md per CLI run.
  - Codec stress tests are enabled by default.
  - Temporary codec files are created in system temp directories and cleaned up automatically.
  - HTML/web output is deferred to a later milestone.


──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


› Implement Milestone 1 from the approved plan. Keep the code small. Run tests. Then run the CLI against a sample WAV if available. Show me the exact commands to verify it.



