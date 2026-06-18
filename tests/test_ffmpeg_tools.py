import json
import subprocess

import pytest

from audio_master_checker import ffmpeg_tools
from audio_master_checker.ffmpeg_tools import DependencyError, parse_loudnorm_json


def test_missing_dependency_names_binary(monkeypatch):
    monkeypatch.setattr(ffmpeg_tools.shutil, "which", lambda name: None if name == "ffmpeg" else f"/usr/bin/{name}")
    with pytest.raises(DependencyError, match="ffmpeg"):
        ffmpeg_tools.require_binaries()


def test_run_command_uses_list_args_and_no_shell(monkeypatch):
    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, "{}", "")

    monkeypatch.setattr(ffmpeg_tools.subprocess, "run", fake_run)
    ffmpeg_tools.run_command(["ffprobe", "file.wav"])
    assert calls["args"] == ["ffprobe", "file.wav"]
    assert calls["kwargs"]["shell"] is False


def test_ffprobe_parses_json(monkeypatch):
    monkeypatch.setattr(ffmpeg_tools, "require_binaries", lambda: ("ffmpeg", "ffprobe"))
    payload = {"streams": [{"codec_type": "audio"}], "format": {"format_name": "wav"}}
    monkeypatch.setattr(
        ffmpeg_tools,
        "run_command",
        lambda args, timeout=300: subprocess.CompletedProcess(args, 0, json.dumps(payload), ""),
    )
    assert ffmpeg_tools.ffprobe("x.wav") == payload


def test_loudnorm_json_parsing():
    stderr = """
noise before
{
  "input_i" : "-10.57",
  "input_tp" : "-0.93",
  "input_lra" : "3.90"
}
noise after
"""
    result = parse_loudnorm_json(stderr)
    assert result["integrated_lufs"] == pytest.approx(-10.57)
    assert result["true_peak_dbtp"] == pytest.approx(-0.93)
    assert result["lra_lu"] == pytest.approx(3.9)
