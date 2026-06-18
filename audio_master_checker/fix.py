from __future__ import annotations

from pathlib import Path
from typing import Any

from .analyzer import analyze_files
from .ffmpeg_tools import loudnorm, require_binaries, run_command
from .report_paths import report_paths
from .reports import write_json_report, write_markdown_report


BIT_DEPTH_CODECS = {
    "16": "pcm_s16le",
    "24": "pcm_s24le",
    "32f": "pcm_f32le",
}


def validate_trim(trim_db: float) -> float:
    if trim_db > 0:
        raise ValueError("Trim must be 0 dB or negative; positive gain is not allowed")
    return trim_db


def codec_for_bit_depth(bit_depth: str) -> str:
    try:
        return BIT_DEPTH_CODECS[bit_depth]
    except KeyError as exc:
        choices = ", ".join(BIT_DEPTH_CODECS)
        raise ValueError(f"Unsupported bit depth: {bit_depth}. Choose one of: {choices}") from exc


def format_trim(trim_db: float) -> str:
    text = f"{trim_db:.6f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def default_output_path(input_path: str | Path, trim_db: float) -> Path:
    path = Path(input_path)
    return path.with_name(f"{path.stem} [{format_trim(trim_db)}dB delivery]{path.suffix}")


def build_ffmpeg_fix_args(
    input_path: str | Path,
    output_path: str | Path,
    trim_db: float,
    bit_depth: str = "24",
) -> list[str]:
    ffmpeg_bin, _ = require_binaries()
    validate_trim(trim_db)
    codec = codec_for_bit_depth(bit_depth)
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-af",
        f"volume={format_trim(trim_db)}dB",
        "-c:a",
        codec,
        str(output_path),
    ]


def create_fixed_wav(
    input_path: str | Path,
    output_path: str | Path,
    trim_db: float,
    bit_depth: str = "24",
    timeout: int = 300,
) -> Path:
    args = build_ffmpeg_fix_args(input_path, output_path, trim_db, bit_depth)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    run_command(args, timeout=timeout)
    return out


def comparison_report_name(report_name: str | None) -> str:
    return "comparison" if report_name is None else f"{report_name}-compare"


def fix_file(
    input_path: str | Path,
    trim_db: float = -1.5,
    output_path: str | Path | None = None,
    bit_depth: str = "24",
    report_dir: str | Path = "./reports",
    report_name: str | None = None,
    compare: bool = False,
    timeout: int = 300,
    codec_tests: bool = True,
) -> dict[str, Any]:
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file does not exist: {source}")
    if not source.is_file():
        raise ValueError(f"Input path is not a file: {source}")

    trim_db = validate_trim(trim_db)
    output = Path(output_path) if output_path else default_output_path(source, trim_db)

    original_loudness = loudnorm(source, timeout=timeout)
    create_fixed_wav(source, output, trim_db, bit_depth=bit_depth, timeout=timeout)

    report = analyze_files([output], timeout=timeout, codec_tests=codec_tests)
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)
    json_path, md_path = report_paths(report_path, report_name)
    write_json_report(report, json_path)
    write_markdown_report(report, md_path)

    compare_json_path = None
    compare_md_path = None
    compare_report = None
    if compare:
        compare_report = analyze_files([source, output], timeout=timeout, codec_tests=codec_tests)
        compare_json_path, compare_md_path = report_paths(report_path, comparison_report_name(report_name))
        write_json_report(compare_report, compare_json_path)
        write_markdown_report(compare_report, compare_md_path)

    measured = report["files"][0]
    measured_loudness = measured["loudnorm"]
    verdict = measured["verdict"]

    return {
        "output_path": output,
        "trim_db": trim_db,
        "original_true_peak_dbtp": original_loudness["true_peak_dbtp"],
        "estimated_new_true_peak_dbtp": original_loudness["true_peak_dbtp"] + trim_db,
        "measured_new_true_peak_dbtp": measured_loudness["true_peak_dbtp"],
        "measured_lufs": measured_loudness["integrated_lufs"],
        "codec_safety": "PASS" if verdict.get("codec_safety_pass") else "FAIL",
        "report_json_path": json_path,
        "report_md_path": md_path,
        "compare_report_json_path": compare_json_path,
        "compare_report_md_path": compare_md_path,
        "report": report,
        "compare_report": compare_report,
    }
