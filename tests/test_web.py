from pathlib import Path

from fastapi.testclient import TestClient

from audio_master_checker.web import app as web_app


def fake_file_report(name="song.wav"):
    return {
        "source_filename": name,
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


def test_index_loads(tmp_path):
    app = web_app.create_app(tmp_path)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Audio Master Checker" in response.text
    assert "Create Safer Delivery" in response.text


def test_analyze_upload_writes_report_and_downloads(tmp_path, monkeypatch):
    app = web_app.create_app(tmp_path)
    client = TestClient(app)
    calls = []

    def fake_analyze(paths, codec_tests=True):
        calls.append(([Path(path) for path in paths], codec_tests))
        return {"files": [fake_file_report(Path(paths[0]).name)]}

    monkeypatch.setattr(web_app, "analyze_files", fake_analyze)
    response = client.post(
        "/analyze",
        data={"codec_tests": "false"},
        files=[("files", ("song.wav", b"audio", "audio/wav"))],
    )

    assert response.status_code == 200
    assert "Analysis Report" in response.text
    assert calls[0][0][0].name == "song.wav"
    assert calls[0][1] is False
    assert "Markdown" in response.text
    assert "JSON" in response.text

    md_path = next(tmp_path.glob("*/report.md"))
    download = client.get(f"/jobs/{md_path.parent.name}/report.md")
    assert download.status_code == 200
    assert "Audio Master Checker Report" in download.text


def test_fix_upload_writes_fixed_download_and_compare_report(tmp_path, monkeypatch):
    app = web_app.create_app(tmp_path)
    client = TestClient(app)

    def fake_fix_file(input_path, trim_db=-1.5, output_path=None, bit_depth="24", report_dir="./reports", report_name=None, compare=False, codec_tests=True, timeout=300):
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fixed")
        report_dir = Path(report_dir)
        fixed_json = report_dir / "fixed.json"
        fixed_md = report_dir / "fixed.md"
        compare_json = report_dir / "fixed-compare.json"
        compare_md = report_dir / "fixed-compare.md"
        fixed_json.write_text('{"files": []}', encoding="utf-8")
        fixed_md.write_text("# Fixed Report", encoding="utf-8")
        compare_json.write_text('{"files": []}', encoding="utf-8")
        compare_md.write_text("# Compare Report", encoding="utf-8")
        return {
            "output_path": output,
            "report_json_path": fixed_json,
            "report_md_path": fixed_md,
            "compare_report_json_path": compare_json if compare else None,
            "compare_report_md_path": compare_md if compare else None,
            "report": {"files": [fake_file_report(output.name)]},
            "compare_report": {"files": [fake_file_report("song.wav"), fake_file_report(output.name)]} if compare else None,
        }

    monkeypatch.setattr(web_app, "fix_file", fake_fix_file)
    response = client.post(
        "/fix",
        data={"trim": "-1.5", "bit_depth": "24", "compare": "true", "codec_tests": "false"},
        files={"file": ("song.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 200
    assert "Fixed Delivery Report" in response.text
    assert "Fixed WAV" in response.text
    assert "Compare Report" in response.text
    fixed_path = next(tmp_path.glob("*/outputs/*.wav"))
    download = client.get(f"/jobs/{fixed_path.parent.parent.name}/{fixed_path.name}")
    assert download.status_code == 200
    assert download.content == b"fixed"


def test_compare_upload_writes_delivery_summary(tmp_path, monkeypatch):
    app = web_app.create_app(tmp_path)
    client = TestClient(app)

    def fake_analyze(paths, codec_tests=True):
        return {"files": [fake_file_report(Path(path).name) for path in paths]}

    monkeypatch.setattr(web_app, "analyze_files", fake_analyze)
    response = client.post(
        "/compare",
        data={"codec_tests": "false"},
        files={
            "original": ("original.wav", b"one", "audio/wav"),
            "fixed": ("fixed.wav", b"two", "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert "Comparison Report" in response.text
    assert "Delivery Comparison Summary" in response.text
