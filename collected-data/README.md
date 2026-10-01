# collected-data/

## Científico

```text
questions.csv                 # 269 perguntas observadas
reference/
  prr-reference.csv
  prr-reference-blind.csv     # consulta do avaliador
  prr-gap-states.csv          # OPEN/ANSWERED por condição
```

## Anotação humana

```text
annotation/
  evaluator-1.csv
  evaluator-2.csv
  calibration-evaluator-1.csv
  calibration-evaluator-2.csv
  disagreements.csv
  README.md
  private/                    # NÃO entregar ao avaliador
    blind-id-map.csv
    calibration-set.csv
    annotation-blind-metadata.json
```

## Auditoria

```text
audit/
  collection-integrity.json   # hashes oficiais
  run-summary.csv             # auditoria da coleta (não tabela analítica)
  outputs-check.csv           # auditoria técnica (congelado)
  baseline-generation.csv
  preflight-report.md         # opcional
  validation-report.md        # opcional
```

Não alterar bytes dos arquivos listados em `audit/collection-integrity.json`
sem atualizar esse registro.
