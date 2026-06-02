# Auto-guarigione

L'auto-guarigione in LLMBase combina controlli lint, correzioni automatiche, cleanup e gestione dei duplicati.

## Strumenti principali

1. `llmbase lint check`
2. `llmbase lint deep`
3. `llmbase lint fix`
4. `llmbase lint normalize-tags`
5. `llmbase lint clean`
6. `llmbase lint dedup`
7. `llmbase lint heal`

## Cosa viene rilevato

- problemi strutturali come `_index.md` o `index.json` mancanti
- link interrotti
- articoli orfani senza link in entrata
- metadati mancanti come titolo, summary o tag
- tag sporchi generati da output LLM malformato
- concetti duplicati
- articoli vuoti o segnaposto
- articoli non categorizzati

`llmbase lint deep` esegue una review separata basata su LLM, focalizzata su incoerenze, dati mancanti, connessioni deboli e candidati per nuovi articoli.

## Gestione dei duplicati

Il rilevamento dei duplicati si basa su sovrapposizioni come:
- similarità dello slug
- sovrapposizione dei tag
- similarità del contenuto

## Report di salute

`llmbase lint heal` persiste l'ultimo ciclo di salute in `wiki/_meta/health.json`.
Il loop di health-check del worker scrive lo stesso file e `GET /api/health` ne espone il contenuto corrente.
