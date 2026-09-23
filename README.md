# Experimento piloto — Context Dependency in LLM-Based Requirements Clarification

Pacote experimental **piloto** para estudar efeitos de contexto na clarificação de
requisitos com Spec Kit (`/speckit.clarify`). O layout espelha
`experimento-extendido`; o conteúdo experimental vem dos PRRs de
**US02, US08, US18 e US25**.

Este passo prepara **materials** e a matriz de execução. **Baselines**,
**scaffold de `runs/`** e o **runner Spec Kit / Codex ainda não foram
executados**.

---

## Visão geral

| Dimensão | Valor |
| --- | --- |
| User Stories | US02, US08, US18, US25 |
| Condições | C0, CL, CO, CD, CS, CT |
| Repetições | 3 |
| Total planejado | **4 × 6 × 3 = 72** execuções |

```text
4 User Stories × 6 context conditions × 3 repetitions = 72 executions
```

| ID | Domain (aba `user_stories`) | Main functionality |
| --- | --- | --- |
| US02 | Gestão de resíduos e reciclagem | Search nearby facilities by ZIP |
| US08 | Estimativa ágil de software | Reveal estimates simultaneously |
| US18 | Estimativa ágil de software | Join a game via invite URL |
| US25 | Sistemas de recomendação | Content recommendations by local news |

| Condition | Material provided to the agent |
| --- | --- |
| C0 | User Story only (sem `context.md`) |
| CL | User Story + lexical context |
| CO | User Story + operational context |
| CD | User Story + decisional context |
| CS | User Story + systemic context |
| CT | User Story + união dos quatro contextos |

Run IDs (sem zero-pad):

```text
US02_C0_R1
US02_CL_R2
US25_CT_R3
```

---

## Estrutura do repositório

```text
experimento-piloto/
├── data/                 # Cópia de trabalho do PRR (não alterar Downloads)
├── materials/            # User Stories + blocos de contexto por US
├── baselines/            # Vazio por enquanto (Spec Kit / specify depois)
├── runs/                 # Não scaffoldar até haver baselines
├── collected-data/       # Placeholder (.gitkeep)
├── environment/          # Registro de ambiente (template)
├── scripts/              # Pipeline (copiado/adaptado do extendido)
├── .specify/             # Spec Kit + constitution
├── .codex/               # Config Codex CLI
├── prepare_materials.py  # Gera materials + manifest + runs + validação
├── manifest.csv
├── runs.csv
├── validation_report.md
├── requirements.txt
└── README.md
```

Cada User Story em `materials/USxx/`:

```text
user-story.md
user-story-original.md
lexical.md
operational.md
decisional.md
systemic.md
total.md
```

---

## Preparar materials (a partir do PRR)

1. Garanta a planilha em `data/Matrizes de rastreabilidade - PRR.xlsx`
   (cópia não destrutiva a partir de Downloads; a original **não** é modificada).
2. Instale dependências e gere artefatos:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python prepare_materials.py
```

Opções:

```bash
python prepare_materials.py --data "data/Matrizes de rastreabilidade - PRR.xlsx"
python prepare_materials.py --source "/caminho/para/Matrizes de rastreabilidade - PRR (1).xlsx"
python prepare_materials.py --repetitions 3
```

O script é **idempotente**: pode ser reexecutado após atualizar a cópia em `data/`.

**Não** executa Spec Kit, Codex clarify nem `scripts/clarification-gen/runner.py`.

Saídas:

| Arquivo | Descrição |
| --- | --- |
| `materials/USxx/*.md` | User Story e contextos (texto literal do PRR) |
| `manifest.csv` | Matriz gap × condição (estados Open/Answered) |
| `runs.csv` | 72 runs planejados (`USxx_Cy_Rn`) |
| `validation_report.md` | Checagens estruturais e de materials |

---

## Experimental invariants

- A User Story **não muda** entre condições.
- Apenas o bloco de contexto varia (CL/CO/CD/CS/CT); **C0** não tem arquivo de contexto.
- Textos de contexto vêm **somente** da coluna *Informação de referência* do PRR (sem Gap ID, Ref ID, categoria, importância ou justificativa).
- **CT** (`total.md`) é a união exata de lexical + operational + decisional + systemic, na ordem de blocos do extendido (Lexical → Operational → Decisional → Systemic), com bullets na ordem do PRR dentro de cada categoria.
- A mesma combinação User Story × condição é **reutilizada** nas 3 repetições; a repetição é nova execução, não novo input.
- Nenhuma saída do Spec Kit altera o PRR; a planilha permanece a fonte de verdade.
- **Baselines** ainda pendentes — não copiar baselines de US19/US22 do extendido.
- **Não** randomizar a ordem de execução neste estágio.

---

## Pipeline (ainda não executar a coleta)

Wrappers em `scripts/bin/` (como no extendido). Ordem prevista após baselines:

1. `scaffold-runs` — cria pastas em `runs/` a partir de `baselines/` + `materials/`
2. `runner.py` (**não executar ainda**) — Spec Kit / Codex clarify
3. `check-outputs` → `extract-questions` → `build-classification-base`

Constantes adaptadas em `scripts/lib/runs.py`:

- `USER_STORY_IDS = ("US02", "US08", "US18", "US25")`
- `DEFAULT_REPETITIONS = 3`

---

## Ambiente e protocolo congelado

- [`environment/environment.md`](environment/environment.md) — template de registro de ambiente
- [`environment/execution-protocol.md`](environment/execution-protocol.md) — **decisões experimentais congeladas** (modelo, reasoning, baseline, falhas, sandbox, auditoria)

O ambiente do piloto deve ser preenchido quando a coleta for iniciada.
