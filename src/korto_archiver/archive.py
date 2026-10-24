from __future__ import annotations

import html
import json
import mimetypes
import re
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TALLINN = ZoneInfo("Europe/Tallinn")


class _PlainTextHTML(HTMLParser):
    BLOCKS = {"address", "article", "blockquote", "div", "footer", "h1", "h2", "h3", "h4", "li", "p", "section", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCKS or tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str | None) -> str:
    parser = _PlainTextHTML()
    parser.feed(value or "")
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_korto_datetime(value: str | None) -> datetime:
    if value:
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=TALLINN)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=TALLINN) if parsed.tzinfo is None else parsed
        except ValueError:
            pass
    return datetime.now(TALLINN)


def safe_name(value: str) -> str:
    value = re.sub(r"[^\w.() -]+", "_", value, flags=re.UNICODE).strip(" .")
    return value or "attachment.bin"


def message_key(message_type: str, message_id: str | int) -> str:
    return f"{safe_name(str(message_type).lower())}-{safe_name(str(message_id))}"


def _set_common_headers(
    email: EmailMessage,
    *,
    sender: str,
    recipient: str,
    subject: str,
    date_value: str | None,
    message_id: str,
) -> None:
    email["From"] = sender or "Korto resident message"
    email["To"] = recipient or "Korto residents"
    email["Subject"] = subject or "(No subject)"
    email["Date"] = format_datetime(parse_korto_datetime(date_value))
    email["Message-ID"] = message_id
    email["X-Korto-Archived"] = "true"


def _add_attachments(
    email: EmailMessage,
    attachments: list[dict[str, Any]],
    attachment_dir: Path,
    download: Any,
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    attachment_dir.mkdir(parents=True, exist_ok=True)
    for item in attachments or []:
        url = item.get("download_url")
        filename = safe_name(str(item.get("filename") or f"attachment-{item.get('id', 'unknown')}"))
        if not url:
            raise RuntimeError(f"Attachment {filename!r} has no download_url")
        content = download(url)
        prefix = safe_name(str(item.get("id") or "file"))
        path = attachment_dir / f"{prefix}-{filename}"
        path.write_bytes(content)
        mime, _ = mimetypes.guess_type(filename)
        maintype, subtype = (mime.split("/", 1) if mime else ("application", "octet-stream"))
        email.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
        saved.append({"id": item.get("id"), "filename": filename, "path": str(path), "size": len(content)})
    return saved


def write_email(
    *,
    message: dict[str, Any],
    email_path: Path,
    attachment_dir: Path,
    download: Any,
    message_type: str,
    message_id: str | int,
    parent_message_id: str | None = None,
    reply_index: int | None = None,
) -> list[dict[str, Any]]:
    sender = str(message.get("from") or "Korto")
    recipient = str(message.get("to") or "Korto residents")
    root_subject = str(message.get("subject") or "(No subject)")
    subject = f"Re: {root_subject}" if reply_index is not None else root_subject
    email = EmailMessage(policy=policy.SMTP)
    stable_id = f"<korto-{safe_name(message_type.lower())}-{safe_name(str(message_id))}@korto-archive.local>"
    _set_common_headers(
        email,
        sender=sender,
        recipient=recipient,
        subject=subject,
        date_value=message.get("datetime"),
        message_id=stable_id,
    )
    if parent_message_id:
        email["In-Reply-To"] = parent_message_id
        email["References"] = parent_message_id
    email["X-Korto-Type"] = str(message_type)
    email["X-Korto-Message-ID"] = str(message_id)

    body_html = str(message.get("body") or "")
    plain = html_to_text(body_html) or "(No message body)"
    email.set_content(plain)
    email.add_alternative(body_html or "<p>(No message body)</p>", subtype="html")
    email_path.parent.mkdir(parents=True, exist_ok=True)
    saved = _add_attachments(email, message.get("attachments") or [], attachment_dir, download)
    email_path.write_bytes(email.as_bytes())
    return saved


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
