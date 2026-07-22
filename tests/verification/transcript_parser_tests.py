import pytest

from pyhamilton.verification.models import EventCategory
from pyhamilton.verification.parsers.transcript_parser import parse_run_transcript


def test_run_transcript_odtc_extraction():
    events = parse_run_transcript("Simulating ODTC protocol 'TAK004_First-Strand_cDNA_Synthesis'")

    assert len(events) == 1
    assert events[0].category == EventCategory.MODULE_ACTION
    assert events[0].action == "run_program"
    assert events[0].resources == ["ODTC"]
    assert events[0].metadata["method_name"] == "TAK004_First-Strand_cDNA_Synthesis"


def test_run_transcript_wait_extraction():
    events = parse_run_transcript("skipping 30 s wait")

    assert len(events) == 1
    assert events[0].category == EventCategory.WAIT
    assert events[0].metadata["duration_s"] == 30


def test_run_transcript_step_extraction():
    events = parse_run_transcript("Executing step: transfer_plate")

    assert len(events) == 1
    assert events[0].category == EventCategory.OTHER
    assert events[0].metadata["step"] == "transfer_plate"


def test_run_transcript_ordered_by_line_number():
    events = parse_run_transcript(
        "\n".join(
            [
                "noise",
                "Executing step: setup",
                "skipping 10 s wait",
                'Simulating ODTC status for "PCR_1"',
            ]
        )
    )

    assert [event.sequence for event in events] == [0, 1, 2]
    assert [event.metadata["line_number"] for event in events] == [2, 3, 4]


def test_run_transcript_returns_empty_for_no_matches():
    assert parse_run_transcript("ordinary output") == []


def test_run_transcript_reads_file(tmp_path):
    transcript = tmp_path / "run_transcript.log"
    transcript.write_text("skipping 5 s wait", encoding="utf-8")

    events = parse_run_transcript(transcript)

    assert events[0].metadata["duration_s"] == 5


def test_run_transcript_missing_path_raises():
    with pytest.raises(FileNotFoundError):
        parse_run_transcript("missing/run_transcript.log")
