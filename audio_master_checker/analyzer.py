from __future__ import annotations

from pathlib import Path
from typing import Any

from .codecs import run_codec_tests
from .ffmpeg_tools import ffprobe, loudnorm, require_binaries
from .metrics import analyze_samples
from .reports import build_report
from .verdict import build_verdict


def analyze_files(
    paths: list[str | Path],
    timeout: int = 300,
    codec_tests: bool = True,
) -> dict[str, Any]:
    require_binaries()
    file_reports: list[dict[str, Any]] = []

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Input path is not a file: {path}")

        probe = ffprobe(path, timeout=timeout)
        loudness = loudnorm(path, timeout=timeout)
        sample_metrics = analyze_samples(path)
        codec_results = run_codec_tests(path, timeout=timeout) if codec_tests else []
        verdict = build_verdict(loudness, sample_metrics, codec_results)

        file_reports.append(
            {
                "source_filename": path.name,
                "source_path": str(path),
                "ffprobe": probe,
                "loudnorm": loudness,
                "sample_metrics": sample_metrics,
                "codec_stress_tests": codec_results,
                "verdict": verdict,
            }
        )

    return build_report(file_reports)
