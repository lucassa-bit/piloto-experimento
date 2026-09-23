# Preflight Report — experimento piloto

**Autoridade:** `environment/execution-protocol.md` (não alterado nesta etapa)  
**Data:** 2026-09-23  
**Escopo:** inspeção e compatibilidade apenas.  
**Não executado:** baseline-gen · scaffold das 72 runs · `/speckit.clarify` experimental · coleta.

Classificação de mudanças futuras:

- **MECHANICAL** — necessária para compatibilidade ou protocolo já congelado  
- **EXPERIMENTAL** — alteraria decisão metodológica; exige nova aprovação

---

## 1. Environment

| Item | Detectado | Esperado (protocolo) | Status |
| --- | --- | --- | --- |
| `specify --version` | **1.0.10** (`~/.local/bin/specify`) | 1.0.10 | OK |
| `specify self check` | Up to date: 1.0.10 | — | OK |
| `codex --version` | **codex-cli 0.156.1** (`~/.local/bin/codex`) | 0.156.1 | OK |
| Único `codex` no PATH | sim (1 path) | — | OK |
| `.specify/init-options.json` → `speckit_version` | 1.0.10 | 1.0.10 | OK |
| `.specify/integration.json` → `version` | 1.0.10 | 1.0.10 | OK |
| `.specify/integrations/codex.manifest.json` | version 1.0.10; `installed_at` 2026-09-23 | — | OK |
| Projeto `.codex/config.toml` | `model=gpt-5.5`, **`model_reasoning_effort=high`**, `web_search=disabled` | modelo gpt-5.5; **reasoning medium** | **DESVIO** (effort) |

**Desvio bloqueante para conformidade com protocolo:**  
`.codex/config.toml` fixa reasoning em **`high`**, mas o protocolo exige **`medium`**. Runners atuais **não** passam `-c model_reasoning_effort=…`, logo herdam `high`.

---

## 2. Codex CLI compatibility

### Sintaxe relevante de `codex exec` (0.156.1)

| Necessidade do protocolo | Mecanismo atual | Notas |
| --- | --- | --- |
| Modelo explícito | `-m` / `--model <MODEL>` | Válido |
| Reasoning effort | **`-c model_reasoning_effort=medium`** (não há flag dedicada) | Valores observados no binário: minimal/low/**medium**/high/xhigh |
| Diretório de trabalho | `-C` / `--cd <DIR>` | Válido |
| Sandbox | `-s` / `--sandbox` ∈ {`read-only`,`workspace-write`,`danger-full-access`} | Válido |
| Aprovação | `--approve-for-me`; `--dangerously-bypass-approvals-and-sandbox` | baseline-gen usa `--approve-for-me` |
| JSONL | `--json` (eventos JSONL em stdout) | **não** usado pelos runners atuais |
| Last message | `-o` / `--output-last-message <FILE>` | Usado |
| Não interativo | `codex exec` + prompt em argv ou stdin (`-`) | Usado via stdin |
| Rede | sem flag “no-network”; projeto já tem `web_search = "disabled"` | reforçar via config/`-c` |
| Sessão nova / sem resume | **não** chamar `codex exec resume` / `fork` | Runners não usam resume (bom) |
| Ephemeral | `--ephemeral` | baseline-gen usa; clarify runner **não** |

### Comparação com `scripts/lib/codex.py`

| Aspecto | Estado | Classificação |
| --- | --- | --- |
| `--cd`, `--model`, `--output-last-message`, `--sandbox`, stdin `-` | **Ainda válidos** | — |
| Flags obsoletas no helper | Nenhuma das usadas parece removida | — |
| `--json` ausente | Precisa adicionar para auditoria (protocolo § auditoria) | MECHANICAL |
| `-c model_reasoning_effort=medium` ausente | Precisa fixar explicitamente | MECHANICAL |
| Separação stdout JSONL vs log mesclado | Hoje stdout+stderr → um único log | MECHANICAL |
| Captura `spec.md` antes/depois | Ausente no helper | MECHANICAL |
| `attempt` / não sobrescrever attempt=1 | Ausente | MECHANICAL |
| `resume` | Não usado (compatível com protocolo) | Safe-to-keep |

### Exit codes

`codex exec --help` **não** documenta tabela de exit codes. Runners tratam `returncode != 0` como falha. Manter essa heurística; registrar código bruto nos metadados. (**MECHANICAL** documentar no runner.)

---

## 3. Spec Kit integration

| Artefato | Achado |
| --- | --- |
| Integração | `codex`, `ai_skills: true`, `invoke_separator: "-"` |
| Skills no projeto | 10 sob `.agents/skills/speckit-*` |
| Manifest hashes | **10/10** batem com `codex.manifest.json` 1.0.10 |
| mtime do diretório skills | 2026-08-18 (mtime antigo); conteúdo = 1.0.10 (reinstall 2026-09-23) |

