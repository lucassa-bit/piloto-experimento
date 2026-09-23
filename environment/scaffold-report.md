# Scaffold report — P2 (72 runs)

**Data:** 2026-09-23T12:33:35-03:00 (scaffolded_at)  
**Status:** **PASS** — 20/20 validações  
**Comando:** `PYTHONPATH=scripts:scripts/clarification-gen python3 scripts/clarification-gen/scaffold_runs.py`  
**Sem** `--force` / `--clean`  
**Não executado:** Codex · `$speckit-clarify` · coleta

---

## Resumo

| Métrica | Valor |
| --- | --- |
| Total de runs | **72** |
| Por US | US02=18, US08=18, US18=18, US25=18 |
| Por condição | C0=12, CL=12, CO=12, CD=12, CS=12, CT=12 |
| Por US×condição | 3 repetições (R1–R3) em cada um dos 24 pares |
| Ordem | Determinística (US × condição × rep); sem seed/shuffle |
| Preexistentes | Nenhum (`runs/` só tinha `.gitkeep`) |
| Arquivos inesperados | Nenhum |
| Divergências | Nenhuma |

---

## Layout (convenção P0)

Cada run usa cópias físicas (sem symlink):

```text
runs/<Run_ID>/
  spec.md                              # cópia de baselines/<US>/spec.md
  checklists/requirements.md           # cópia do checklist do baseline
  experiment-input/user-story.md       # cópia de materials/<US>/user-story.md
  experiment-input/context.md          # ausente em C0; cópia literal do material
  metadata.json                        # metadados estáticos do scaffold
```

`user-story.md` / `context.md` ficam em `experiment-input/` (prompt de clarify já validado).

---

## Hashes dos baselines (congelados; inalterados após scaffold)

| US | SHA-256 `baselines/<US>/spec.md` |
| --- | --- |
| US02 | `ee9291c398af0edfda42b8420017355a54df2a71ed3ae1aac38fb014a169a4aa` |
| US08 | `427e858ff781a8a8375a37eedbdaa6ecef127a821c7f2809265ef3116d547a84` |
| US18 | `55f45f8e5811dc7b29d226fcb5945cd57814d3eb0b90e38a3a9921778ea13eaa` |
| US25 | `0d14d17c97bccc0deb8b78229be963b75293139e7dc6aed59c0c1ef1bf118c8a` |

Todas as 18 cópias `runs/<US>_*_R*/spec.md` de cada US batem com o hash acima.

---

## Hashes de User Story (materials = runs)

| US | SHA-256 `user-story.md` |
| --- | --- |
| US02 | `5e1b66dfeb18e52708677fbf0404808e0383a3045300cb4a387e9c5981b2ace6` |
| US08 | `75eafb62a6439e030cf20c5757a69b9d336bd055d675ed00c4ad6d3a8a88fc0e` |
| US18 | `004c1a82fc6d2148008f634f1f23c4d96e06252b2327aec8d495612430fb2a5f` |
| US25 | `7d2f83b698f1f354eeaba4d183c25970f08d9aae78d2fcb1fb38b4e69fd172b0` |

---

## Hashes de context por US/condição

Fonte = `materials/<US>/<arquivo>`; destino = `runs/<US>_<COND>_R*/experiment-input/context.md` (byte-a-byte).

| US | Cond | Material | SHA-256 |
| --- | --- | --- | --- |
| US02 | CL | lexical.md | `167ff59da3196ea6fe27fce83c82da232f54ffebaebd51b6bdfc8460739025dc` |
| US02 | CO | operational.md | `9d03305fd21dc061f1e690cf9bbcf8d28ca0a37c1e433901051d81d48b41e25f` |
| US02 | CD | decisional.md | `ab979770533c5a7451eeb7af2d570a51acabb39593d3b5a735dba7369b2ab3d2` |
| US02 | CS | systemic.md | `c81480b42e9b74642788bfefc7f578f46553b5105c2063a85d89e9cb5324f1e3` |
| US02 | CT | total.md | `c3f0fa42e3819cba720cca47ce0e9a6b29ac5aa19da9c87626551630a7c8b6bf` |
| US08 | CL | lexical.md | `f06bf663569aa97a1b8d86c8a1883c54e8b9bedee823240eab51067ad7860602` |
| US08 | CO | operational.md | `5e9b83ce9a26f3e313a5634f79eb7a0b475f9b35b3754610e036ebb50c202d22` |
| US08 | CD | decisional.md | `2282cb147b59ac774bdfc68e7b36eb163cb7fcc71e63a9c83bc04182103152bf` |
| US08 | CS | systemic.md | `8afeee46857128185fc8a6788b1f242663c18c9a8125267d116c8c7d24a5d0e9` |
| US08 | CT | total.md | `9ebb2f73c59057c018e157f7d2f36367d3f6d0cea66bbb3015ff5130aebbf23b` |
| US18 | CL | lexical.md | `748134c76fee8a8782b3d407fa2a586481a3bf77ae2585e3651a5c9097741f49` |
| US18 | CO | operational.md | `76727a5368fdc51b1be7743c7a3ad83f23c6c47ef2095eb7c64048923f7232b6` |
| US18 | CD | decisional.md | `069d3abdcebf08df1ab2e028a231f271cddaef36155577e92d27e9036e22b8ff` |
| US18 | CS | systemic.md | `59633699d003789543eb26a7e93d378fc878875d7cbe23cb9207116afa7f6486` |
| US18 | CT | total.md | `8df51616c58d3bf4532a5d23c7822c5a6998cc9c9462934a71b0a007bb4938f5` |
| US25 | CL | lexical.md | `7e7fc814ec5b5b281cb32c6e25a8bf5b0f4ba9a850ac58aee36054a6939b8226` |
| US25 | CO | operational.md | `eac9bf44913c26c2481ff2e2c2c682fc2bbc44cd656898e1b87426bb1ffbd63b` |
| US25 | CD | decisional.md | `2127dfbc0f1038e70d5ea9bce3cdd119374eb7ca5f66f5b4b8ab388e05002dd4` |
| US25 | CS | systemic.md | `6404f20f4694177941915328af7ff0a95907a34a81b4288db449bfb5e7a6793b` |
| US25 | CT | total.md | `37df83405f48e2ebdb97e6bdfd74d30823c2be710c9bdc38653978b8c00c538a` |

