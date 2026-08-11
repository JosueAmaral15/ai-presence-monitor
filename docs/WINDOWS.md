# Guia Operacional do Windows

## Capacidades

A versao 0.5.0 oferece no Windows:

- CLI, menu, SQLite, protocolos, hooks e notificacoes;
- automacao da janela do Codex pela API Win32;
- alarme local com limite obrigatorio e `stop-alarm`;
- monitor e observer de respostas no Task Scheduler;
- caminhos nativos em `%APPDATA%` e `%LOCALAPPDATA%`;
- testes automatizados em `windows-latest`.

Nao e necessario executar como administrador. A automacao GUI exige a sessao do
usuario desbloqueada e uma janela visivel.

## Instalacao

Abra PowerShell na raiz do projeto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\install-user-command.ps1
```

O script cria:

```text
%LOCALAPPDATA%\ai-presence-monitor\venv
```

Teste o launcher instalado:

```powershell
$AiPresence = "$env:LOCALAPPDATA\ai-presence-monitor\venv\Scripts\ai-presence.exe"
& $AiPresence --help
```

Para usar diretamente do checkout:

```powershell
.\run_interactive.bat
```

## Configuracao

O arquivo global padrao fica em:

```text
%APPDATA%\ai-presence-monitor\.env
```

Crie-o a partir do exemplo:

```powershell
$ConfigDir = "$env:APPDATA\ai-presence-monitor"
New-Item -ItemType Directory -Force $ConfigDir | Out-Null
Copy-Item .env.example "$ConfigDir\.env"
notepad "$ConfigDir\.env"
```

Tambem e permitido usar `.ai-presence-monitor.env` na raiz de cada projeto ou
passar `--env-file` explicitamente.

Primeiro teste sem rede, banco ou GUI:

```powershell
& $AiPresence --dry-run protocols
& $AiPresence --dry-run monitor --once
& $AiPresence --dry-run continue --window-title "Codex"
```

## Automacao da Janela

O adaptador Win32:

1. enumera janelas superiores visiveis;
2. aplica `PRESENCE_CODEX_GUI_WINDOW_TITLE` como expressao regular;
3. exige exatamente uma correspondencia;
4. captura o `HWND` e o titulo;
5. depois do delay, revalida o mesmo `HWND` e titulo;
6. ativa a janela e verifica se ela recebeu foreground;
7. clica nas proporcoes configuradas;
8. envia texto Unicode e Enter por `SendInput`.

O clipboard nao e alterado no Windows. O texto nunca e enviado a `cmd.exe` ou
PowerShell e nao e interpretado como comando.

### Localizar o identificador da janela

Normalmente basta fornecer um titulo unico. Se houver ambiguidade, liste os
handles de janelas principais:

```powershell
Get-Process |
  Where-Object { $_.MainWindowHandle -ne 0 } |
  Select-Object ProcessName, MainWindowHandle, MainWindowTitle
```

Use `MainWindowHandle`, nao o PID:

```powershell
& $AiPresence continue `
  --window-id 123456 `
  --window-title "Codex.*AmaralAgenda" `
  --allow-title-change
```

### Limites do Windows

- tela bloqueada, UAC em secure desktop ou outra sessao impedem entrada;
- `SetForegroundWindow` pode ser negado pelo Windows; nesse caso o dispatcher
  falha fechado e nao digita;
- uma tarefa executada como `SYSTEM` nao interage com o desktop do usuario;
- mantenha o observer como tarefa de logon do usuario com privilegio limitado.

## Continue Integrado

Uso normal:

```powershell
& $AiPresence start --protocol protocol2 --task "tarefa atual"
& $AiPresence continue --window-title "Codex" --delay 60
```

Depois de uma emissao bem-sucedida, somente um worker existente e ativo recebe
`observation:automation:continue`. Falha de janela, `--dry-run` ou cancelamento
nao atualizam a atividade.

## Alarme Local

Exemplo com FFmpeg/ffplay instalado:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=ffplay.exe -nodisp -loop 0 "C:\Sounds\alarm.mp3"
```

O controlador:

- interpreta a linha com `CommandLineToArgvW`;
- inicia um runner Python em grupo proprio;
- identifica o runner por PID, horario nativo de criacao e executavel;
- encerra a arvore com `taskkill /T /F` no limite;
- impede outro alarme enquanto o processo registrado estiver ativo.

Interrupcao manual:

```powershell
& $AiPresence stop-alarm
```

O comando nunca procura processos apenas pelo nome `ffplay.exe`.

## Task Scheduler

### Monitor

```powershell
& $AiPresence --dry-run install-background-service --component monitor
& $AiPresence install-background-service --component monitor
schtasks.exe /Run /TN "AI Presence Monitor"
schtasks.exe /Query /TN "AI Presence Monitor" /V /FO LIST
```

### Observer de respostas

Ative o fluxo Discord e teste uma resposta manual antes de registrar:

```powershell
& $AiPresence --dry-run install-background-service --component reply-observer
& $AiPresence install-background-service --component reply-observer
schtasks.exe /Run /TN "AI Presence Reply Observer"
```

As definicoes XML ficam em:

```text
%LOCALAPPDATA%\ai-presence-monitor\tasks
```

Elas contêm caminhos para Python e `.env`, nao os valores secretos do `.env`.

## Remocao e Rollback

Remova primeiro as tarefas:

```powershell
& $AiPresence uninstall-background-service --component reply-observer
& $AiPresence uninstall-background-service --component monitor
```

Interrompa qualquer alarme:

```powershell
& $AiPresence stop-alarm
```

Depois, se necessario, remova apenas o ambiente instalado:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\ai-presence-monitor\venv"
```

Nao remova o `.env` nem o SQLite durante rollback. A versao 0.5.0 nao altera o
schema do banco.

## Desenvolvimento e Testes

```powershell
py -3 -m pip install -e ".[dev]"
py -3 scripts\quality_check.py
```

O gate executa compilacao, testes, cobertura, Ruff, mypy, build do wheel e
`git diff --check` sem depender de Bash.