**Conclusão:** integração do projeto está em **1.0.10**, não em leftover 0.12.x de conteúdo.

---

## 4. Skills discovery

| Skill | `name` (frontmatter) | Invocação documentada nos skills |
| --- | --- | --- |
| Specify | `speckit-specify` | `$speckit-specify` ou `/skill:speckit-specify` |
| Clarify | `speckit-clarify` | `$speckit-clarify` ou `/skill:speckit-clarify` |
| Outros | analyze, checklist, constitution, converge, implement, plan, tasks, taskstoissues | `$speckit-*` |

### Diferença vs prompts atuais (sem alteração nesta etapa)

| Arquivo | Sintaxe atual | Sintaxe esperada 1.0.10 |
| --- | --- | --- |
| `scripts/baseline-gen/specify-prompt.txt` | `/speckit.specify` e `/speckit.*` | `$speckit-specify` / `$speckit-*` (ou `/skill:speckit-specify`) |
| `scripts/clarification-gen/clarify-prompt.txt` | `/speckit.clarify` | `$speckit-clarify` |

**Classificação:** MECHANICAL (alinhamento de invocação), sem mudar a semântica experimental.

---

## 5. Constitution compatibility

Constitution experimental (`.specify/memory/constitution.md`):

- Audit-only; não inventar respostas  
- Evidência só em US + contexto da condição  
- Escopo funcional  
- ≤5 perguntas com `[NEEDS CLARIFICATION]`  
- **No mutation** de User Story / materials / reference files  

### Conflito com skill stock `speckit-clarify` 1.0.10

O skill nativo instrui:

1. Loop **interativo** (uma pergunta por vez; espera resposta do usuário)  
2. Após cada resposta, **escrever** `## Clarifications` e **atualizar** `spec.md`  
3. Revalidar checklist e sugerir `$speckit-plan`  

Isso **conflita** com o protocolo piloto:

- uma invocação não interativa  
- coletar perguntas **sem responder**  
- não incorporar respostas ao spec  

A constitution cobre parte do conflito, mas **não** diz explicitamente:

- não escrever `## Clarifications` / não mutar `spec.md`  
- não esperar respostas do operador  
- não sugerir/encadear `$speckit-plan` / implement  

O `clarify-prompt.txt` experimental mitiga (“Do not answer… Return only the clarification output”), porém a **tensão skill stock × prompt × constitution** permanece.

| Item | Classificação |
| --- | --- |
| Reforçar constitution/prompt para “emitir perguntas e parar; não escrever Q→A no spec” | MECHANICAL (operacionaliza protocolo já congelado) |
| Mudar o skill upstream ou o número máximo de perguntas | EXPERIMENTAL |
| Aceitar o loop interativo stock do Spec Kit | EXPERIMENTAL (quebraria o desenho) |

**Não reescrita neste preflight.**

---

## 6. Sandbox recommendation

### O que o clarify stock precisa escrever

Pelo skill: **sim** — `FEATURE_SPEC` (`spec.md`) e possivelmente `checklists/requirements.md` após respostas.

### O que o piloto exige

Emitir perguntas; **não** responder; constitution “no mutation” de materials; protocolo pede `spec.md` antes/depois para auditar mutação.

### Recomendação (sem smoke experimental nas 4 US)

| Fase | Sandbox | Motivo |
| --- | --- | --- |
| **baseline-gen** | `workspace-write` (já próximo do atual: `sandbox=None` + `--approve-for-me`) + rede off | Specify **deve** criar `spec.md` / checklist |
| **clarify coleta** | Preferência de protocolo: tentar **`read-only`** | Força mecanicamente a não persistir Q→A no disc |
| Fallback clarify | **`workspace-write` + rede desabilitada** (`web_search=disabled` já no projeto) | Se o agente/skill falhar tecnicamente ao tentar gravar sob read-only |

**Conclusão pré-smoke:**  

- **A (read-only)** é desejável e alinhada ao audit-only **se** o prompt experimental sobrescrever os passos 6–8 do skill.  
- **B (workspace-write sem rede)** é o fallback seguro se read-only gerar falha técnica por tentativa de write.  

Decisão final de sandbox do clarify: **fechada em P3** — ver `environment/clarify-smoke-report.md` e `environment/execution-protocol.md` § Sandbox.

**Resolução técnica congelada para as 72 runs:** `sandbox=read-only` · `approval_policy=never` · `model=gpt-5.5` · `reasoning_effort=medium`.  
Fallback `workspace-write` **não** será usado na coleta experimental.

Nenhuma execução experimental foi feita nesta etapa para fechar A vs B.

---

## 7. Legacy assumptions found

