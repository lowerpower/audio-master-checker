from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


NEG_INF = float("-inf")


def linear_to_db(value: float) -> float:
    if value <= 0:
        return NEG_INF
    return 20.0 * math.log10(value)


def db_to_linear(db: float) -> float:
    return 10.0 ** (db / 20.0)


def compute_metrics(audio: np.ndarray) -> dict[str, Any]:
    if audio.size == 0:
        abs_audio = np.array([])
        peak = 0.0
        rms = 0.0
    else:
        abs_audio = np.abs(audio)
        peak = float(np.max(abs_audio))
        rms = float(np.sqrt(np.mean(np.square(audio))))

    peak_db = linear_to_db(peak)
    rms_db = linear_to_db(rms)
    crest = NEG_INF if peak_db == NEG_INF or rms_db == NEG_INF else peak_db - rms_db

    return {
        "sample_peak_linear": peak,
        "sample_peak_dbfs": peak_db,
        "rms_linear": rms,
        "rms_dbfs": rms_db,
        "crest_factor_db": crest,
        "samples_over_0_dbfs": int(np.sum(abs_audio > 1.0)) if audio.size else 0,
        "samples_above_minus_0_1_dbfs": int(np.sum(abs_audio >= db_to_linear(-0.1))) if audio.size else 0,
        "samples_above_minus_0_5_dbfs": int(np.sum(abs_audio >= db_to_linear(-0.5))) if audio.size else 0,
        "samples_above_minus_1_0_dbfs": int(np.sum(abs_audio >= db_to_linear(-1.0))) if audio.size else 0,
    }


def analyze_samples(path: str | Path) -> dict[str, Any]:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float64")
    metrics = compute_metrics(audio)
    metrics["sample_rate"] = int(sample_rate)
    metrics["channels"] = int(audio.shape[1]) if audio.ndim == 2 else 1
    metrics["frames"] = int(audio.shape[0]) if audio.ndim else 0
    return metrics
