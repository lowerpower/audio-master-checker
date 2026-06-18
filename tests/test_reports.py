from audio_master_checker.reports import build_report, to_markdown


def file_report(name="master.wav", codec_overs=0):
    return {
        "source_filename": name,
        "ffprobe": {
            "streams": [{"codec_type": "audio", "codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 2}],
            "format": {"format_name": "wav", "duration": "10.0"},
        },
        "loudnorm": {"integrated_lufs": -10.5, "true_peak_dbtp": -0.9, "lra_lu": 3.2},
        "sample_metrics": {
            "sample_peak_dbfs": 0.26,
            "rms_dbfs": -13.0,
            "crest_factor_db": 13.26,
            "samples_over_0_dbfs": 0,
            "samples_above_minus_0_1_dbfs": 10,
            "samples_above_minus_0_5_dbfs": 26466,
            "samples_above_minus_1_0_dbfs": 61965,
        },
        "codec_stress_tests": [
            {"codec": "MP3 320k", "sample_peak_dbfs": 1.17, "true_peak_dbtp": 1.17, "samples_over_0_dbfs": codec_overs}
        ],
        "verdict": {
            "status": "caution",
            "positives": ["ok"],
            "warnings": [f"MP3 320k decode has {codec_overs} samples over 0 dBFS."],
            "codec_safety_pass": codec_overs == 0,
            "recommended_trim_db": 0.1,
            "safer_trim_db": 0.6,
            "estimated_lufs_after_safer_trim": -11.1,
            "estimated_true_peak_after_safer_trim": -1.5,
            "estimated_sample_peak_after_safer_trim": -0.34,
        },
    }


def comparison_item(name, true_peak, sample_peak, lufs, codec_pass=True):
    item = file_report(name)
    item["loudnorm"]["integrated_lufs"] = lufs
    item["loudnorm"]["true_peak_dbtp"] = true_peak
    item["sample_metrics"]["sample_peak_dbfs"] = sample_peak
    item["verdict"]["codec_safety_pass"] = codec_pass
    item["codec_stress_tests"] = [] if codec_pass else [
        {"codec": "MP3 320k", "sample_peak_dbfs": 0.2, "true_peak_dbtp": 0.2, "samples_over_0_dbfs": 3}
    ]
    return item


def test_json_report_shape_and_existing_fields():
    report = build_report([file_report()])
    item = report["files"][0]
    assert list(report) == ["files"]
    assert item["source_filename"] == "master.wav"
    assert "samples_over_0_dbfs" in item["sample_metrics"]
    assert "codec_stress_tests" in item
    assert "status" in item["verdict"]


def test_markdown_contains_expected_sections():
    markdown = to_markdown(build_report([file_report()]))
    assert "master.wav" in markdown
    assert "### Metrics" in markdown
    assert "### Codec Stress Test" in markdown
    assert "### Verdict" in markdown
    assert "### Recommended Action" in markdown


def test_codec_table_uses_terminal_friendly_headers():
    markdown = to_markdown(build_report([file_report()]))
    assert "| Codec | Decoded sample peak | Decoded true peak | Over samples |" in markdown
    assert "Sample Peak After Decode" not in markdown
    assert "True Peak After Decode" not in markdown
    assert "Over-0 Samples" not in markdown


def test_multiple_files_include_comparison():
    markdown = to_markdown(build_report([file_report("a.wav"), file_report("b.wav")]))
    assert "## Comparison" in markdown
    assert "a.wav" in markdown
    assert "b.wav" in markdown


def test_positive_peak_db_values_render_with_plus_sign():
    markdown = to_markdown(build_report([file_report()]))
    assert "+0.26 dBFS" in markdown
    assert "+1.17 dBFS" in markdown
    assert "+1.17 dBTP" in markdown


def test_crest_factor_renders_without_plus_sign():
    markdown = to_markdown(build_report([file_report()]))
    assert "| Crest factor | 13.26 dB |" in markdown
    assert "| Crest factor | +13.26 dB |" not in markdown


def test_trim_reduction_wording_does_not_render_as_positive_gain():
    markdown = to_markdown(build_report([file_report()]))
    assert "Recommended reduction to reach -1.0 dBTP | 0.1 dB" in markdown
    assert "Safer reduction to reach -1.5 dBTP | 0.6 dB" in markdown
    assert "Recommended trim to reach -1.0 dBTP" not in markdown
    assert "Safer trim to reach -1.5 dBTP" not in markdown
    assert "+0.6 dB" not in markdown
    assert "In Audacity or a DAW, apply Amplify/Gain of **-0.6 dB** to create the safer delivery version." in markdown


def test_summary_block_includes_status_codec_safety_and_trim_when_recommended():
    markdown = to_markdown(build_report([file_report()]))
    assert "**Status:** caution" in markdown
    assert "**Codec Safety:** PASS" in markdown
    assert "**Recommended safer trim:** -0.6 dB" in markdown


def test_codec_safety_fail_when_any_codec_decode_has_overs():
    markdown = to_markdown(build_report([file_report(codec_overs=3)]))
    assert "Codec Safety: **FAIL**" in markdown


def test_markdown_contains_near_ceiling_rows():
    markdown = to_markdown(build_report([file_report()]))
    assert "Samples above -0.1 dBFS" in markdown
    assert "Samples above -0.5 dBFS" in markdown
    assert "Samples above -1.0 dBFS" in markdown


def test_sample_counts_render_with_commas():
    markdown = to_markdown(build_report([file_report(codec_overs=1089)]))
    assert "26,466" in markdown
    assert "61,965" in markdown
    assert "1,089" in markdown
    assert "MP3 320k decode has 1,089 samples over 0 dBFS." in markdown


def test_summary_block_omits_trim_when_not_recommended():
    item = file_report()
    item["loudnorm"]["true_peak_dbtp"] = -1.2
    item["verdict"]["safer_trim_db"] = 0.0
    markdown = to_markdown(build_report([item]))
    assert "**Status:** caution" in markdown
    assert "**Codec Safety:** PASS" in markdown
    assert "**Recommended safer trim:**" not in markdown


def test_two_file_report_contains_delivery_comparison_summary():
    original = comparison_item("original.wav", -0.09, -0.10, -8.52, codec_pass=False)
    fixed = comparison_item("fixed.wav", -1.59, -1.60, -10.02, codec_pass=True)
    markdown = to_markdown(build_report([original, fixed]))
    assert "## Delivery Comparison Summary" in markdown
    assert "**Original:** original.wav" in markdown
    assert "**Fixed:** fixed.wav" in markdown
    assert "| Integrated loudness | -8.52 LUFS | -10.02 LUFS | -1.50 dB |" in markdown
    assert "| True peak | -0.09 dBTP | -1.59 dBTP | -1.50 dB |" in markdown
    assert "| Sample peak | -0.10 dBFS | -1.60 dBFS | -1.50 dB |" in markdown
    assert "| Codec Safety | FAIL | PASS | improved |" in markdown
    assert "Use the fixed delivery WAV." in markdown


def test_delivery_summary_recommends_reduce_more_when_fixed_codec_fails():
    original = comparison_item("original.wav", -0.09, -0.10, -8.52, codec_pass=False)
    fixed = comparison_item("fixed.wav", -1.59, -1.60, -10.02, codec_pass=False)
    markdown = to_markdown(build_report([original, fixed]))
    assert "| Codec Safety | FAIL | FAIL | unchanged |" in markdown
    assert "Reduce more and run the check again." in markdown


def test_delivery_summary_recommends_reduce_more_when_true_peak_still_hot():
    original = comparison_item("original.wav", -0.09, -0.10, -8.52, codec_pass=False)
    fixed = comparison_item("fixed.wav", -0.80, -0.81, -9.23, codec_pass=True)
    markdown = to_markdown(build_report([original, fixed]))
    assert "| Codec Safety | FAIL | PASS | improved |" in markdown
    assert "Reduce more to reach the -1.0 dBTP true-peak target." in markdown