| Resíduo | Onde | vs protocolo |
| --- | --- | --- |
| US19 / US22 | **Ausente** em `scripts/` | OK (matriz já US02/08/18/25) |
| 5 repetições / 120 runs | **Ausente**; `DEFAULT_REPETITIONS=3` | OK |
| Seed `20260708` **em uso** | `clarification-gen/runner.py` (`CLARIFY_SEED`) | **Conflito** — seed não deve ser usada |
| Shuffle **ativo** | `random.shuffle(runs)` no clarify runner | **Conflito** — shuffle desativado |
| `gpt-5.5` só como default de env | Runners: `CLARIFY_MODEL` default `gpt-5.5` | Quase OK; falta **obrigar** e registrar; config projeto já tem model |
| Reasoning **não** fixado em medium | `.codex/config.toml` = **high**; runners não passam `-c` | **Conflito** |
| Sintaxe `/speckit.*` | `specify-prompt.txt`, `clarify-prompt.txt`, ecos em bin/ | Desatualizado vs `$speckit-*` |
| Paths antigos de skills | Não encontrados | OK |
| Materiais “auditados” extendido | Scripts leem `materials/`; conteúdo já é PRR | OK em princípio |
| `context.md` em C0 | `validate_run_inputs` **proíbe** C0+context | OK |
| Zero-pad Run ID | `R{n}` sem pad (`US02_C0_R1`) | OK |
| Sobrescrita de attempt | Clarify runner **substitui** `output.md`/logs existentes; sem `attempt` | **Conflito** |
| Resume de sessão | Não usado | OK |
| Zero perguntas = erro | `extract_questions` trata `NO_CLARIFICATION_NEEDED`; check_outputs não falha | OK |
| `--json` / auditoria completa | Ausente | Lacuna vs protocolo |
| Ordem determinística | Substituída por shuffle | **Conflito** |

---

## 8. Required changes by file

| Arquivo | Problema | Mudança necessária | Tipo |
| --- | --- | --- | --- |
| `.codex/config.toml` | `model_reasoning_effort=high` | Fixar **`medium`** (e manter `model=gpt-5.5`, web_search disabled) | MECHANICAL |
| `scripts/lib/codex.py` | Sem reasoning explícito; sem `--json`; log único; sem attempt dirs | Passar `-m gpt-5.5`, `-c model_reasoning_effort=medium`, `--json`, separar artefatos; suporte attempt | MECHANICAL |
| `scripts/clarification-gen/runner.py` | Shuffle+seed ativos; overwrite; sandbox fixo read-only; metadata incompleta | Ordem determinística; remover uso de seed; attempt=1/2 sem overwrite; metadata completa; sandbox configurável | MECHANICAL |
| `scripts/baseline-gen/runner.py` | Docstring `/speckit.specify`; reasoning não explícito; sandbox `None` | `$speckit-specify`; `-c model_reasoning_effort=medium`; workspace-write explícito; não `--force` silencioso em baseline congelado | MECHANICAL |
| `scripts/baseline-gen/specify-prompt.txt` | `/speckit.*` | Trocar para `$speckit-specify` / `$speckit-*`; manter regras experimentais | MECHANICAL |
| `scripts/clarification-gen/clarify-prompt.txt` | `/speckit.clarify`; não anula explicitamente write Q→A do skill | `$speckit-clarify`; instruções explícitas: listar até 5 perguntas de uma vez, **não** esperar resposta, **não** editar `spec.md` | MECHANICAL |
| `scripts/clarification-gen/scaffold_runs.py` | Já alinhado à matriz 3 reps / context map | Validar C0/CT; opcionalmente recusar scaffold sem baseline | MECHANICAL (menor) |
| `scripts/lib/runs.py` | Matriz OK | Opcional: constante `EXPECTED_RUNS=72`; helpers attempt | MECHANICAL (menor) |
| `scripts/lib/paths.py` / `io.py` | Genéricos | Estender paths de attempt/audit se necessário | MECHANICAL |
| `scripts/check-outputs/check_outputs.py` | Só checa `output.md` | Distinguir falha técnica vs 0 perguntas válido; checar metadata/attempt | MECHANICAL |
| `scripts/clarification-processing/extract_questions.py` | Formato de output pode mudar com Spec Kit 1.0.10 | Adaptar **após** smoke real do formato; manter 0Q válido | MECHANICAL (depois do smoke) |
| `scripts/clarification-processing/build_classification_base.py` | Não liga ao `manifest.csv`/PRR | Integrar rastreabilidade PRR sem classificar automaticamente | MECHANICAL (+ EXPERIMENTAL se auto-mapear gap) |
| `scripts/bin/*.sh|*.bat` | Ecos `/speckit.specify` | Atualizar mensagens; não rodar coleta ainda | MECHANICAL |
| `.specify/memory/constitution.md` | Não cobre “não mutar spec / não interativo” | Reforço alinhado ao protocolo | MECHANICAL (operacionaliza congelado; **não** feito neste preflight) |

