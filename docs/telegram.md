# Telegram Bot

LLMBase includes an optional Telegram bot that runs as a long-polling thread in
the same process as the web app. It lets you query the wiki and add documents
from Telegram.

## Enable the bot

Set these environment variables (see `.env.example`):

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLMBASE_TG_TOKEN` | ✅ | — | Bot token from [@BotFather](https://t.me/BotFather). When empty, the bot is disabled. |
| `LLMBASE_TG_ALLOWED_CHAT_IDS` | ✅ | — | Comma-separated chat ids allowed to talk to the bot. Any other chat is ignored. |
| `LLMBASE_TG_DEFAULT_DOMAIN` | — | `generale` | Default domain used for queries and uploads. |

Example:

```dotenv
LLMBASE_TG_TOKEN=123456:ABC-DEF...
LLMBASE_TG_ALLOWED_CHAT_IDS=123456789,987654321
LLMBASE_TG_DEFAULT_DOMAIN=generale
```

## Get the token and chat id

1. Talk to [@BotFather](https://t.me/BotFather), create a bot with `/newbot`, and copy the token.
2. Send any message to your bot, then find your chat id (e.g. via `https://api.telegram.org/bot<TOKEN>/getUpdates` or an ID bot).

## Commands

- `/ask <domanda>` — ask the wiki a question.
- `/cerca <testo>` — full-text search across the wiki.
- `/dominio <nome>` — switch the active domain for this chat (must be an existing domain).
- `/dominio` — show the current domain.
- `/aiuto` (or `/help`, `/start`) — show the command list.
- Send a PDF or any file — it is ingested into the current domain.
- Any other message is treated as a question.

## Domains

The bot scopes queries and uploads to a per-chat domain. It starts from
`LLMBASE_TG_DEFAULT_DOMAIN` and can be changed with `/dominio`. The `/dominio`
command only switches to **existing** domains (create them first from the web
UI, the API, or `kb_domains_create`); unknown names return an error listing the
available domains.

## Security

Only chat ids in `LLMBASE_TG_ALLOWED_CHAT_IDS` are served. Messages from other
chats are silently ignored.
