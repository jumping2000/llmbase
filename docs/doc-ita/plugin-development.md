# Sviluppo plugin

LLMBase supporta ancora punti di estensione in stile plugin, ma il repository non distribuisce più plugin corpus-specific incorporati.

## Plugin di riferimento

Un plugin di riferimento definisce tipicamente:
- `PLUGIN_ID`
- `PLUGIN_NAME`
- `get_source_url(source: dict) -> str`

Usa per default nomi di visualizzazione in inglese e italiano.

## Plugin di operazioni

Se vuoi che una funzionalità appaia in CLI, HTTP e MCP, registrala tramite `llmwiki.operations.register`.

## Fonti di apprendimento

Le custom learn sources possono essere registrate downstream.
Il repository predefinito non assume più alcuna fonte esterna incorporata.
