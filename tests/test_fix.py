from pathlib import Path

import pytest

from audio_master_checker import fix
from audio_master_checker.cli import main


def test_default_output_filename_generation():
    output = fix.default_output_path("Mycal - Konocti Sunset [6-11-26 WAV].wav", -1.5)
    assert output.name == "Mycal - Konocti Sunset [6-11-26 WAV] [-1.5dB delivery].wav"


def test_comparison_report_name():
    assert fix.comparison_report_name(None) == "comparison"
    assert fix.comparison_report_name("fixed-song") == "fixed-song-compare"


def test_bit_depth_codec_selection():
    assert fix.codec_for_bit_depth("16") == "pcm_s16le"
    assert fix.codec_for_bit_depth("24") == "pcm_s24le"
    assert fix.codec_for_bit_depth("32f") == "pcm_f32le"


def test_ffmpeg_command_construction_uses_list_args_and_no_shell(monkeypatch):
    monkeypatch.setattr(fix, "require_binaries", lambda: ("ffmpeg", "ffprobe"))
    calls = []

    def fake_run_command(args, timeout=300):
        calls.append((args, timeout))

    monkeypatch.setattr(fix, "run_command", fake_run_command)
    fix.create_fixed_wav("input.wav", "output.wav", -1.5, bit_depth="24", timeout=12)

    args, timeout = calls[0]
    assert isinstance(args, list)
    assert "shell=True" not in args
    assert args == [
        "ffmpeg",
        "-y",
        "-i",
        "input.wav",
        "-af",
        "volume=-1.5dB",
        "-c:a",
        "pcm_s24le",
        "output.wav",
    ]
    assert timeout == 12


def test_invalid_positive_trim_is_rejected():
    with pytest.raises(ValueError, match="positive gain"):
        fix.validate_trim(1.0)


def test_fix_command_writes_output_and_runs_analyzer(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake wav")
    output = tmp_path / "song [-1.5dB delivery].wav"
    reports = tmp_path / "reports"
    calls = []

    monkeypatch.setattr(fix, "loudnorm", lambda path, timeout=300: {"true_peak_dbtp": -0.09})

    def fake_create_fixed_wav(input_path, output_path, trim_db, bit_depth="24", timeout=300):
        calls.append((Path(input_path), Path(output_path), trim_db, bit_depth, timeout))
        Path(output_path).write_bytes(b"fixed wav")
        return Path(output_path)

    monkeypatch.setattr(fix, "create_fixed_wav", fake_create_fixed_wav)

    def fake_analyze_files(paths, timeout=300, codec_tests=True):
        calls.append(("analyze", [Path(path) for path in paths], timeout, codec_tests))
        return {
            "files": [
                {
                    "source_filename": Path(paths[0]).name,
                    "ffprobe": {
                        "streams": [{"codec_type": "audio", "codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 2}],
                        "format": {"format_name": "wav", "duration": "1.0"},
                    },
                    "loudnorm": {"integrated_lufs": -10.02, "true_peak_dbtp": -1.59, "lra_lu": 5.0},
                    "sample_metrics": {
                        "sample_peak_dbfs": -1.6,
                        "rms_dbfs": -12.0,
                        "crest_factor_db": 10.4,
                        "samples_over_0_dbfs": 0,
                        "samples_above_minus_0_1_dbfs": 0,
                        "samples_above_minus_0_5_dbfs": 0,
                        "samples_above_minus_1_0_dbfs": 0,
                    },
                    "codec_stress_tests": [],
                    "verdict": {"status": "safe", "positives": [], "warnings": [], "codec_safety_pass": True},
                }
            ]
        }

    monkeypatch.setattr(fix, "analyze_files", fake_analyze_files)

    exit_code = main([
        "fix",
        str(source),
        "--trim",
        "-1.5",
        "--output",
        str(output),
        "--out",
        str(reports),
        "--report-name",
        "fixed-song",
        "--no-codec-tests",
    ])

    assert exit_code == 0
    assert output.exists()
    assert (reports / "fixed-song.json").exists()
    assert (reports / "fixed-song.md").exists()
    assert calls[0][0] == source
    assert calls[0][1] == output
    assert calls[0][2] == -1.5
    assert calls[1] == ("analyze", [output], 300, False)

    stdout = capsys.readouterr().out
    assert f"Created: {output}" in stdout
    assert "Applied gain: -1.5 dB" in stdout
    assert "Original true peak: -0.09 dBTP" in stdout
    assert "Estimated new true peak: -1.59 dBTP" in stdout
    assert "Measured new true peak: -1.59 dBTP" in stdout
    assert "Measured LUFS: -10.02 LUFS" in stdout
    assert "Codec Safety: PASS" in stdout
    assert f"Report: {reports / 'fixed-song.md'}" in stdout


def test_fix_compare_writes_original_vs_fixed_report(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"fake wav")
    output = tmp_path / "song [-1.5dB delivery].wav"
    reports = tmp_path / "reports"
    calls = []

    monkeypatch.setattr(fix, "loudnorm", lambda path, timeout=300: {"true_peak_dbtp": -0.09})

    def fake_create_fixed_wav(input_path, output_path, trim_db, bit_depth="24", timeout=300):
        calls.append(("fix", Path(input_path), Path(output_path), trim_db, bit_depth, timeout))
        Path(output_path).write_bytes(b"fixed wav")
        return Path(output_path)

    monkeypatch.setattr(fix, "create_fixed_wav", fake_create_fixed_wav)

    def fake_file_report(path):
        return {
            "source_filename": Path(path).name,
            "ffprobe": {
                "streams": [{"codec_type": "audio", "codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 2}],
                "format": {"format_name": "wav", "duration": "1.0"},
            },
            "loudnorm": {"integrated_lufs": -10.02, "true_peak_dbtp": -1.59, "lra_lu": 5.0},
            "sample_metrics": {
                "sample_peak_dbfs": -1.6,
                "rms_dbfs": -12.0,
                "crest_factor_db": 10.4,
                "samples_over_0_dbfs": 0,
                "samples_above_minus_0_1_dbfs": 0,
                "samples_above_minus_0_5_dbfs": 0,
                "samples_above_minus_1_0_dbfs": 0,
            },
            "codec_stress_tests": [],
            "verdict": {"status": "safe", "positives": [], "warnings": [], "codec_safety_pass": True},
        }

    def fake_analyze_files(paths, timeout=300, codec_tests=True):
        path_list = [Path(path) for path in paths]
        calls.append(("analyze", path_list, timeout, codec_tests))
        return {"files": [fake_file_report(path) for path in path_list]}

    monkeypatch.setattr(fix, "analyze_files", fake_analyze_files)

    exit_code = main([
        "fix",
        str(source),
        "--trim",
        "-1.5",
        "--output",
        str(output),
        "--out",
        str(reports),
        "--report-name",
        "fixed-song",
        "--compare",
        "--no-codec-tests",
    ])

    assert exit_code == 0
    assert (reports / "fixed-song.json").exists()
    assert (reports / "fixed-song.md").exists()
    assert (reports / "fixed-song-compare.json").exists()
    assert (reports / "fixed-song-compare.md").exists()
    assert calls[1] == ("analyze", [output], 300, False)
    assert calls[2] == ("analyze", [source, output], 300, False)
    assert f"Compare report: {reports / 'fixed-song-compare.md'}" in capsys.readouterr().out
