from __future__ import annotations

from typing import Any

import httpx

from .graphql import GET_MESSAGE_QUERY, GET_MESSAGES_QUERY


class KortoAPIError(RuntimeError):
    """Raised when Korto returns an HTTP or GraphQL error."""


class KortoClient:
    def __init__(
        self,
        cookie: str,
        apartment_id: str = "123456",
        api_url: str = "https://pro.korto.ee/api/",
        language: str = "et",
        timeout: float = 45.0,
    ) -> None:
        if not cookie.strip():
            raise ValueError("A Korto Cookie header value is required")
        self.apartment_id = str(apartment_id)
        self.api_url = api_url
        self.http = httpx.Client(
            timeout=timeout,
            headers={
                "Accept": "*/*",
                "Accept-Language": language,
                "Content-Type": "application/json",
                "Origin": "https://korto.ee",
                "Referer": "https://korto.ee/",
                "Cookie": cookie.strip(),
                "User-Agent": "korto-archiver/0.1.0",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "KortoClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _graphql(self, operation: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.http.post(
            self.api_url,
            json={"operationName": operation, "variables": variables, "query": query},
        )
        if response.is_error:
            raise KortoAPIError(f"Korto API returned HTTP {response.status_code} for {operation}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise KortoAPIError(f"Korto API returned non-JSON data for {operation}") from exc
        if payload.get("errors"):
            messages = "; ".join(str(item.get("message", item)) for item in payload["errors"])
            raise KortoAPIError(f"GraphQL error in {operation}: {messages}")
        if not isinstance(payload.get("data"), dict):
            raise KortoAPIError(f"Korto API response has no data for {operation}")
        return payload["data"]

    def list_messages(self, archived: bool) -> list[dict[str, Any]]:
        data = self._graphql(
            "GetMessagesData",
            GET_MESSAGES_QUERY,
            {"id": self.apartment_id, "archived": archived},
        )
        try:
            messages = data["viewer"]["apartment"]["association"]["messages"]
        except (KeyError, TypeError) as exc:
            raise KortoAPIError("GetMessagesData response did not contain the expected messages list") from exc
        if not isinstance(messages, list):
            raise KortoAPIError("GetMessagesData returned a non-list messages value")
        return messages

    def get_message(self, message_type: str, message_id: str | int) -> dict[str, Any]:
        data = self._graphql(
            "GetMessageData",
            GET_MESSAGE_QUERY,
            {"objectId": self.apartment_id, "type": message_type, "id": str(message_id)},
        )
        try:
            message = data["viewer"]["apartment"]["association"]["message"]
        except (KeyError, TypeError) as exc:
            raise KortoAPIError(f"GetMessageData response missing message {message_type}/{message_id}") from exc
        if not isinstance(message, dict):
            raise KortoAPIError(f"Korto returned no message for {message_type}/{message_id}")
        return message

    def download(self, url: str) -> bytes:
        # Use the same authenticated HTTP client/cookies as the GraphQL calls.
        response = self.http.get(url)
        if response.is_error:
            raise KortoAPIError(f"Attachment download failed with HTTP {response.status_code}")
        return response.content
