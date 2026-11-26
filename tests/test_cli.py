import json
from typing import Any

import korto_archiver.cli as cli


class FakeClient:
    def __init__(self, responses: dict[bool, list[dict[str, Any]]]) -> None:
        self.responses = responses

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def list_messages(self, archived: bool) -> list[dict[str, Any]]:
        return [dict(item) for item in self.responses[archived]]

    def get_message(self, message_type: str, message_id: str | int) -> dict[str, Any]:
        return {"id": str(message_id), "type": message_type, "subject": "Test", "datetime": "25.11.2026 10:47"}

    def download(self, url: str) -> bytes:
        raise AssertionError("no attachments in test data")


def _run_lists(monkeypatch, tmp_path, responses: dict[bool, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    monkeypatch.setattr(cli, "KortoClient", lambda *a, **kw: FakeClient(responses))
    args = cli.build_parser().parse_args(["--output", str(tmp_path), "--cookie", "test-cookie"])
    assert cli.run(args) == 0
    path = tmp_path / "lists" / "messages.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _item(message_id: str, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "__typename": "Message",
        "datetime": "25.11.2026 10:47",
        "id": message_id,
        "is_archived": False,
        "type": "DISCUSSION",
        "subject": "Korstnapühkija",
    }
    item.update(extra)
    return item


def test_message_returned_by_both_views_is_saved_once(monkeypatch, tmp_path):
    shared = _item("867406")
    items = _run_lists(monkeypatch, tmp_path, {False: [shared], True: [dict(shared)]})

    assert items == [shared]


def test_all_messages_are_saved_in_one_list(monkeypatch, tmp_path):
    open_item = _item("111", is_archived=False)
    closed_item = _item("222", is_archived=True)
    items = _run_lists(
        monkeypatch,
        tmp_path,
        {False: [open_item, closed_item], True: [closed_item, open_item]},
    )

    assert [item["id"] for item in items] == ["111", "222"]
    assert [item["is_archived"] for item in items] == [False, True]


def test_missing_is_archived_falls_back_to_api_view(monkeypatch, tmp_path):
    item = _item("333")
    del item["is_archived"]
    items = _run_lists(monkeypatch, tmp_path, {False: [], True: [item]})

    assert items == [_item("333", is_archived=True)]
