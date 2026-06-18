import pytest

from audio_master_checker.verdict import build_verdict


def verdict(lufs=-10.5, true_peak=-1.2, sample_peak=-1.4, source_overs=0, codec_overs=0):
    return build_verdict(
        {"integrated_lufs": lufs, "true_peak_dbtp": true_peak, "lra_lu": 4.0},
        {"sample_peak_dbfs": sample_peak, "samples_over_0_dbfs": source_overs},
        [{"codec": "MP3 320k", "samples_over_0_dbfs": codec_overs}],
    )


def test_safe_verdict():
    result = verdict()
    assert result["status"] == "safe"
    assert result["codec_safety_pass"] is True


def test_loudness_warning():
    result = verdict(lufs=-9.0)
    assert result["status"] == "caution"
    assert any("very loud" in warning for warning in result["warnings"])


def test_hot_true_peak_warning():
    result = verdict(true_peak=-0.5)
    assert result["status"] == "caution"
    assert any("True peak is hot" in warning for warning in result["warnings"])


def test_source_overs_warning():
    result = verdict(source_overs=2)
    assert result["status"] == "caution"
    assert any("Source has 2" in warning for warning in result["warnings"])


def test_codec_overs_warning():
    result = verdict(codec_overs=3)
    assert result["status"] == "caution"
    assert result["codec_safety_pass"] is False
    assert any("MP3 320k decode" in warning for warning in result["warnings"])


def test_minor_true_peak_status():
    result = verdict(true_peak=-0.8)
    assert result["status"] == "usable with minor caution"


def test_trim_recommendation_rounds_up_to_nearest_tenth():
    result = verdict(lufs=-8.52, true_peak=-0.93, sample_peak=-0.1)
    assert result["recommended_trim_db"] == pytest.approx(0.1)
    assert result["safer_trim_db"] == pytest.approx(0.6)
    assert result["estimated_lufs_after_safer_trim"] == pytest.approx(-9.12)
    assert result["estimated_true_peak_after_safer_trim"] == pytest.approx(-1.53)
    assert result["estimated_sample_peak_after_safer_trim"] == pytest.approx(-0.7)