Nenhuma mudança EXPERIMENTAL nova foi introduzida pelo preflight. Qualquer alteração do desenho (ex.: voltar a 5 reps, ativar shuffle, aceitar clarify interativo stock) seria **EXPERIMENTAL**.

---

## 9. Safe-to-keep behavior

- Layout `materials/` / `baselines/` / `runs/` / `collected-data/` / `scripts/lib`  
- `USER_STORY_IDS`, `CONDITIONS`, `DEFAULT_REPETITIONS=3`, `CONDITION_CONTEXT_FILES`  
- Validação C0 sem `context.md`  
- Run ID sem zero-pad  
- Constitution audit-only (núcleo)  
- `web_search = "disabled"` no projeto  
- `model = "gpt-5.5"` no `.codex/config.toml` (corrigir só o effort)  
- Baseline skip-unless-`--force` (útil após congelar)  
- Tratamento de `NO_CLARIFICATION_NEEDED` como não-erro na extração  
- Wrappers `scripts/bin` como orquestração (após adaptação)  
- Pipeline conceitual baseline → scaffold → clarify → check → extract → classify  

---

## 10. Blocking issues

Ordenados por severidade para **adaptação** (ainda sem coleta):

1. **Reasoning `high` vs protocolo `medium`** (config + ausência de `-c` nos runners) — MECHANICAL  
2. **Shuffle ativo + seed `20260708`** no clarify runner — MECHANICAL  
3. **Conflito skill clarify stock (interativo + escreve spec) × protocolo (perguntas only)** — MECHANICAL via prompt/constitution; risco residual de mutação/interatividade  
4. **Prompts com `/speckit.*`** vs invocação `$speckit-*` — MECHANICAL  
5. **Overwrite de outputs** sem `attempt` — MECHANICAL  
6. **Auditoria incompleta** (`--json`, spec before/after, versões) — MECHANICAL  
7. **Sandbox clarify A vs B** ainda não fechado por smoke descartável — pendência operacional (protocolo já prevê)  

**Não bloqueante para matriz:** ausência de US19/US22/5 reps nos scripts (já corrigido).

### Decisões experimentais ainda abertas

| Item | Estado |
| --- | --- |
| Modelo `gpt-5.5` | Congelado |
| Reasoning `medium` | Congelado (código/config ainda não alinhados) |
| Shuffle off / sem seed | Congelado (código ainda não alinhado) |
| attempt=2 / preservar attempt=1 | Congelado (código ainda não) |
| Sandbox clarify final | **Congelado: `read-only`** (P3 smoke PASS; sem fallback experimental) |
| Forma exata do output clarify 1.0.10 sob prompt experimental | **Pendente smoke** (afeta extract/check) |

---

## 11. Recommended adaptation order

```text
0. (feito) Preflight → este relatório
1. Alinhar .codex/config.toml → model_reasoning_effort=medium
2. Adaptar scripts/lib/codex.py (model+reasoning explícitos, --json, attempt paths)
3. Atualizar specify-prompt.txt + clarify-prompt.txt ($speckit-*; anti-write/anti-interactive)
4. Reforçar constitution (sem reabrir decisões) — sob aprovação explícita na próxima etapa
5. Adaptar baseline-gen/runner.py
6. Adaptar clarification-gen/runner.py (no shuffle, attempt, metadata, sandbox config)
7. Ajustes menores scaffold_runs / runs.py / bin/
8. Smoke NÃO experimental (US fictícia / temp) → fechar sandbox + formato de output
9. Só então: baseline das 4 US → scaffold → coleta (com autorização)
10. Por último: check_outputs / extract / classification_base conforme output real
```

---

## Apêndice A — Versões detectadas (verbatim)

```text
specify 1.0.10
codex-cli 0.156.1
```

## Apêndice B — Invocação skills

```text
$speckit-specify
$speckit-clarify
# alternativo documentado nos skills:
/skill:speckit-specify
/skill:speckit-clarify
```

## Apêndice C — Flags `codex exec` usadas vs a adicionar

| Flag / config | Hoje nos scripts | Ação |
| --- | --- | --- |
| `--model gpt-5.5` | sim (default env) | tornar obrigatório + logar |
| `-c model_reasoning_effort=medium` | **não** | adicionar |
| `--cd` | sim | manter |
| `--sandbox` | clarify: read-only; baseline: None+approve | fechar após smoke |
| `--json` | **não** | adicionar |
| `--output-last-message` | sim | manter (não como única fonte) |
| `--ephemeral` | só baseline | avaliar clarify (sessão limpa) |
| `exec resume` | não | continuar evitando |
