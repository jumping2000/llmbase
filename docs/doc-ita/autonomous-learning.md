# Apprendimento autonomo

Il worker puo far avanzare la base di conoscenza senza supervisione manuale, ma la fonte integrata predefinita e volutamente semplice.

## Comportamento predefinito

- `worker.learn_source` ha come default `seed_urls`
- la fonte integrata legge `wiki/_meta/seed-urls.json`
- progresso di ingest e stato dei retry sono salvati in `wiki/_meta/worker-seeds-state.json`
- le fonti remote incorporate non vengono piu distribuite

## Ciclo tipico

1. Nuovo materiale grezzo viene ingerito in `raw/`.
2. Il worker compila il nuovo materiale in `wiki/concepts/`.
3. Tassonomia e introduzioni guidate possono essere aggiornate.
4. Workflow di lint e cleanup possono mantenere la KB in salute.

## Esempio di configurazione

```yaml
worker:
  enabled: true
  learn_source: seed_urls
```

Nel deployment Docker Compose il worker gira nel servizio dedicato `llmbase-worker` invece che dentro il processo web Gunicorn.
Quando `worker.enabled` e `false`, quel servizio resta inattivo e fa polling della configurazione invece di riavviarsi in loop.

Esempio di file seed:

```json
{
  "urls": [
    "https://example.com/article-1",
    "https://example.com/article-2"
  ]
}
```

## Estendere le fonti di apprendimento

Se ti serve apprendimento autonomo da un sistema upstream personalizzato, registra una custom learn source in Python e indirizza il worker verso quella fonte.
Il repository non assume piu alcuna fonte esterna incorporata.
