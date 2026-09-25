# Anotação humana — pergunta → Gap ID

## O avaliador recebe

1. `evaluator-X.csv` (ou `calibration-evaluator-X.csv`)
2. `../prr-reference-blind.csv`
3. este README

## Para cada pergunta

1. Ler `question_text_raw`
2. Consultar gaps da mesma `user_story_id` em `prr-reference-blind.csv`
3. Preencher `mapped_gap_ids`: `G03` | `G03;G07` | `NONE` | `REVIEW`
4. `notes` opcional

## Regras

- Sem classificação automática / LLM / embeddings.
- Não alterar `blind_item_id`, `user_story_id`, `question_text_raw`.
- Não usar `blind-id-map.csv` (privado).
- Não inferir condição experimental nem OPEN/ANSWERED.

## Pesquisador

```bash
./scripts/bin/status.sh
./scripts/bin/validate-all.sh
```
