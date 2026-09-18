# Auto-guarigione

L'auto-guarigione in LLMBase combina controlli lint, correzioni automatiche, cleanup e gestione dei duplicati.

## Strumenti principali

1. `llmbase lint check`
2. `llmbase lint deep`
3. `llmbase lint fix`
4. `llmbase lint normalize-tags`
5. `llmbase lint clean`
6. `llmbase lint dedup`
7. `llmbase lint orphans`
8. `llmbase lint heal`

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

## Articoli orfani

`llmbase lint orphans` elenca gli articoli senza link in entrata insieme agli articoli che potrebbero citarli, scelti per numero di tag in comune (nessuna chiamata LLM). Con `--fix` inserisce il wiki-link: una riga `See also:` in coda alla sezione `## English` e `Vedi anche:` in coda a `## Italiano`, accodando allo slug se la riga esiste già. Il cap `--max-links` (10 di default) limita quante scritture avvengono per run.

Le stesse azioni sono disponibili dalla pagina Health della UI — scegliendo a mano l'articolo sorgente oppure lasciandolo decidere al server — e via `GET /api/lint/orphans`, `POST /api/lint/orphans/link` e `POST /api/lint/orphans/fix`.

Questo fix resta **fuori** da `llmbase lint fix` / `lint heal`: collegare gli orfani riscrive articoli esistenti, e va innescato esplicitamente.

## Gestione dei duplicati

Il rilevamento dei duplicati si basa su sovrapposizioni come:
- similarità dello slug
- sovrapposizione dei tag
- similarità del contenuto

## Report di salute

`llmbase lint heal` persiste l'ultimo ciclo di salute in `wiki/_meta/health.json`.
Il loop di health-check del worker scrive lo stesso file e `GET /api/health` ne espone il contenuto corrente.
