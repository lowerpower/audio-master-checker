from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .ffmpeg_tools import loudnorm, require_binaries, run_command
from .metrics import analyze_samples


CODECS = [
    {
        "name": "MP3 320k",
        "encoded": "mp3_320.mp3",
        "encode_args": ["-codec:a", "libmp3lame", "-b:a", "320k"],
    },
    {
        "name": "AAC 256k",
        "encoded": "aac_256.m4a",
        "encode_args": ["-codec:a", "aac", "-b:a", "256k"],
    },
    {
        "name": "Ogg q8",
        "encoded": "ogg_q8.ogg",
        "encode_args": ["-codec:a", "libvorbis", "-q:a", "8"],
    },
]


def run_codec_tests(path: str | Path, timeout: int = 300) -> list[dict[str, Any]]:
    ffmpeg_bin, _ = require_binaries()
    source = Path(path)
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="audio-master-checker-") as temp_dir:
        work = Path(temp_dir)
        for spec in CODECS:
            encoded = work / spec["encoded"]
            decoded = work / f"{encoded.stem}_decoded.wav"
            run_command(
                [ffmpeg_bin, "-y", "-i", str(source), *spec["encode_args"], str(encoded)],
                timeout=timeout,
            )
            run_command(
                [ffmpeg_bin, "-y", "-i", str(encoded), "-c:a", "pcm_f32le", str(decoded)],
                timeout=timeout,
            )

            sample_metrics = analyze_samples(decoded)
            loudness = loudnorm(decoded, timeout=timeout)
            results.append(
                {
                    "codec": spec["name"],
                    "sample_peak_dbfs": sample_metrics["sample_peak_dbfs"],
                    "true_peak_dbtp": loudness["true_peak_dbtp"],
                    "samples_over_0_dbfs": sample_metrics["samples_over_0_dbfs"],
                }
            )

    return results
