from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class DependencyError(RuntimeError):
    pass


class CommandError(RuntimeError):
    pass


def require_binaries() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    missing = [name for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if path is None]
    if missing:
        raise DependencyError(f"Missing required dependency: {', '.join(missing)}")
    return ffmpeg or "ffmpeg", ffprobe or "ffprobe"


def run_command(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        shell=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise CommandError(f"Command failed ({result.returncode}): {' '.join(args)}\n{stderr}")
    return result


def ffprobe(path: str | Path, timeout: int = 300) -> dict[str, Any]:
    _, ffprobe_bin = require_binaries()
    result = run_command(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        timeout=timeout,
    )
    return json.loads(result.stdout)


def parse_loudnorm_json(stderr: str) -> dict[str, float]:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise CommandError("Could not find loudnorm JSON in ffmpeg output")
    raw = json.loads(stderr[start : end + 1])
    return {
        "integrated_lufs": float(raw["input_i"]),
        "true_peak_dbtp": float(raw["input_tp"]),
        "lra_lu": float(raw["input_lra"]),
    }


def loudnorm(path: str | Path, timeout: int = 300) -> dict[str, float]:
    ffmpeg_bin, _ = require_binaries()
    result = run_command(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        timeout=timeout,
    )
    return parse_loudnorm_json(result.stderr)
