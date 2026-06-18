from pathlib import Path

from audio_master_checker import cli


def test_analyze_command_uses_report_name(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake wav")
    out = tmp_path / "reports"

    monkeypatch.setattr(
        cli,
        "analyze_files",
        lambda files, timeout=300, codec_tests=True: {"files": []},
    )

    exit_code = cli.main(["analyze", str(source), "--out", str(out), "--report-name", "song-check"])

    assert exit_code == 0
    assert (out / "song-check.json").exists()
    assert (out / "song-check.md").exists()
    stdout = capsys.readouterr().out
    assert f"Wrote JSON report: {out / 'song-check.json'}" in stdout
    assert f"Wrote Markdown report: {out / 'song-check.md'}" in stdout



def _comparison_file_report(path):
    return {
        "source_filename": Path(path).name,
        "ffprobe": {
            "streams": [{"codec_type": "audio", "codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 2}],
            "format": {"format_name": "wav", "duration": "1.0"},
        },
        "loudnorm": {"integrated_lufs": -10.0, "true_peak_dbtp": -1.5, "lra_lu": 3.0},
        "sample_metrics": {
            "sample_peak_dbfs": -1.5,
            "rms_dbfs": -12.0,
            "crest_factor_db": 10.5,
            "samples_over_0_dbfs": 0,
            "samples_above_minus_0_1_dbfs": 0,
            "samples_above_minus_0_5_dbfs": 0,
            "samples_above_minus_1_0_dbfs": 0,
        },
        "codec_stress_tests": [],
        "verdict": {"status": "safe", "positives": [], "warnings": [], "codec_safety_pass": True},
    }


def test_compare_command_uses_two_files_and_report_name(tmp_path, monkeypatch, capsys):
    original = tmp_path / "original.wav"
    fixed = tmp_path / "fixed.wav"
    original.write_bytes(b"original")
    fixed.write_bytes(b"fixed")
    out = tmp_path / "reports"
    calls = []

    def fake_analyze_files(files, timeout=300, codec_tests=True):
        calls.append(([Path(path) for path in files], timeout, codec_tests))
        return {"files": [_comparison_file_report(path) for path in files]}

    monkeypatch.setattr(cli, "analyze_files", fake_analyze_files)

    exit_code = cli.main([
        "compare",
        str(original),
        str(fixed),
        "--out",
        str(out),
        "--report-name",
        "original-vs-fixed",
        "--no-codec-tests",
    ])

    assert exit_code == 0
    assert calls == [([original, fixed], 300, False)]
    assert (out / "original-vs-fixed.json").exists()
    assert (out / "original-vs-fixed.md").exists()
    markdown = (out / "original-vs-fixed.md").read_text()
    assert "## Delivery Comparison Summary" in markdown
    stdout = capsys.readouterr().out
    assert f"Wrote comparison JSON report: {out / 'original-vs-fixed.json'}" in stdout
    assert f"Wrote comparison Markdown report: {out / 'original-vs-fixed.md'}" in stdout
