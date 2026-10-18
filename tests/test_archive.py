from email import policy
from email.parser import BytesParser
from pathlib import Path

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
