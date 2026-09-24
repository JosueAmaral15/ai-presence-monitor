# Portabilidade e Reutilizacao

## Resultado

Desde a versao 0.2.0, o AI Presence Monitor pode ser instalado como pacote
Python e usado fora do diretorio do codigo-fonte. Os hooks do Codex e o servico
systemd gerado usam o mesmo Python da instalacao.

Desde a versao 0.6.2, Linux e o runtime suportado para publicacao. Os adaptadores
Windows continuam no pacote e nos testes, mas sua execucao fica desabilitada
por padrao e exige opt-in experimental explicito.

## Instalacao Recomendada

Para a release privada Linux 0.9.0, extraia o bundle e valide seu conteudo:

```bash
sha256sum -c SHA256SUMS
python3 verify_release.py .
./install-linux.sh --wheel ./ai_presence_monitor-0.9.0-py3-none-any.whl
```

Os comandos ficam em:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --help
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence-interactive"
```

O instalador cria o link em `~/.local/bin`, preserva um `.env` existente e nao
habilita componentes opcionais. Para atualizar uma instalacao existente, use o
updater transacional e forneca o wheel exato da versao instalada:

```bash
ai-presence --dry-run upgrade \
  --package /caminho/absoluto/novo.whl \
  --rollback-package /caminho/absoluto/instalado.whl \
  --json
```

Depois de revisar o dry-run, a operacao real exige autorizacao unica:

```bash
ai-presence upgrade \
  --package /caminho/absoluto/novo.whl \
  --rollback-package /caminho/absoluto/instalado.whl \
  --authorize-once
```

Nao use `pip install --upgrade` diretamente em um runtime operacional: esse
caminho ignora snapshot SQLite, estado de servicos, manifesto e rollback.
Consulte [INSTALL-LINUX.md](INSTALL-LINUX.md) e
[TRANSACTIONAL-UPGRADE.md](TRANSACTIONAL-UPGRADE.md).

### Windows

Instalar o pacote e consultar `--help` continuam permitidos. Qualquer operacao
Windows que possa criar estado, instalar componentes, enviar entrada ou iniciar
monitoramento exige esta configuracao no `.env` selecionado:

```env
PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true
```

Mantenha `false` em distribuicoes normais. Diagnostico e recuperacao continuam
disponiveis com o runtime desabilitado para que alarmes, hooks e tarefas antigas
nao fiquem presos.

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

Desde a versao 0.5.0, o codigo Windows possui uma familia operacional completa:

- dispatcher Win32 por `ctypes` e `SendInput`;
- backend de alarme com identidade por horario de criacao do processo;
- runner de duracao limitada e parada da arvore por `taskkill`;
- Task Scheduler para monitor e observer de respostas;
- configuracao global em `%APPDATA%\ai-presence-monitor\.env`;
- estado e definicoes em `%LOCALAPPDATA%\ai-presence-monitor`.

Desde a versao 0.6.0, `codex queue` oferece entrada nativa compartilhada entre
Linux e Windows sem depender dos adaptadores GUI. O comando Codex precisa estar
no `PATH`. A bandeja PySide6 tambem e portatil, mas permanece extra opcional:

```bash
python -m pip install '/caminho/para/ai-presence-monitor[tray]'
ai-presence tray --check
```

Na versao 0.6.1, o envio para a propria sessao inicia um subprocesso destacado:
POSIX usa `start_new_session` e Windows usa um novo grupo de processo sem abrir
janela. O retorno `dispatch_started` nao atualiza presenca; o hook posterior e
a evidencia portatil de processamento.

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

Sem `PRESENCE_CONTROL_PATH`, o `control.json` usa a area de estado do usuario e
fica fora do checkout. Quando configurado, um caminho relativo usa a mesma
regra do banco. O arquivo centraliza flags e alvos alterados em tempo de
execucao e deve permanecer fora do Git.

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

O gate completo de uma release limpa gera e valida o bundle:

```bash
./scripts/release-gate.sh "$PWD/dist/release-0.9.0"
```

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
