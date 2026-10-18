from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .archive import message_key, write_email, write_json
from .client import KortoAPIError, KortoClient


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "messages": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read manifest {path}: {exc}") from exc
    if not isinstance(data.get("messages"), dict):
        raise RuntimeError(f"Manifest {path} has an invalid messages field")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive messages from Korto to JSON, EML, and attachment files.")
    parser.add_argument("--output", type=Path, default=Path("archive"), help="Archive directory (default: %(default)s)")
    parser.add_argument("--apartment-id", default=os.environ.get("KORTO_APARTMENT_ID", "123456"))
    parser.add_argument("--api-url", default=os.environ.get("KORTO_API_URL", "https://pro.korto.ee/api/"))
    parser.add_argument("--cookie", default=os.environ.get("KORTO_COOKIE"), help="Cookie header value; prefer KORTO_COOKIE environment variable")
    parser.add_argument("--refresh", action="store_true", help="Refetch and rewrite all known messages")
    parser.add_argument("--version", action="version", version=f"korto-archiver {__version__}")
    return parser


def run(args: argparse.Namespace) -> int:
    if not args.cookie:
        print("error: set KORTO_COOKIE to the Cookie header value copied from Chrome DevTools", file=sys.stderr)
        return 2

    output: Path = args.output
    messages_dir = output / "messages"
    attachments_dir = output / "attachments"
    manifest_path = output / "manifest.json"
    manifest = _read_manifest(manifest_path)
    manifest.setdefault("version", 1)
    manifest.setdefault("messages", {})
    if manifest.get("apartment_id") is not None and str(manifest["apartment_id"]) != str(args.apartment_id):
        raise RuntimeError("This archive belongs to another apartment; use a different --output directory")
    manifest["apartment_id"] = str(args.apartment_id)

    with KortoClient(args.cookie, apartment_id=args.apartment_id, api_url=args.api_url) as client:
        # Fetch both categories and merge by type + ID in case the server's views overlap.
        listed: dict[tuple[str, str], dict[str, Any]] = {}
        for archived in (False, True):
            items = client.list_messages(archived=archived)
            write_json(output / "lists" / f"messages-archived-{str(archived).lower()}.json", items)
            print(f"Listed {len(items)} {'archived' if archived else 'non-archived'} messages")
            for item in items:
                if item.get("id") is None or not item.get("type"):
                    print(f"warning: skipping list item without id/type: {item!r}", file=sys.stderr)
                    continue
                listed[(str(item["type"]), str(item["id"]))] = item

        print(f"Found {len(listed)} unique message IDs")
        new_count = updated_count = skipped_count = 0
        for (message_type, message_id), list_item in sorted(
            listed.items(), key=lambda pair: (str(pair[1].get("datetime") or ""), pair[0][0], pair[0][1])
        ):
            key = message_key(message_type, message_id)
            folder = messages_dir / key
            detail_path = folder / "message.json"
            record = manifest["messages"].get(key)
            if record and detail_path.exists() and not args.refresh:
                skipped_count += 1
                continue

            try:
                detail = client.get_message(message_type, message_id)
                write_json(detail_path, detail)
                attachment_records = write_email(
                    message=detail,
                    email_path=folder / "message.eml",
                    attachment_dir=attachments_dir,
                    download=client.download,
                    message_type=message_type,
                    message_id=message_id,
                )
                parent_mid = f"<korto-{message_type.lower()}-{message_id}@korto-archive.local>"
                reply_records: list[dict[str, Any]] = []
                for index, reply in enumerate(detail.get("replies") or [], start=1):
                    reply_id = str(reply.get("id") or f"{message_id}-reply-{index}")
                    reply_folder = folder / "replies"
                    reply_for_email = dict(reply)
                    reply_for_email["subject"] = detail.get("subject") or "(No subject)"
                    reply_for_email["to"] = reply.get("new_to") or detail.get("to") or "Korto residents"
                    reply_attachments = write_email(
                        message=reply_for_email,
                        email_path=reply_folder / f"{index:03d}-{message_key('reply', reply_id)}.eml",
                        attachment_dir=attachments_dir,
                        download=client.download,
                        message_type=f"{message_type}-reply",
                        message_id=reply_id,
                        parent_message_id=parent_mid,
                        reply_index=index,
                    )
                    reply_records.append({"id": reply_id, "datetime": reply.get("datetime"), "from": reply.get("from"), "attachments": reply_attachments})

                manifest["messages"][key] = {
                    "id": message_id,
                    "type": message_type,
                    "subject": detail.get("subject") or list_item.get("subject"),
                    "datetime": detail.get("datetime") or list_item.get("datetime"),
                    "is_archived": detail.get("is_archived", list_item.get("is_archived")),
                    "edit_datetime": detail.get("edit_datetime"),
                    "message_json": str(detail_path),
                    "email": str(folder / "message.eml"),
                    "attachments": attachment_records,
                    "replies": reply_records,
                    "poll_count": len(detail.get("polls") or []),
                }
                if record:
                    updated_count += 1
                else:
                    new_count += 1
                write_json(manifest_path, manifest)
                print(f"Archived {message_type}/{message_id}: {detail.get('subject') or '(no subject)'}")
            except (KortoAPIError, OSError, RuntimeError, ValueError) as exc:
                print(f"error: failed to archive {message_type}/{message_id}: {exc}", file=sys.stderr)
                # Continue so one inaccessible message does not prevent the rest of the archive.

    write_json(manifest_path, manifest)
    print(f"Done. New: {new_count}; refreshed: {updated_count}; already archived locally: {skipped_count}")
    print(f"Archive directory: {output.resolve()}")
    if skipped_count:
        print("Note: known messages are skipped unless --refresh is supplied; edits to existing messages are not detected automatically.")
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        code = run(args)
    except (KortoAPIError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = 1
    raise SystemExit(code)
