# Analysis — Spec Kit clarification pilot

Camada de **análise estatística descritiva/exploratória** do experimento piloto de dependência de contexto em clarificação de requisitos com LLMs.

> Este estudo é um piloto metodológico. As estatísticas são descritivas e exploratórias; não devem ser interpretadas como estimativas generalizáveis do comportamento de LLMs ou do Spec Kit.

## 1. Inputs necessários

Somente artefatos finais em `collected-data/` (não altera dados experimentais, PRR nem anotações):

| Artefato | Caminho |
|----------|---------|
| Perguntas | `collected-data/questions.csv` |
| Avaliador 1 | `collected-data/annotation/evaluator-1.csv` |
| Avaliador 2 | `collected-data/annotation/evaluator-2.csv` |
| Adjudicação | `collected-data/annotation/disagreements.csv` (`final_gap_ids`) |
| Blind map | `collected-data/annotation/private/blind-id-map.csv` |
| PRR gaps | `collected-data/reference/prr-reference.csv` |
| Estados OPEN/ANSWERED | `collected-data/reference/prr-gap-states.csv` |
| Runs | `collected-data/audit/run-summary.csv` |

**Pré-requisito:** mapeamento humano completo. Sem `mapped_gap_ids` preenchidos (e adjudicação quando houver divergência), a análise **para** com erro claro — não inventa mappings.

## 2. Como executar

```bash
# Dependências
pip install -r requirements.txt

# Testes unitários (fixtures sintéticas)
PYTHONPATH=. pytest analysis/tests -q

# Pipeline reproduzível (executa o notebook)
./scripts/bin/run-analysis.sh

# Ou só o pipeline Python
PYTHONPATH=. python -m analysis.src.pipeline

# Interativo
jupyter notebook analysis/notebooks/pilot-analysis.ipynb
```

`ANALYSIS_SEED = 20260930` aplica-se apenas a operações estocásticas (bootstrap). Métricas determinísticas não dependem da seed.

## 3. Arquivos derivados

```
analysis/outputs/
├── derived/
│   ├── final-question-mapping.csv   # 1 linha / pergunta
│   ├── question-gap-mapping.csv     # 1 linha / pergunta × gap
│   └── gap-run-matrix.csv           # unidade Gap × execução
├── tables/                          # CSVs exportáveis
└── figures/                         # PNG 300 dpi + PDF
```

## 4. Métricas

| Métrica | Definição | Notas |
|---------|-----------|--------|
| **Gap Recall** | recognized OPEN / total OPEN | Mesma unidade (tipicamente Gap×Run) |
| **Miss Rate** | 1 − Gap Recall | Não é descoberta independente |
| **Requery Rate** | recognized ANSWERED / total ANSWERED | “Reconsulta”; não rotular automaticamente como erro |
| **Occurrence Rate** | ocorrências com recognized=1 / n repetições observadas | Escala com n arbitrário de repetições |
| **NONE rate** | perguntas NONE / total | Só quantitativo neste notebook |
| **Viabilidade** | cobertura de mapping, burden de adjudicação | Diagnóstico do procedimento — **sem** Cohen’s κ neste piloto |

Condição sem gaps OPEN → Gap Recall = **N/A** (nunca 0).

## 5. Unidade analítica principal

A unidade principal **não** é a pergunta. É:

**Gap × execução** (ex.: `US02_C0_R1 × G03`)

No piloto: 42 gaps × 6 condições × 3 repetições = **756** linhas em `gap-run-matrix.csv`.

`recognized = 1` se ≥1 pergunta daquela execução foi mapeada ao gap; `question_count_for_gap` conta quantas.

Mapping final:

- E1 == E2 → `DIRECT_AGREEMENT`
- Divergência → exclusivamente `final_gap_ids` da adjudicação humana (`ADJUDICATION`)
- Nunca escolher entre avaliadores automaticamente
- Sem mapping semântico pergunta→gap automático

## 6. Limitações do piloto

- n=4 User Stories; não generalizar.
- Avaliador 2 assistivo/ChatGPT → divergência só como diagnóstico de procedimento.
- Bootstrap clusterizado preparado, mas CIs com poucos clusters são marcados como inadequados/exploratórios.
- Testes inferenciais confirmatórios e GLMM de efeitos mistos estão **desabilitados** / marcados como future.
- Contagem bruta de perguntas não é métrica principal de qualidade.

## Arquitetura

```
analysis/
├── notebooks/pilot-analysis.ipynb   # apresentação
├── src/                             # lógica reutilizável
├── outputs/
├── config.py
└── README.md
```
