import math

import numpy as np
import pytest

from audio_master_checker.metrics import compute_metrics, db_to_linear, linear_to_db


def test_linear_to_db():
    assert linear_to_db(1.0) == 0
    assert linear_to_db(0.5) == pytest.approx(-6.0206, abs=0.001)
    assert linear_to_db(0.0) == float("-inf")


def test_silence_returns_negative_infinity():
    result = compute_metrics(np.zeros((4, 2)))
    assert result["sample_peak_dbfs"] == float("-inf")
    assert result["rms_dbfs"] == float("-inf")
    assert result["crest_factor_db"] == float("-inf")
    assert result["samples_over_0_dbfs"] == 0
    assert result["samples_above_minus_0_1_dbfs"] == 0
    assert result["samples_above_minus_0_5_dbfs"] == 0
    assert result["samples_above_minus_1_0_dbfs"] == 0


def test_sample_metrics_for_small_array():
    audio = np.array([[0.5, -0.5], [1.2, 0.0]])
    result = compute_metrics(audio)
    expected_rms = math.sqrt(float(np.mean(np.square(audio))))
    assert result["sample_peak_linear"] == pytest.approx(1.2)
    assert result["sample_peak_dbfs"] == pytest.approx(linear_to_db(1.2))
    assert result["rms_linear"] == pytest.approx(expected_rms)
    assert result["rms_dbfs"] == pytest.approx(linear_to_db(expected_rms))
    assert result["crest_factor_db"] == pytest.approx(result["sample_peak_dbfs"] - result["rms_dbfs"])
    assert result["samples_over_0_dbfs"] == 1


def test_near_ceiling_sample_counts():
    audio = np.array(
        [
            [1.01],
            [db_to_linear(-0.1)],
            [db_to_linear(-0.5)],
            [db_to_linear(-1.0)],
            [db_to_linear(-1.1)],
        ]
    )
    result = compute_metrics(audio)
    assert result["samples_over_0_dbfs"] == 1
    assert result["samples_above_minus_0_1_dbfs"] == 2
    assert result["samples_above_minus_0_5_dbfs"] == 3
    assert result["samples_above_minus_1_0_dbfs"] == 4
