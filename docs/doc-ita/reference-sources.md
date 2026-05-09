# Fonti di riferimento

Gli articoli possono includere metadati di fonte strutturati. Le citazioni delle fonti vengono unite ed esposte tramite API web e superfici di export.

## Esempio di blocco fonte

```yaml
sources:
  - plugin: docs
    url: https://example.com/spec
    title: Example Specification
```

## Come viene usato

- le pagine articolo possono mostrare citazioni
- gli export includono `sources`
- i plugin di riferimento downstream possono costruire URL canonici dai metadati salvati

## Deduplicazione

Quando piu documenti raw contribuiscono lo stesso record di fonte, l'elenco delle fonti viene unito invece di essere duplicato.
