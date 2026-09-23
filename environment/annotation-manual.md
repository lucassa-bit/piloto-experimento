# Manual de Anotação Humana — Experimento Piloto Spec Kit Clarify

**Versão:** `0.1-draft` (pré-calibração)  
**Status:** aberto a ajuste após o conjunto de calibração (~30 perguntas)  
**Congelamento:** após discussão da calibração → atribuir `1.0`, registrar SHA-256 em `environment/annotation-manual-freeze.json`, e só então iniciar a anotação completa.

Este manual define regras **operacionais**. Não altera o PRR. Não usa similaridade textual, embedding ou LLM como critério de correspondência.

---

## 0. Artefatos que o avaliador usa

| Artefato | Uso |
| --- | --- |
| `collected-data/annotation/calibration-evaluator-N.csv` | Calibração (30 itens) — **não** é anotação final |
| `collected-data/annotation/evaluator-N.csv` | Anotação completa (269) — só após freeze do manual v1.0 |
| `collected-data/prr-reference-blind.csv` | Catálogo de gaps da mesma User Story |
| `environment/annotation-manual.md` | Este protocolo |

**Privado (não entregar ao avaliador durante o mapping):**

- `collected-data/annotation/blind-id-map.csv`
- `collected-data/annotation/calibration-set.csv` (contém `question_uid`)
- `collected-data/prr-gap-states.csv`
- qualquer CSV com `condition` / `run_id`

### Blindagem obrigatória durante o mapping

O avaliador **não** deve consultar:

- `condition`, `repetition`, `run_id`, `question_order`
- estados `OPEN` / `ANSWERED` / `gap_state`
- categoria experimental da condição (C0, CL, CO, CD, CS, CT)
- `collected-data/prr-gap-states.csv`
- `importance` e `category` do PRR (usar apenas `prr-reference-blind.csv`)
- `blind-id-map.csv` / `question_uid` originais

O avaliador **pode** ver:

- `blind_item_id` (opaco, ex.: `B0042`)
- `user_story_id` (necessário para consultar gaps da US)
- `question_text_raw`

O avaliador **não** determina `OPEN`/`ANSWERED`. Esses estados serão derivados mecanicamente depois do mapping final.

---

## 1. Unidade original e identificador cego

**Unidade original** = uma pergunta extraída do Spec Kit, congelada em `collected-data/questions.csv`.

Identificador interno (pesquisa, **não** mostrado ao avaliador):

```text
question_uid = {run_id}_Q{order:02d}
exemplo: US02_C0_R1_Q01
```

Identificador apresentado ao avaliador (P5.1):

```text
blind_item_id = B0001 … B0269
```

A correspondência `blind_item_id ↔ question_uid` está apenas em `blind-id-map.csv` (privado).

A ordem das linhas nas folhas dos avaliadores é embaralhada **dentro de cada User Story** com `annotation_order_seed` (metadata de anotação). Essa seed **não** é usada em runs experimentais e **não** altera o experimento.

O campo `question_text_raw` é imutável. Nunca editar o texto original.

---

## 2. Unidade anotável

**Unidade anotável** = uma **necessidade informacional** independentemente respondível.

Casos:

| Situação | Linhas na folha | `segment_id` | `segment_text` |
| --- | --- | --- | --- |
| Uma necessidade | 1 linha | vazio | vazio (a necessidade = pergunta inteira) |
| Várias necessidades | N linhas (N≥2) | `S1`, `S2`, … | texto da necessidade daquele segmento |

Cada linha anotável preenche: `normalized_need`, `mapped_gap_id` (se MATCH), `mapping_status`, `notes` (opcional).

---

## 3. Quando segmentar

Segmentar **somente** quando a pergunta original contém **duas ou mais** necessidades que:

1. pedem evidências/informações **distintas**; e
2. poderiam ser respondidas de forma **independente** (uma resposta não esgota a outra).

**Não** segmentar quando:

- há apenas reformulação / detalhe da mesma necessidade;
- há exemplos ilustrativos da mesma lacuna;
- a “segunda parte” é condição ou restrição da primeira (ainda uma necessidade).

**Não** segmentar automaticamente (script/LLM). A decisão é humana.

### Como registrar segmentos

1. Manter o mesmo `blind_item_id` e o mesmo `question_text_raw` em todas as linhas do mesmo original.
2. Duplicar a linha para cada necessidade.
3. Preencher `segment_id` = `S1`, `S2`, …
4. Em `segment_text`, copiar/parafrasear **apenas** a parte correspondente (rastreável ao texto original).
5. Anotar cada segmento de forma independente.

Rastreabilidade composta (interna, após recomposição):

```text
{question_uid}_S1   ← via blind-id-map + segment_id
```

A pergunta original permanece recuperável via `blind_item_id` → map → `question_text_raw`.

---

## 4. `normalized_need`

Frase curta, em linguagem clara, que expressa **a informação que falta** (não a solução de implementação).

Regras:

- uma necessidade por linha anotável;
- não copiar automaticamente `[NEEDS CLARIFICATION]`;
- não incluir julgamento de qualidade do Spec Kit;
- não mencionar a condição experimental.

