# Ingestione Email

LLMBase può interrogare una casella IMAP e ingerire i messaggi in arrivo come
documenti wiki. Gira come thread in background nell'app web, controllando la
casella ogni minuto.

## Abilitare l'ingestione email

Imposta queste variabili d'ambiente (vedi `.env.example`):

| Variabile | Richiesta | Default | Descrizione |
|---|---|---|---|
| `LLMBASE_MAIL_HOST` | ✅ | — | Host IMAP. |
| `LLMBASE_MAIL_USER` | ✅ | — | Utente di login. |
| `LLMBASE_MAIL_PASSWORD` | ✅ | — | Password di login. |
| `LLMBASE_MAIL_PORT` | — | `993` | Porta IMAP (SSL). |
| `LLMBASE_MAIL_FOLDER` | — | `INBOX` | Cartella da interrogare. |
| `LLMBASE_MAIL_PROCESSED_FOLDER` | — | `Processed` | Cartella dove spostare i messaggi processati. |
| `LLMBASE_MAIL_POLL_MINUTES` | — | `1` | Intervallo di polling in minuti (minimo 1). |
| `LLMBASE_MAIL_DEFAULT_DOMAIN` | — | `generale` | Dominio per i messaggi senza tag. |

Esempio:

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

## Routing del dominio tramite tag nell'oggetto

Metti un tag nell'oggetto per indirizzare il messaggio a un dominio:

```
[lavoro] Report trimestrale
```

- Un tag che corrisponde a un dominio esistente indirizza il messaggio a quel dominio.
- Un tag sconosciuto ricade su `generale` (con warning nei log).
- Senza tag viene usato `LLMBASE_MAIL_DEFAULT_DOMAIN`.

## Cosa viene ingerito

- Il corpo del messaggio (testo semplice, o HTML convertito in markdown) diventa un documento markdown.
- Gli allegati PDF vengono spezzati in chunk e ingeriti come documenti.
- Gli altri allegati vengono ingeriti come file.
- Un allegato PDF corrotto viene saltato (il corpo viene comunque ingerito).

## Deduplicazione

Dopo l'elaborazione, il messaggio viene spostato in `LLMBASE_MAIL_PROCESSED_FOLDER`
e marcato come eliminato. Se lo spostamento fallisce, come fallback viene marcato
come letto.
