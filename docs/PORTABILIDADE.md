# Portabilidade e Reutilizacao

## Resultado

Desde a versao 0.2.0, o AI Presence Monitor pode ser instalado como pacote
Python e usado fora do diretorio do codigo-fonte. Os hooks do Codex e o servico
systemd gerado usam o mesmo Python da instalacao.

## Instalacao Recomendada

Use um ambiente virtual dedicado:

```bash
python3 -m venv "$HOME/.local/share/ai-presence-monitor/venv"
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install /caminho/para/ai-presence-monitor
```

Os comandos ficam em:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --help
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence-interactive"
```

Para expor o comando principal no `PATH` do usuario Linux:

```bash
./scripts/install-user-command.sh
command -v ai-presence
```

O script cria um link em `~/.local/bin`. Ele e preferivel a um alias porque
tambem funciona em shells nao interativos e para AI-workers.

Atualizacao:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install --upgrade /caminho/para/ai-presence-monitor
```

Rollback do pacote:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install /caminho/para/ai-presence-monitor-0.1.0.whl
```

Guarde o wheel anterior antes de atualizar quando o monitor estiver em uso
continuo.

### Windows

O mesmo `pyproject.toml` gera um launcher `ai-presence.exe` no ambiente virtual:

```powershell
py -3 -m venv "$env:LOCALAPPDATA\ai-presence-monitor\venv"
& "$env:LOCALAPPDATA\ai-presence-monitor\venv\Scripts\python.exe" `
  -m pip install C:\caminho\para\ai-presence-monitor
& "$env:LOCALAPPDATA\ai-presence-monitor\venv\Scripts\ai-presence.exe" --help
```

