# Protocolo de execução — experimento piloto (congelado)

Decisões experimentais confirmadas antes da adaptação dos scripts.
Não alterar sem registrar nova versão do protocolo.

**Data de congelamento:** 2026-09-23  
**Status:** congelado — scripts ainda não adaptados / coleta ainda não iniciada

---

## Matriz experimental

| Dimensão | Valor |
| --- | --- |
| User Stories | US02, US08, US18, US25 |
| Condições | C0, CL, CO, CD, CS, CT |
| Repetições | 3 |
| Total | 72 execuções |
| Run ID | `USxx_Cy_Rn` **sem** zero-pad (ex.: `US02_C0_R1`) |
| Shuffle | **desativado** (ordem determinística US × condição × rep) |
| Seed | **não utilizada** neste piloto |

---

## Modelo e configuração Codex

| Parâmetro | Valor congelado |
| --- | --- |
| Modelo | **`gpt-5.5`** (explícito; **não** usar default do Codex) |
| Reasoning | **`medium`** (explícito em todas as 72 execuções) |
| Sessão | Nova sessão por run (**sem** `resume`) |
| Comparabilidade | Mantida com o experimento estendido via modelo fixo |

---

## Baseline e clarificação

1. **Um baseline por US**, gerado uma única vez só a partir de `user-story.md` (sem CL/CO/CD/CS/CT).
2. Baseline **congelado** e reutilizado nas 18 execuções daquela US (6 condições × 3 reps).
3. Cada run parte de uma **cópia limpa** do baseline da respectiva US.
4. O contexto da condição é injetado **somente** no momento do clarify:
   - C0 → sem `context.md`
   - CL → `lexical.md`
   - CO → `operational.md`
   - CD → `decisional.md`
   - CS → `systemic.md`
   - CT → `total.md`
5. **Exatamente uma** invocação de clarify por run.
6. Coletar as **perguntas** e **encerrar sem responder** (constitution audit-only).
7. **0 perguntas** com sucesso técnico = resultado experimental **válido** (`NO_CLARIFICATION_NEEDED` ok).

---

## Falhas técnicas

| Regra | Valor |
| --- | --- |
| Política | Mesmo `Run_ID` + `attempt=2` |
| attempt=1 | **Preservar** (nunca sobrescrever logs/output) |
| Quando repetir | Somente **falha técnica** |
| Quando **não** repetir | Resultado semanticamente “ruim” ou **0 perguntas** bem-sucedidas |

---

## Sandbox (resolução técnica congelada — P3 smoke)

| Parâmetro | Valor congelado |
| --- | --- |
| Clarify sandbox | **`read-only`** |
| Approval policy | **`never`** |
| Modelo | **`gpt-5.5`** |
| Reasoning | **`medium`** |
| Sessão | Nova por run (**sem** `resume`) |

**Evidência:** `environment/clarify-smoke-report.md` — `$speckit-clarify` audit-only produziu perguntas com `sandbox=read-only`, `spec.md` inalterado.

**Não utilizar** `workspace-write` nas 72 runs experimentais (fallback do smoke não acionado).

Histórico do preflight (agora fechado):

1. Tentar `read-only` primeiro — **confirmado suficiente**.
2. Fallback `workspace-write` — **não aplicável** à coleta experimental.

---

## Auditoria por run (obrigatória)

Preservar, no mínimo:

- stdout / JSONL bruto
- stderr
- last-message
- `spec.md` antes e depois
- versões: Spec Kit, Codex, modelo, reasoning, sandbox, cwd, exit code, timestamps
- `attempt`

---

## Ferramentas (versão no momento do congelamento do protocolo)

| Ferramenta | Versão |
| --- | --- |
| Spec Kit / specify | 1.0.10 |
| Codex CLI | 0.156.1 |

Skills do projeto: `.agents/skills/` alinhados à integração Spec Kit 1.0.10.

---

## Ordem de trabalho (ainda sem coleta)

```text
0. Preflight de compatibilidade
1. Adaptar scripts (P0→P4)
2. baseline-gen (4 US) → congelar baselines
3. scaffold-runs
4. clarification runner (72) — só após autorização
5. check → extract → classification base
```

---

## Invariantes (resumo)

- User Story não muda entre condições.
- Só o contexto adicional varia; C0 sem contexto; CT sem informação exclusiva.
- Materials vêm do PRR literal; scripts não melhoram/inventam conteúdo.
- Repetições reutilizam o mesmo tratamento (mesmos arquivos de material/baseline).
- Saídas do Spec Kit não modificam o PRR.
