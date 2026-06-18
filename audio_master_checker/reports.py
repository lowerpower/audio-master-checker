from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


def build_report(files: list[dict[str, Any]]) -> dict[str, Any]:
    return {"files": files}


def write_json_report(report: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(_json_safe(report), indent=2, allow_nan=False), encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(to_markdown(report), encoding="utf-8")


def _fmt(value: Any, digits: int = 2) -> str:
    if isinstance(value, float):
        if math.isinf(value):
            return "-inf"
        if math.isnan(value):
            return ""
        return f"{value:.{digits}f}"
    if value is None:
        return ""
    return str(value)


def _fmt_db(value: Any, digits: int = 2) -> str:
    if isinstance(value, float) and not math.isinf(value) and not math.isnan(value) and value > 0:
        return f"+{value:.{digits}f}"
    return _fmt(value, digits=digits)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    return value


def _audio_stream(ffprobe: dict[str, Any]) -> dict[str, Any]:
    for stream in ffprobe.get("streams", []):
        if stream.get("codec_type") == "audio":
            return stream
    return {}


def _codec_safety_pass(item: dict[str, Any]) -> bool:
    verdict = item.get("verdict", {})
    if "codec_safety_pass" in verdict:
        return bool(verdict["codec_safety_pass"])
    return all(int(result.get("samples_over_0_dbfs", 0)) == 0 for result in item.get("codec_stress_tests", []))


def _fmt_count(value: Any) -> str:
    return f"{int(value):,}"


def _fmt_warning(text: str) -> str:
    return re.sub(r"\b(\d{4,})(?= samples?\b)", lambda match: _fmt_count(match.group(1)), text)


def _sample_count(samples: dict[str, Any], key: str) -> str:
    return _fmt_count(samples.get(key, 0))


def _db_change(after: float, before: float) -> str:
    return f"{after - before:+.2f} dB"


def _codec_safety_text(item: dict[str, Any]) -> str:
    return "PASS" if _codec_safety_pass(item) else "FAIL"


def _safety_change(original: dict[str, Any], fixed: dict[str, Any]) -> str:
    before = _codec_safety_pass(original)
    after = _codec_safety_pass(fixed)
    if before == after:
        return "unchanged"
    return "improved" if after else "worse"


def _comparison_recommendation(original: dict[str, Any], fixed: dict[str, Any]) -> str:
    original_safe = _codec_safety_pass(original)
    fixed_safe = _codec_safety_pass(fixed)
    original_tp = original["loudnorm"]["true_peak_dbtp"]
    fixed_tp = fixed["loudnorm"]["true_peak_dbtp"]

    if fixed_safe and fixed_tp <= -1.0 and (not original_safe or original_tp > -1.0):
        return "Use the fixed delivery WAV."
    if not fixed_safe:
        return "Reduce more and run the check again."
    if fixed_tp > -1.0:
        return "Reduce more to reach the -1.0 dBTP true-peak target."
    return "Use either version based on loudness preference; the fixed version is safer."


def _delivery_comparison_summary(original: dict[str, Any], fixed: dict[str, Any]) -> list[str]:
    original_loudness = original["loudnorm"]
    fixed_loudness = fixed["loudnorm"]
    original_samples = original["sample_metrics"]
    fixed_samples = fixed["sample_metrics"]

    return [
        "## Delivery Comparison Summary",
        "",
        f"**Original:** {original['source_filename']}",
        f"**Fixed:** {fixed['source_filename']}",
        "",
        "| Metric | Original | Fixed | Change |",
        "| --- | ---: | ---: | --- |",
        "| Integrated loudness | {orig} LUFS | {fixed} LUFS | {change} |".format(
            orig=_fmt(original_loudness["integrated_lufs"]),
            fixed=_fmt(fixed_loudness["integrated_lufs"]),
            change=_db_change(fixed_loudness["integrated_lufs"], original_loudness["integrated_lufs"]),
        ),
        "| True peak | {orig} dBTP | {fixed} dBTP | {change} |".format(
            orig=_fmt_db(original_loudness["true_peak_dbtp"]),
            fixed=_fmt_db(fixed_loudness["true_peak_dbtp"]),
            change=_db_change(fixed_loudness["true_peak_dbtp"], original_loudness["true_peak_dbtp"]),
        ),
        "| Sample peak | {orig} dBFS | {fixed} dBFS | {change} |".format(
            orig=_fmt_db(original_samples["sample_peak_dbfs"]),
            fixed=_fmt_db(fixed_samples["sample_peak_dbfs"]),
            change=_db_change(fixed_samples["sample_peak_dbfs"], original_samples["sample_peak_dbfs"]),
        ),
        "| Codec Safety | {orig} | {fixed} | {change} |".format(
            orig=_codec_safety_text(original),
            fixed=_codec_safety_text(fixed),
            change=_safety_change(original, fixed),
        ),
        "",
        "**Recommendation:**",
        _comparison_recommendation(original, fixed),
        "",
    ]


def to_markdown(report: dict[str, Any]) -> str:
    lines = ["# Audio Master Checker Report", ""]
    files = report.get("files", [])

    if len(files) == 2:
        lines.extend(_delivery_comparison_summary(files[0], files[1]))

    if len(files) > 1:
        lines.extend(
            [
                "## Comparison",
                "",
                "| File | LUFS | True Peak dBTP | Sample Peak dBFS | RMS dBFS | Crest dB | Codec Safety | Verdict |",
                "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for item in files:
            loudness = item["loudnorm"]
            samples = item["sample_metrics"]
            codec_safety = "PASS" if _codec_safety_pass(item) else "FAIL"
            lines.append(
                "| {file} | {lufs} | {tp} | {peak} | {rms} | {crest} | {codec_safety} | {status} |".format(
                    file=item["source_filename"],
                    lufs=_fmt(loudness["integrated_lufs"]),
                    tp=_fmt_db(loudness["true_peak_dbtp"]),
                    peak=_fmt_db(samples["sample_peak_dbfs"]),
                    rms=_fmt_db(samples["rms_dbfs"]),
                    crest=_fmt(samples["crest_factor_db"]),
                    codec_safety=codec_safety,
                    status=item["verdict"]["status"],
                )
            )
        lines.append("")

    for item in files:
        stream = _audio_stream(item["ffprobe"])
        fmt = item["ffprobe"].get("format", {})
        loudness = item["loudnorm"]
        samples = item["sample_metrics"]
        verdict = item["verdict"]
        codec_safety = "PASS" if _codec_safety_pass(item) else "FAIL"

        trim_recommended = loudness["true_peak_dbtp"] > -1.0 or codec_safety == "FAIL"
        summary_lines = [
            f"**Status:** {verdict['status']}",
            f"**Codec Safety:** {codec_safety}",
        ]
        if trim_recommended:
            summary_lines.append(
                f"**Recommended safer trim:** -{_fmt(verdict.get('safer_trim_db', 0.0), digits=1)} dB"
            )

        lines.extend(
            [
                f"## {item['source_filename']}",
                "",
                *summary_lines,
                "",
                "### Format",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Format | {fmt.get('format_name', '')} |",
                f"| Codec | {stream.get('codec_name', '')} |",
                f"| Sample rate | {stream.get('sample_rate', '')} |",
                f"| Channels | {stream.get('channels', '')} |",
                f"| Bits per sample | {stream.get('bits_per_sample', stream.get('bits_per_raw_sample', ''))} |",
                f"| Duration | {fmt.get('duration', '')} |",
                "",
                "### Metrics",
                "",
                "| Metric | Result |",
                "| --- | ---: |",
                f"| Integrated loudness | {_fmt(loudness['integrated_lufs'])} LUFS |",
                f"| True peak | {_fmt_db(loudness['true_peak_dbtp'])} dBTP |",
                f"| Loudness range | {_fmt(loudness['lra_lu'])} LU |",
                f"| Sample peak | {_fmt_db(samples['sample_peak_dbfs'])} dBFS |",
                f"| RMS | {_fmt_db(samples['rms_dbfs'])} dBFS |",
                f"| Crest factor | {_fmt(samples['crest_factor_db'])} dB |",
                f"| Samples over 0 dBFS | {_sample_count(samples, 'samples_over_0_dbfs')} |",
                f"| Samples above -0.1 dBFS | {_sample_count(samples, 'samples_above_minus_0_1_dbfs')} |",
                f"| Samples above -0.5 dBFS | {_sample_count(samples, 'samples_above_minus_0_5_dbfs')} |",
                f"| Samples above -1.0 dBFS | {_sample_count(samples, 'samples_above_minus_1_0_dbfs')} |",
                "",
                "### Codec Stress Test",
                "",
                f"Codec Safety: **{codec_safety}**",
                "",
                "| Codec | Decoded sample peak | Decoded true peak | Over samples |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for result in item.get("codec_stress_tests", []):
            lines.append(
                f"| {result['codec']} | {_fmt_db(result['sample_peak_dbfs'])} dBFS | "
                f"{_fmt_db(result['true_peak_dbtp'])} dBTP | {_fmt_count(result['samples_over_0_dbfs'])} |"
            )
        if not item.get("codec_stress_tests"):
            lines.append("| Skipped |  |  |  |")

        lines.extend(["", "### Verdict", "", f"**{verdict['status']}**", ""])
        for text in verdict.get("positives", []):
            lines.append(f"- {text}")
        for text in verdict.get("warnings", []):
            lines.append(f"- {_fmt_warning(text)}")

        lines.extend(["", "### Recommended Action", ""])
        if trim_recommended:
            lines.extend(
                [
                    "Trim the final master or ask for a true-peak-limited export.",
                    f"In Audacity or a DAW, apply Amplify/Gain of **-{_fmt(verdict.get('safer_trim_db', 0.0), digits=1)} dB** to create the safer delivery version.",
                    "",
                    "| Estimate | Value |",
                    "| --- | ---: |",
                    f"| Recommended reduction to reach -1.0 dBTP | {_fmt(verdict.get('recommended_trim_db', 0.0), digits=1)} dB |",
                    f"| Safer reduction to reach -1.5 dBTP | {_fmt(verdict.get('safer_trim_db', 0.0), digits=1)} dB |",
                    f"| Estimated LUFS after safer trim | {_fmt(verdict.get('estimated_lufs_after_safer_trim'))} LUFS |",
                    f"| Estimated true peak after safer trim | {_fmt_db(verdict.get('estimated_true_peak_after_safer_trim'))} dBTP |",
                    f"| Estimated sample peak after safer trim | {_fmt_db(verdict.get('estimated_sample_peak_after_safer_trim'))} dBFS |",
                ]
            )
        else:
            lines.append("No trim is recommended from true-peak or codec safety results.")
        lines.append("")

    return "\n".join(lines)
