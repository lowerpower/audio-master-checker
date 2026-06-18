from __future__ import annotations

import math
from typing import Any


def _ceil_tenth(value: float) -> float:
    return math.ceil(max(0.0, value) * 10.0 - 1e-12) / 10.0


def _subtract_db(value: float, amount: float) -> float:
    if math.isinf(value) or math.isnan(value):
        return value
    return value - amount


def build_verdict(
    loudness: dict[str, float],
    sample_metrics: dict[str, Any],
    codec_results: list[dict[str, Any]],
) -> dict[str, Any]:
    positives: list[str] = []
    warnings: list[str] = []
    minor_cautions: list[str] = []

    lufs = loudness["integrated_lufs"]
    true_peak = loudness["true_peak_dbtp"]
    sample_peak = float(sample_metrics.get("sample_peak_dbfs", float("-inf")))
    codec_safety_pass = all(int(result.get("samples_over_0_dbfs", 0)) == 0 for result in codec_results)
    recommended_trim_db = _ceil_tenth(true_peak - (-1.0))
    safer_trim_db = _ceil_tenth(true_peak - (-1.5))

    if -11.5 <= lufs <= -9.5:
        positives.append("Integrated loudness is in the target range.")
    elif lufs < -12.5:
        warnings.append(f"Integrated loudness is quiet at {lufs:.2f} LUFS.")
    elif lufs > -9.5:
        warnings.append(f"Integrated loudness is very loud at {lufs:.2f} LUFS.")
    else:
        minor_cautions.append(f"Integrated loudness is outside the target range at {lufs:.2f} LUFS.")

    if true_peak <= -1.0:
        positives.append("True peak is below the strict -1.0 dBTP target.")
    elif true_peak <= -0.7:
        minor_cautions.append(f"True peak is slightly hot at {true_peak:.2f} dBTP.")
    else:
        warnings.append(f"True peak is hot at {true_peak:.2f} dBTP.")

    source_overs = int(sample_metrics.get("samples_over_0_dbfs", 0))
    if source_overs:
        warnings.append(f"Source has {source_overs} samples over 0 dBFS.")
    else:
        positives.append("Source has no samples over 0 dBFS.")

    for result in codec_results:
        overs = int(result.get("samples_over_0_dbfs", 0))
        if overs:
            warnings.append(f"{result['codec']} decode has {overs} samples over 0 dBFS.")

    if warnings:
        status = "caution"
    elif minor_cautions:
        status = "usable with minor caution"
    else:
        status = "safe"

    return {
        "status": status,
        "positives": positives,
        "warnings": [*minor_cautions, *warnings],
        "codec_safety_pass": codec_safety_pass,
        "recommended_trim_db": recommended_trim_db,
        "safer_trim_db": safer_trim_db,
        "estimated_lufs_after_safer_trim": _subtract_db(lufs, safer_trim_db),
        "estimated_true_peak_after_safer_trim": _subtract_db(true_peak, safer_trim_db),
        "estimated_sample_peak_after_safer_trim": _subtract_db(sample_peak, safer_trim_db),
    }
