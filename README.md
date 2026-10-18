# Korto Archiver

Archiver for messages in Korto's resident portal.

A first-pass Python archiver for messages in Korto's resident portal. It uses the same cookie-authenticated GraphQL API observed in the web app and stores message details, polls, replies, attachments, and RFC 5322 `.eml` files locally. It is intentionally read-only: it does not post, edit, vote, or delete anything in Korto.

## What it saves

```text
archive/
├── lists/
│   ├── messages-archived-false.json
│   └── messages-archived-true.json
├── messages/
│   └── discussion-54321/
│       ├── message.json       # full GraphQL detail response
│       ├── message.eml        # root message, with MIME attachments
│       └── replies/           # one .eml per reply
├── attachments/               # downloaded original files
└── manifest.json              # index of archived messages
```

Poll data is preserved in each `message.json`. Replies are saved as separate `.eml` files with `In-Reply-To` and `References` headers pointing to the root message. Email clients may or may not thread imported messages the way you expect; Gmail import behavior should be tested separately.

## Requirements

- Python 3.10 or newer
- A currently authenticated Korto browser session

## Install

From this project directory, preferably in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

## Get the cookie from Chrome

1. Sign in to Korto in Chrome.
2. Open DevTools → **Network**, select a GraphQL request to `https://pro.korto.ee/api/`.
3. In **Request Headers**, copy the value of the `Cookie` header. Do not include the text `Cookie:` itself.
4. Set it in the shell where you will run the archiver:

```sh
export KORTO_COOKIE='cookieconsent_status_v2=allow; PHPSESSID=...; auth_token=...'
export KORTO_APARTMENT_ID=123456
```

Treat this cookie string like a password. Do not commit it, paste it into issues, or include it in logs. The `.gitignore` excludes `.env` and archive data, but environment variables are preferred so the cookie never needs to be written to a file. If a real cookie has been exposed, sign out/revoke the session and copy a fresh one.

## Run

Fetch both archived and non-archived lists, deduplicate them by `(type, id)`, and archive each message not already present locally:

```sh
korto-archive --output archive
```

Equivalent module invocation:

```sh
python -m korto_archiver --output archive
```

To re-fetch known messages and update their saved details and emails:

```sh
korto-archive --output archive --refresh
```

You can override the apartment ID and endpoint with `--apartment-id` and `--api-url`, or set `KORTO_APARTMENT_ID` and `KORTO_API_URL` environment variables.

The script prints counts and per-message progress, but never prints the cookie. Failed messages are reported and the run continues. HTTP/GraphQL errors are raised clearly. A run can be repeated safely; without `--refresh`, existing message folders are skipped. That also means edits to an already archived message are not detected automatically unless you run with `--refresh`.

## Tests

```sh
pytest
```

## Current limitations / next refinements

- The `GetMessagesData` query has no explicit pagination fields in the request captured so far. The script saves each list response verbatim so completeness can be checked against Korto's UI.
- This first version assumes the observed GraphQL response shape remains stable.
- Attachment URLs are used as returned by GraphQL and downloaded with the same cookie-authenticated HTTP session.
- Message date strings such as `06.05.2026 13:21` are interpreted in `Europe/Tallinn`.
- Polls are preserved as JSON but not yet rendered into the email body.
- Gmail import and label assignment are intentionally out of scope for this initial fetcher.