C0: `context.md` **ausente** (`context_source` / `context_sha256` = `null`).

CT: cópia literal de `materials/<US>/total.md` (não reconstruída nesta etapa).

---

## Validações (20)

| # | Critério | Resultado |
| --- | --- | --- |
| 1 | Exatamente 72 Run IDs | **PASS** |
| 2 | Exatamente 18 runs por US | **PASS** |
| 3 | Exatamente 12 runs por condição | **PASS** |
| 4 | Exatamente 3 runs por US × condição | **PASS** |
| 5 | Nenhum Run ID duplicado | **PASS** |
| 6 | Formato dos IDs correto (sem zero-pad) | **PASS** |
| 7 | Todas as runs possuem `spec.md` | **PASS** |
| 8 | Hashes dos specs = baseline congelado da US | **PASS** |
| 9 | Mesma User Story dentro da mesma US | **PASS** |
| 10 | C0 não possui `context.md` | **PASS** |
| 11 | CL usa `lexical.md` | **PASS** |
| 12 | CO usa `operational.md` | **PASS** |
| 13 | CD usa `decisional.md` | **PASS** |
| 14 | CS usa `systemic.md` | **PASS** |
| 15 | CT usa `total.md` | **PASS** |
| 16 | Hashes de `context.md` = materials | **PASS** |
| 17 | Scaffold só copia + `metadata.json` (sem conteúdo gerado / logs) | **PASS** |
| 18 | `baselines/` permanecem byte-a-byte iguais | **PASS** |
| 19 | `materials/` permanecem byte-a-byte iguais | **PASS** |
| 20 | Nenhuma execução Codex | **PASS** |

**Arquivos inesperados:** nenhum  
**Divergências:** nenhuma

---

## Árvores de exemplo

### `runs/US02_C0_R1/`

```text
checklists/requirements.md
experiment-input/user-story.md
metadata.json
spec.md
```

### `runs/US02_CL_R1/`

```text
checklists/requirements.md
experiment-input/context.md
experiment-input/user-story.md
metadata.json
spec.md
```

### `runs/US25_CT_R3/`

```text
checklists/requirements.md
experiment-input/context.md
experiment-input/user-story.md
metadata.json
spec.md
```

---

## `metadata.json` — C0 (`US02_C0_R1`)

```json
{
  "run_id": "US02_C0_R1",
  "user_story_id": "US02",
  "condition": "C0",
  "repetition": 1,
  "baseline_source": "baselines/US02/spec.md",
  "baseline_sha256": "ee9291c398af0edfda42b8420017355a54df2a71ed3ae1aac38fb014a169a4aa",
  "user_story_source": "materials/US02/user-story.md",
  "user_story_sha256": "5e1b66dfeb18e52708677fbf0404808e0383a3045300cb4a387e9c5981b2ace6",
  "context_source": null,
  "context_sha256": null,
  "scaffolded_at": "2026-09-23T12:33:35-03:00"
}
```

## `metadata.json` — CT (`US25_CT_R3`)

```json
{
  "run_id": "US25_CT_R3",
  "user_story_id": "US25",
  "condition": "CT",
  "repetition": 3,
  "baseline_source": "baselines/US25/spec.md",
  "baseline_sha256": "0d14d17c97bccc0deb8b78229be963b75293139e7dc6aed59c0c1ef1bf118c8a",
  "user_story_source": "materials/US25/user-story.md",
  "user_story_sha256": "7d2f83b698f1f354eeaba4d183c25970f08d9aae78d2fcb1fb38b4e69fd172b0",
  "context_source": "materials/US25/total.md",
  "context_sha256": "37df83405f48e2ebdb97e6bdfd74d30823c2be710c9bdc38653978b8c00c538a",
  "scaffolded_at": "2026-09-23T12:33:35-03:00"
}
```

Campos de execução (`exit_code`, `started_at`, `finished_at`, `attempt`, `stdout`, `stderr`) **não** foram preenchidos.

---

## Isolamento

- Cópias físicas (`shutil.copy2`); zero symlinks.
- Cada run tem seu próprio `spec.md` e `experiment-input/`.
- `baselines/` e `materials/` não foram modificados.
- Proteção contra overwrite: scaffold falha se Run_ID já existir (sem `--force`).

---

## Testes

`python3 -m unittest scripts.tests.test_p2_scaffold scripts.tests.test_p0_mechanical` → **OK** (antes do scaffold real).

---

**Próximo passo (não executado):** coleta clarify das 72 runs — somente com autorização explícita.