Exemplo:  
Original: *What maximum search radius should define “nearby” recycling facilities?*  
`normalized_need`: *Qual o raio máximo que define “nearby” para facilities?*

---

## 5. `MATCH`

Atribuir `mapping_status=MATCH` e preencher `mapped_gap_id` (ex.: `G03`) quando:

> **A mesma informação/evidência seria suficiente para responder à necessidade observada e ao gap de referência do PRR.**

Critério principal = **suficiência informacional compartilhada**, não similaridade de palavras.

Consequências:

- formulações diferentes podem ser MATCH;
- overlapping lexical sem a mesma evidência **não** é MATCH;
- o gap deve pertencer à **mesma** `user_story_id`.

---

## 6. `NO_REFERENCE_GAP`

Usar quando a necessidade é real/anotável, mas **nenhum** gap do PRR daquela US seria respondido pela mesma evidência.

Não forçar correspondência. Deixar `mapped_gap_id` vazio.

---

## 7. `REVIEW_REQUIRED`

Usar quando o avaliador **não consegue decidir com segurança** entre MATCH e NO_REFERENCE_GAP, ou entre dois gaps, ou sobre a segmentação.

Deixar `mapped_gap_id` vazio (ou anotar candidatos em `notes`, sem decidir).

---

## 8. Múltiplos gaps candidatos

Se dois ou mais gaps da mesma US poderiam servir:

1. Preferir o gap cuja `reference_information` (em `prr-reference-blind.csv`) é a evidência **mínima suficiente** para a necessidade.
2. Se ainda empatar → `REVIEW_REQUIRED` e listar candidatos em `notes` (`candidates: G02,G03`).
3. **Nunca** mapear a mesma linha a dois `mapped_gap_id`.

Se a pergunta tiver duas necessidades e cada uma casa com um gap diferente → **segmentar** e mapear cada segmento.

---

## 9. Correspondência parcial

Se a necessidade observada é **mais estreita** ou **mais ampla** que o gap:

| Caso | Decisão típica |
| --- | --- |
| Evidência do gap responde integralmente a necessidade | `MATCH` |
| Evidência do gap responde só uma parte, e sobra outra necessidade distinta | segmentar; mapear a parte coberta; o restante pode ser outro MATCH / NO_REFERENCE_GAP |
| Sobreposição vaga / evidência insuficiente para afirmar equivalência | `REVIEW_REQUIRED` |

Não “esticar” o gap para caber a pergunta.

---

## 10. Rastreabilidade

Preservar sempre:

| Campo | Papel |
| --- | --- |
| `blind_item_id` | chave opaca na folha do avaliador |
| `question_text_raw` | texto original intacto |
| `segment_id` / `segment_text` | decomposição humana (se houver) |
| `normalized_need` | interpretação explícita do anotador |
| `mapped_gap_id` + `mapping_status` | decisão de mapping |
| `notes` | ambiguidade, candidatos, justificativa breve |

Não apagar linhas de itens originais. Segmentação = linhas adicionais com o mesmo `blind_item_id`.

---

## 11. Procedimento humano (fluxo)

```text
Pergunta (question_text_raw)
   ↓
avaliar se contém uma ou várias necessidades
   ↓
segmentar, se necessário (S1, S2, …)
   ↓
escrever normalized_need (por segmento)
   ↓
comparar com gaps da mesma User Story (prr-reference-blind.csv)
   ↓
MATCH / NO_REFERENCE_GAP / REVIEW_REQUIRED
   ↓
se MATCH → indicar mapped_gap_id
```

Valores controlados de `mapping_status`:

- `MATCH`
- `NO_REFERENCE_GAP`
- `REVIEW_REQUIRED`

---

## 12. Calibração → congelamento do manual → anotação completa

A calibração **não** é anotação final do estudo.

```text
30 itens (calibration-evaluator-1/2)
   ↓
avaliadores 1 e 2 independentemente
   ↓
compare_evaluators.py  → métricas DIAGNÓSTICAS de calibração
   ↓
discussão apenas de regras / problemas do manual
   ↓
revisão de annotation-manual.md
   ↓
freeze annotation-manual v1.0 (+ hash)
   ↓
gerar folhas LIMPAS evaluator-1/2 (269) sob o manual v1.0
   ↓
ambos anotam as 269 perguntas novamente
```

Regras:

- as 30 perguntas da calibração **devem ser anotadas de novo** na fase completa;
- **não** copiar automaticamente mappings da calibração para a anotação final;
- métricas de calibração ≠ confiabilidade final do estudo.

---

## 13. Adjudicação (após anotação completa)

1. Comparar avaliadores com `compare_evaluators.py`.
2. Revisar `collected-data/annotation/disagreements.csv`.
3. Resolver divergências **humanamente** em um conjunto adjudicado final.
4. Somente depois executar `derive_classified_questions.py` para obter `gap_state` (OPEN|ANSWERED).

Não alterar anotações automaticamente com base em acordo/kappa.

---

## 14. Fora de escopo deste protocolo

- Gap Recall, Miss Rate, redundância, testes estatísticos de efeito de condição
- Preenchimento automático de mapping
- Alteração de `questions.csv`, baselines ou PRR
