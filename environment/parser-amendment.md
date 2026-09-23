# Parser amendment — v2 (mechanical)

**Data:** 2026-09-23  
**parser_version:** `2`  
**Escopo:** segmentação de `last-message.txt` apenas — sem reexecução Codex, sem alteração experimental.

## Motivo

`US02_CL_R2` produziu 5 blocos `[NEEDS CLARIFICATION]` **sem** lista numerada.  
Com parser v1 isso virava `PARSE_REVIEW_REQUIRED` apesar de sucesso técnico.

## Regra (prioridade)

| Prioridade | Forma | Resultado |
| --- | --- | --- |
| A | Lista numerada `N.` / `N)` ou bullet `-`/`*` | `PARSE_OK` (inalterado) |
| B | Blocos independentes iniciados por `[NEEDS CLARIFICATION]` no começo da linha | `PARSE_OK` |
| C | Marker ambíguo / prosa / mid-line / múltiplos markers na mesma linha | `PARSE_REVIEW_REQUIRED` |

Delimitador semântico em B: o **marker**, não “split por linha em branco”.  
Perguntas multiline: linhas até o próximo marker-start pertencem ao bloco corrente.  
Texto preservado literalmente (marker + corpo + newlines internas).

## O que não mudou

- Fonte canônica: `attempt-N/last-message.txt`
- `stdout.jsonl` não substitui last-message
- 0 perguntas / `NO_CLARIFICATION_NEEDED` continua válido
- Sem mapping Gap ID / PRR
- Execuções brutas (`attempt-1`) intactas

## Fixture US02_CL_R2

Após v2: `PARSE_OK`, `question_count=5`, sem `attempt-2`.
