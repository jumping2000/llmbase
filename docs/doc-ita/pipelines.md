# Pipeline

LLMBase usa pipeline semplici basate su file per fasi ripetibili e di lunga durata.

## Fasi tipiche

1. ingest
2. compile
3. taxonomy
4. lint
5. export

## Garanzie

- i nomi delle fasi vengono validati prima di toccare il filesystem
- le chiavi di fase vengono hashate prima di essere usate nei nomi file
- righe di log tronche o parzialmente scritte vengono tollerate durante la ricostruzione
- le operazioni di scrittura usano locking esplicito dove richiesto

## Guida pratica

- mantieni i nomi delle fasi ASCII e descrittivi
- tratta i log di fase come JSONL append-only
- preferisci ricostruire lo stato dalla cronologia dei log invece di fidarti dello stato in memoria dopo un crash
