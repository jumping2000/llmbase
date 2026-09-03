# Email Ingestion

LLMBase can poll an IMAP mailbox and ingest incoming messages as wiki documents.
It runs as a background thread in the web app, checking the mailbox every minute.

## Enable email ingestion

Set these environment variables (see `.env.example`):

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLMBASE_MAIL_HOST` | ✅ | — | IMAP host. |
| `LLMBASE_MAIL_USER` | ✅ | — | Login user. |
| `LLMBASE_MAIL_PASSWORD` | ✅ | — | Login password. |
| `LLMBASE_MAIL_PORT` | — | `993` | IMAP port (SSL). |
| `LLMBASE_MAIL_FOLDER` | — | `INBOX` | Folder to poll. |
| `LLMBASE_MAIL_PROCESSED_FOLDER` | — | `Processed` | Folder to move processed messages to. |
| `LLMBASE_MAIL_POLL_MINUTES` | — | `1` | Poll interval in minutes (minimum 1). |
| `LLMBASE_MAIL_DEFAULT_DOMAIN` | — | `generale` | Domain for messages without a tag. |

Example:

```dotenv
LLMBASE_MAIL_HOST=imap.example.com
LLMBASE_MAIL_PORT=993
LLMBASE_MAIL_USER=wiki@example.com
LLMBASE_MAIL_PASSWORD=your-password
LLMBASE_MAIL_FOLDER=INBOX
LLMBASE_MAIL_PROCESSED_FOLDER=Processed
LLMBASE_MAIL_POLL_MINUTES=1
LLMBASE_MAIL_DEFAULT_DOMAIN=generale
```

## Domain routing via subject tag

Put a tag in the subject to route the message to a domain:

```
[lavoro] Report trimestrale
```

- A tag matching an existing domain routes the message to it.
- An unknown tag falls back to `generale` (logged with a warning).
- No tag uses `LLMBASE_MAIL_DEFAULT_DOMAIN`.

## What gets ingested

- The message body (plain text, or HTML converted to markdown) becomes a markdown document.
- PDF attachments are chunked and ingested as documents.
- Other attachments are ingested as files.
- A broken PDF attachment is skipped (the body is still ingested).

## Deduplication

After processing, the message is moved to `LLMBASE_MAIL_PROCESSED_FOLDER` and
marked deleted. If the move fails, it is marked seen as a fallback.
