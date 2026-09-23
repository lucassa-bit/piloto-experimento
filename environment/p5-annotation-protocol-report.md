# P5 — Protocolo de anotação humana (prep)

**Status:** done (pré-calibração)  
**Manual:** `environment/annotation-manual.md` versão `0.1-draft`  
**Congelamento do manual:** somente após discussão da calibração (`1.0` + `annotation-manual-freeze.json`)

## Artefatos

| Path | Papel |
| --- | --- |
| `environment/annotation-manual.md` | regras operacionais |
| `collected-data/prr-reference-blind.csv` | catálogo cego (sem importance/category) |
| `collected-data/prr-reference.csv` | catálogo completo (preservado) |
| `collected-data/annotation/calibration-set.csv` | 30 `question_uid` |
| `collected-data/annotation/calibration-evaluator-{1,2}.csv` | folhas de calibração |
| `collected-data/annotation/evaluator-{1,2}.csv` | folhas completas (269), vazias |
| `scripts/.../prepare_annotation_protocol.py` | seleção determinística + exports |
| `scripts/.../compare_evaluators.py` | acordo bruto + kappa + disagreements |

## Não feito (por design)

- anotação humana
- derive `classified-questions.csv`
- estatística experimental (Gap Recall etc.)
- alteração de PRR / `questions.csv`
