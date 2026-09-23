# P4 — Collection freeze + annotation prep

**Status:** done  
**Coleta:** congelada (`environment/collection-freeze.json`)  
**Anotação humana:** bases criadas, **sem** mapping preenchido

## Artefatos

| Path | Papel |
| --- | --- |
| `environment/collection-freeze.json` | hashes + metadados da coleta |
| `collected-data/questions.csv` | bruto processado (**não** alterado) |
| `collected-data/prr-reference.csv` | catálogo de gaps por US |
| `collected-data/prr-gap-states.csv` | estados OPEN/ANSWERED por US×gap×condição |
| `collected-data/annotation-base.csv` | 269 perguntas + colunas de anotação vazias |
| `collected-data/annotation-blind.csv` | visão cega (sem condition/repetition) |
| `collected-data/annotation/evaluator-1.csv` | cópia independente inicial |
| `collected-data/annotation/evaluator-2.csv` | cópia independente inicial |
| `scripts/.../compare_evaluators.py` | gera `disagreements.csv` |
| `scripts/.../derive_classified_questions.py` | deriva `gap_state` **após** mapping humano |

## Scripts adaptados

`build_classification_base.py` deixou de usar o schema legado `questions_raw`/`classification_base` e passou a:

1. ler o PRR xlsx (via `prepare_materials.parse_prr_sheet`);
2. emitir `prr-reference.csv` + `prr-gap-states.csv`;
3. emitir `annotation-base.csv` / `annotation-blind.csv` / evaluators;
4. **não** preencher mapping automaticamente.
