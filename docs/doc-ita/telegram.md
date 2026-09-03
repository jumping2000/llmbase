# Bot Telegram

LLMBase include un bot Telegram opzionale che gira come thread long-polling nello
stesso processo dell'app web. Permette di interrogare la wiki e aggiungere
documenti da Telegram.

## Abilitare il bot

Imposta queste variabili d'ambiente (vedi `.env.example`):

| Variabile | Richiesta | Default | Descrizione |
|---|---|---|---|
| `LLMBASE_TG_TOKEN` | ✅ | — | Token del bot da [@BotFather](https://t.me/BotFather). Se vuoto, il bot è disabilitato. |
| `LLMBASE_TG_ALLOWED_CHAT_IDS` | ✅ | — | Chat id separati da virgola autorizzati a parlare col bot. Le altre chat vengono ignorate. |
| `LLMBASE_TG_DEFAULT_DOMAIN` | — | `generale` | Dominio di default usato per query e caricamenti. |

Esempio:

```dotenv
LLMBASE_TG_TOKEN=123456:ABC-DEF...
LLMBASE_TG_ALLOWED_CHAT_IDS=123456789,987654321
LLMBASE_TG_DEFAULT_DOMAIN=generale
```

## Ottenere token e chat id

1. Parla con [@BotFather](https://t.me/BotFather), crea un bot con `/newbot` e copia il token.
2. Invia un messaggio qualsiasi al tuo bot, poi recupera il tuo chat id (ad es. via `https://api.telegram.org/bot<TOKEN>/getUpdates` o un bot ID).

## Comandi

- `/ask <domanda>` — fai una domanda alla wiki.
- `/cerca <testo>` — ricerca full-text nella wiki.
- `/dominio <nome>` — cambia il dominio attivo per questa chat (deve essere un dominio esistente).
- `/dominio` — mostra il dominio corrente.
- `/aiuto` (oppure `/help`, `/start`) — mostra l'elenco comandi.
- Invia un PDF o un file qualsiasi — viene ingerito nel dominio corrente.
- Qualsiasi altro messaggio viene trattato come domanda.

## Domini

Il bot circoscrive query e caricamenti a un dominio per-chat. Parte da
`LLMBASE_TG_DEFAULT_DOMAIN` e si può cambiare con `/dominio`. Il comando
`/dominio` passa solo a domini **esistenti** (creali prima dalla UI web, dall'API
o con `kb_domains_create`); nomi sconosciuti restituiscono un errore con l'elenco
dei domini disponibili.

## Sicurezza

Vengono servite solo le chat id presenti in `LLMBASE_TG_ALLOWED_CHAT_IDS`. I
messaggi dalle altre chat vengono ignorati silenziosamente.