Instalacao automatizada sem privilegio administrativo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\install-user-command.ps1
```

Desde a versao 0.5.0, Windows possui familia operacional completa:

- dispatcher Win32 por `ctypes` e `SendInput`;
- backend de alarme com identidade por horario de criacao do processo;
- runner de duracao limitada e parada da arvore por `taskkill`;
- Task Scheduler para monitor e observer de respostas;
- configuracao global em `%APPDATA%\ai-presence-monitor\.env`;
- estado e definicoes em `%LOCALAPPDATA%\ai-presence-monitor`.

Consulte [WINDOWS.md](WINDOWS.md) para o passo a passo.

## Onde Fica o `.env`

A CLI procura a configuracao nesta ordem:

1. `--env-file /caminho/arquivo.env`;
2. variavel `PRESENCE_ENV_FILE`;
3. `.ai-presence-monitor.env` no diretorio atual, se existir;
4. `$XDG_CONFIG_HOME/ai-presence-monitor/.env`;
5. `~/.config/ai-presence-monitor/.env` quando `XDG_CONFIG_HOME` nao existe.

Isso permite dois modelos.

### Configuracao Central

Use um unico arquivo:

```text
~/.config/ai-presence-monitor/.env
```

Esse modelo e recomendado quando todos os projetos usam os mesmos canais,
horarios e banco.

### Configuracao por Projeto

Coloque um `.ai-presence-monitor.env` na raiz de cada projeto. Esse nome
dedicado evita confundir a configuracao do monitor com o `.env` da aplicacao.
O arquivo pode ter webhooks, banco e horarios diferentes. Mantenha-o fora do Git.

Um `.env` comum so e usado automaticamente no checkout do proprio monitor, para
compatibilidade com a versao 0.1. Em qualquer outro projeto, use o nome dedicado
ou passe `--env-file` explicitamente.

Um `PRESENCE_DB_PATH` relativo e resolvido em relacao ao diretorio do `.env`, e
nao ao diretorio de onde o hook foi executado:

```env
PRESENCE_DB_PATH=./data/presence.db
```

## Isolamento de Workers

Configure:

```env
PRESENCE_CODEX_WORKER_SCOPE=project
PRESENCE_CODEX_TASK=
```

Escopos disponiveis:

| Escopo | Identidade | Uso |
|---|---|---|
| `global` | computador + IA | compatibilidade com a versao 0.1 |
| `project` | computador + IA + projeto | recomendado para projetos diferentes |
| `session` | computador + IA + sessao | sessoes simultaneas |
| `project-session` | computador + IA + projeto + sessao | isolamento maximo |

O componente de projeto inclui o nome da pasta e oito caracteres do hash do
caminho absoluto. Assim, duas pastas chamadas `backend` em locais diferentes nao
colidem.

Para `project`, execute os comandos manuais dentro da raiz do projeto:

```bash
cd /caminho/do/projeto
ai-presence start --protocol protocol2 --task "tarefa"
ai-presence finish --protocol protocol2 --task "tarefa"
```

Tambem e possivel informar explicitamente:

```bash
ai-presence start --scope project --project /caminho/do/projeto --task "tarefa"
```

`--worker` continua aceitando um ID exato e, quando usado, ignora a derivacao por
escopo.

Escopos com sessao dependem do `session_id` recebido pelo hook. Para comandos
manuais, informe `--session`. Se a sessao nao estiver disponivel, o componente
usado sera `session=unknown`.

## Hook Portatil do Codex

Depois de instalar o pacote com o Python definitivo:

```bash
ai-presence --dry-run install-codex-hook
ai-presence install-codex-hook
```

O comando gerado tem esta forma:

```text
/caminho/absoluto/python -m ai_presence_monitor.codex_hook --env-file /caminho/absoluto/.env
```

O instalador:

- substitui hooks antigos baseados em `codex_presence_hook.py`;
- preserva hooks de terceiros;
- cria `hooks.json.backup-*`;
- nao duplica entradas em reinstalacoes.

Rollback:

```bash
ai-presence uninstall-codex-hook
```

## Monitor Continuo com systemd

Gere o arquivo sem alterar o sistema:

```bash
ai-presence --dry-run install-systemd-service
```

Instale e ative:

```bash
ai-presence install-systemd-service
systemctl --user daemon-reload
systemctl --user enable --now ai-presence-monitor.service
```

Verifique:

```bash
systemctl --user status ai-presence-monitor.service
journalctl --user -u ai-presence-monitor.service -n 100
```

Rollback:

```bash
systemctl --user disable --now ai-presence-monitor.service
ai-presence uninstall-systemd-service
systemctl --user daemon-reload
```

O desinstalador cria um backup antes de remover o arquivo `.service`.

## Execucao Continua Portatil

O comando abaixo seleciona systemd no Linux e Task Scheduler no Windows:

```bash
ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor
```

Para o observer:

```bash
ai-presence install-background-service --component reply-observer
```

No Linux, o observer espera 30 segundos entre falhas e o systemd bloqueia uma
tempestade depois de tres falhas em cinco minutos. Depois de corrigir a causa:

```bash
systemctl --user reset-failed ai-presence-reply-observer.service
systemctl --user start ai-presence-reply-observer.service
```

Essa protecao e exclusiva do observer; o monitor principal preserva a politica
de reinicio continuo. No Windows, a tarefa ja limita reinicios a tres falhas.

Rollback:

```bash
ai-presence uninstall-background-service --component reply-observer
ai-presence uninstall-background-service --component monitor
```

## Limites

- Um worker `global` ainda representa apenas uma atividade por computador/IA.
- `project` separa projetos, mas duas sessoes simultaneas no mesmo projeto
  precisam de `session` ou `project-session`.
- O hook registra evidencia de eventos, nao qualidade ou progresso semantico.
- O monitor precisa estar em execucao para avaliar atrasos e enviar alertas.
- Discord, Telegram e telefonia continuam dependendo de conectividade e
  credenciais externas.
- O nome de uma aba de terminal pode nao ser o titulo da janela X11. Identidade
  de worker deve usar projeto ou sessao, nao texto visual da aba.

## Observer de Respostas

O observer de respostas possui unidade separada:

```bash
ai-presence --dry-run install-reply-observer-service
ai-presence install-reply-observer-service
systemctl --user daemon-reload
```

Para controle GUI em X11, o servico tambem precisa receber as variaveis da
sessao grafica:

```bash
systemctl --user import-environment DISPLAY XAUTHORITY XDG_RUNTIME_DIR
```

Nao habilite a unidade ou tarefa antes de concluir os testes do guia
`docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md`. Linux usa X11; Windows usa Win32.
Wayland e macOS continuam sem adaptador GUI.

## Continue Integrado

O comando faz parte do mesmo wheel:

```bash
ai-presence --dry-run continue --window-title Codex
ai-presence continue --window-title Codex
```

No Linux, ele depende de `xdotool`, `xclip` e X11. No Windows, usa somente APIs
Win32 da biblioteca padrao e nao substitui o clipboard. A sincronizacao usa o
mesmo SQLite e o mesmo escopo de worker do monitor.

## Verificacao de Release

Quando as versoes estiverem instaladas na maquina:

```bash
./scripts/test-python-matrix.sh
```

O script executa compilacao e toda a suite sequencialmente em Python 3.10, 3.11
e 3.12. A execucao sequencial evita interferencia entre ambientes Python locais.

O projeto tambem possui gate de cobertura total em 80%:

```bash
COVERAGE_CORE=pytrace python3.12 -m coverage erase
PYTHONPATH=src COVERAGE_CORE=pytrace python3.12 -m coverage run \
  -m unittest discover -s tests
COVERAGE_CORE=pytrace python3.12 -m coverage report
```

O gate completo local e:

```bash
python3 -m pip install -e '.[dev]'
./scripts/quality-check.sh
```
