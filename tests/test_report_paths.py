import pytest

from audio_master_checker.report_paths import report_paths


def test_default_report_paths():
    json_path, md_path = report_paths("reports")
    assert str(json_path) == "reports/report.json"
    assert str(md_path) == "reports/report.md"


def test_named_report_paths():
    json_path, md_path = report_paths("reports", "song")
    assert str(json_path) == "reports/song.json"
    assert str(md_path) == "reports/song.md"


def test_named_report_paths_strip_known_suffix():
    json_path, md_path = report_paths("reports", "song.md")
    assert str(json_path) == "reports/song.json"
    assert str(md_path) == "reports/song.md"


def test_report_name_rejects_paths():
    with pytest.raises(ValueError, match="filename stem"):
        report_paths("reports", "nested/song")
