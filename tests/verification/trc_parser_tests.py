from pyhamilton.verification.parsers.trc_parser import extract_trc_guid, parse_trc_health


def test_trc_guid_extraction():
    assert (
        extract_trc_guid("STAR_OEM_noFan_3f1c2a_Trace.trc")
        == "3f1c2a"
    )
    assert (
        extract_trc_guid("123_STAR_OEM_noFan_abc-def_Trace.trc")
        == "abc-def"
    )


def test_trc_health_report(tmp_path):
    trace = tmp_path / "STAR_OEM_noFan_run-guid_Trace.trc"
    trace.write_text(
        "\n".join(
            [
                "HTTP polling noise",
                "Analyze method - complete",
                "Connection established to instrument",
                '{"command": "end", "id": "0x1"}',
            ]
        ),
        encoding="utf-8",
    )

    report = parse_trc_health(trace)

    assert report.guid == "run-guid"
    assert report.analyzed_ok is True
    assert report.connected is True
    assert report.reached_end is True
    assert report.errors == []
    assert len(report.raw_signal_lines) == 3


def test_trc_health_report_collects_errors(tmp_path):
    trace = tmp_path / "STAR_OEM_noFan_run-guid_Trace.trc"
    trace.write_text(
        "\n".join(
            [
                "Analyze method - error",
                "Main - error: script failed",
            ]
        ),
        encoding="utf-8",
    )

    report = parse_trc_health(trace)

    assert report.analyzed_ok is False
    assert report.errors == ["Analyze method - error", "Main - error: script failed"]


def test_trc_health_report_no_signal_lines(tmp_path):
    trace = tmp_path / "STAR_OEM_noFan_run-guid_Trace.trc"
    trace.write_text("polling\nbookkeeping", encoding="utf-8")

    report = parse_trc_health(trace)

    assert report.analyzed_ok is False
    assert report.connected is False
    assert report.reached_end is False
    assert report.errors == ["no signal lines in trace"]
    assert report.raw_signal_lines == []
