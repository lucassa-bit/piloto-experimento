# Ambiente de execução

Registro do ambiente usado no experimento. No caso de replicação execute os comandos da sua plataforma e cole a saída na seção **Ambiente de experimento** correspondente.

---

## Windows (PowerShell)

```powershell
Write-Output "=== DATE ==="
Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"

Write-Output "`n=== OPERATING SYSTEM ==="
Get-CimInstance Win32_OperatingSystem |
    Select-Object Caption, Version, BuildNumber, OSArchitecture |
    Format-List

Write-Output "`n=== POWERSHELL ==="
$PSVersionTable | Format-List

Write-Output "`n=== TOOLS ==="
specify --version
codex --version
python --version
uv --version
git --version

Write-Output "`n=== PYENV ==="
pyenv version
```

---

## Linux (bash)

```bash
echo "=== DATE ==="
date --iso-8601=seconds

echo ""
echo "=== KERNEL ==="
uname -a

echo ""
echo "=== OPERATING SYSTEM ==="
cat /etc/os-release

echo ""
echo "=== TOOLS ==="
specify --version
codex --version
python --version
uv --version
git --version
```

---

### Spec Kit (piloto)

Em 2026-09-23 o CLI e a integração do projeto foram atualizados para **Spec Kit 1.0.10** (`uv tool install` from `git+https://github.com/github/spec-kit.git@v1.0.10`; integração `codex` com `ai_skills`). A constitution experimental (audit-only) foi preservada.

### Codex CLI (piloto)

Em 2026-09-23 o Codex CLI neste host Linux foi atualizado de **0.147.0** para **0.156.1** via instalador standalone (`codex update` → `curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh`; binário em `~/.local/bin/codex` → `~/.codex/packages/standalone`).

---

### Ambiente de experimento

```
=== DATE ===
2026-07-08T15:07:57-03:00

=== OPERATING SYSTEM ===
Caption        : Microsoft Windows 11 Pro
Version        : 10.0.26200
BuildNumber    : 26200
OSArchitecture : 64 bits

=== POWERSHELL ===
PSVersion                      5.1.26100.8457
PSEdition                      Desktop
PSCompatibleVersions           {1.0, 2.0, 3.0, 4.0...}
BuildVersion                   10.0.26100.8457
CLRVersion                     4.0.30319.42000
WSManStackVersion              3.0
PSRemotingProtocolVersion      2.3
SerializationVersion           1.1.0.1

=== TOOLS ===
specify 0.12.8.dev0
codex-cli 0.143.0
Python 3.7.9
uv 0.11.16 (135a36367 2026-05-21 x86_64-pc-windows-msvc)
git version 2.48.1.windows.1

=== PYENV ===
3.7.9 (set by %PYENV_VERSION%)
```

> Nota: o bloco acima registra o ambiente na data original do experimento. Após o upgrade do piloto, o CLI/projeto passam a reportar `specify 1.0.10` (ver seção Spec Kit acima).