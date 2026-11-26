import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from korto_archiver.archive import html_to_text, message_key, parse_korto_datetime, write_email


def test_html_to_text_handles_breaks_and_entities():
    assert html_to_text("Esimene<br />Teine &amp; kolmas") == "Esimene\nTeine & kolmas"


def test_parse_korto_datetime_uses_tallinn_timezone():
    parsed = parse_korto_datetime("06.05.2026 13:21")
    assert parsed.year == 2026
    assert parsed.month == 5
    assert parsed.hour == 13
    assert parsed.tzinfo is not None


def test_message_key_is_filesystem_safe():
    assert message_key("DISCUSSION", "54321") == "discussion-54321"


def test_write_email_includes_html_and_attachment(tmp_path: Path):
    msg = {
        "from": "Mari Maasikas",
        "to": "All residents",
        "datetime": "06.05.2026 13:21",
        "subject": "Teisipäev on uus reede",
        "body": "Teade<br />Teine rida",
        "attachments": [{"id": "7", "filename": "notice.txt", "download_url": "https://example.invalid/file"}],
    }
    path = tmp_path / "message.eml"
    write_email(
        message=msg,
        email_path=path,
        attachment_dir=tmp_path / "attachments",
        download=lambda _: b"attachment contents",
        message_type="DISCUSSION",
        message_id="54321",
    )
    parsed = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    assert parsed["Subject"] == "Teisipäev on uus reede"
    assert "Mari Maasikas" in parsed["From"]
    assert parsed.get_body(preferencelist=("plain",)).get_content().strip() == "Teade\r\nTeine rida"
    attachments = list(parsed.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "notice.txt"
    assert attachments[0].get_content() == "attachment contents"


def _sample_message() -> dict[str, Any]:
    return {
        "from": "Mari Maasikas",
        "to": "All residents",
        "datetime": "06.05.2026 13:21",
        "subject": "Teisipäev on uus reede",
        "body": "Teade<br />Teine rida",
        "attachments": [{"id": "7", "filename": "notice.txt", "download_url": "https://example.invalid/file"}],
    }


def _write(msg: dict[str, Any], path: Path, tmp_path: Path, **overrides: Any) -> Path:
    options: dict[str, Any] = {
        "message": msg,
        "email_path": path,
        "attachment_dir": tmp_path / "attachments",
        "download": lambda _: b"attachment contents",
        "message_type": "DISCUSSION",
        "message_id": "54321",
    }
    options.update(overrides)
    write_email(**options)
    return path


def _boundaries(path: Path) -> list[str]:
    parsed = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    return [part.get_boundary() for part in parsed.walk() if part.is_multipart()]


def test_write_email_is_deterministic(tmp_path: Path):
    msg = _sample_message()
    first = _write(msg, tmp_path / "first.eml", tmp_path)
    second = _write(msg, tmp_path / "second.eml", tmp_path)
    assert first.read_bytes() == second.read_bytes()


def test_write_email_boundaries_are_stable_and_consistent(tmp_path: Path):
    path = _write(_sample_message(), tmp_path / "message.eml", tmp_path)
    raw = path.read_bytes().decode("ascii")
    boundaries = _boundaries(path)
    assert len(boundaries) == 2  # multipart/mixed wrapping multipart/alternative
    for boundary in boundaries:
        assert re.fullmatch(r"={15}[0-9]{19}==", boundary)
        assert f'boundary="{boundary}"' in raw
        assert f"--{boundary}" in raw
        assert f"--{boundary}--" in raw

    again = _write(_sample_message(), tmp_path / "again.eml", tmp_path)
    assert _boundaries(again) == boundaries


def test_write_email_boundaries_depend_on_message_identity(tmp_path: Path):
    msg = _sample_message()
    first = _boundaries(_write(msg, tmp_path / "first.eml", tmp_path))
    second = _boundaries(_write(msg, tmp_path / "second.eml", tmp_path, message_id="54322"))
    assert first != second
