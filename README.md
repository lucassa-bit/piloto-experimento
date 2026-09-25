# Experimento piloto — Context Dependency in LLM-Based Requirements Clarification

Pacote experimental (US02, US08, US18, US25). A coleta oficial em `runs/` está
**congelada** e é a fonte científica.

## Interface pública: `scripts/bin/`

```bash
./scripts/bin/status.sh          # status da coleta / anotação
./scripts/bin/preflight.sh       # ferramentas + integridade
./scripts/bin/check-outputs.sh   # checagem técnica → audit/
./scripts/bin/validate-all.sh    # validação estrutural → audit/
./scripts/bin/run-all.sh         # preflight + check + validate + status
./scripts/bin/retry-run.sh --run US02_CO_R2 --attempt 2   # só se necessário
```

Entrypoints de **reconstrução** (`prepare-materials`, `build-baselines`,
`scaffold-runs`, `collect`, `extract-questions`, `prepare-annotation`) estão
**desabilitados** na coleta oficial — não apagam nem recriam `runs/`.

---

## Layout

| Caminho | Papel |
| --- | --- |
| `runs/` | 72 execuções oficiais (não apagar) |
| `baselines/`, `materials/` | inputs congelados |
| `collected-data/` | perguntas, PRR CSVs, folhas de anotação |
| `collected-data/audit/` | integridade + relatórios de verificação |
| `environment/environment.md` | registro de ambiente |
| `environment/collection-report.md` | relatório da coleta |

---

## Anotação humana

Folhas em `collected-data/annotation/` (`mapped_gap_ids` preenchido por humanos).
Instruções: `collected-data/annotation/README.md`.

---

## Pré-requisitos

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Spec Kit 1.0.10 · Codex 0.156.1 · modelo gpt-5.5 · reasoning medium.
