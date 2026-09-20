# AI Presence Monitor

[English documentation](README.md)

## Diagnostico do produto

Os comandos abaixo identificam a versao instalada e inspecionam a saude local
sem imprimir segredos nem alterar o banco durante a leitura:

```bash
ai-presence --version
ai-presence schema-status
ai-presence doctor
ai-presence doctor --json
ai-presence doctor --strict
```

`schema-status` informa a versao esperada, a versao atual, a necessidade de
migracao e a integridade SQLite. `doctor --strict` tambem retorna codigo
diferente de zero quando houver avisos.

Monitor local para presencas artificiais de trabalho. Ele registra atividade de uma IA/agente, mantém estado em SQLite e envia notificacoes automáticas por Discord e, opcionalmente, Telegram.

Esta release possui suporte operacional oficial somente para Linux. O codigo
Windows foi preservado, mas fica experimental e desabilitado por padrao. Testes
controlados no Windows exigem `PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true`.

O projeto tambem registra evidencias diagnosticas com TTL sem alterar os
relogios de presenca. No Linux, `observe-linux-state` pode observar um PID
explicito, rota e links locais, retomada depois de suspensao e unidades
`.service` selecionadas. Esses fatos nao constituem diagnostico, nao enviam
alertas e nao acionam recuperacao automaticamente. O comando one-shot
`diagnose` correlaciona os fatos atuais, registra confianca e mantem no maximo
um incidente aberto por worker. Ele ainda nao envia notificacao nem executa
recuperacao. O comando separado `notify-diagnostic-incident` pode enviar uma
mensagem Discord deduplicada para o incidente, sem tocar alarme, enviar input
ou recuperar a sessao. Uma recuperacao restrita existe somente no comando
explicito `recover-diagnostic-incident`: ela nunca e iniciada automaticamente.

## Protocolos

### Protocolo 1

A IA deve sinalizar publicamente a cada 5 minutos que continua trabalhando. O canal de ponto recebe as batidas de atividade.

Alertas:

- amarelo: 7 minutos sem nova sinalizacao;
- laranja: 15 minutos sem nova sinalizacao;
- vermelho: 30 minutos sem nova sinalizacao.

### Protocolo 2

A IA sinaliza publicamente somente quando inicia e termina. Durante a tarefa, chamadas silenciosas de `touch` podem registrar atividade interna sem postar no canal de ponto.

Alertas:

- amarelo: 5 minutos sem atividade;
- laranja: 10 minutos sem atividade;
- vermelho: 15 minutos sem atividade.

## Configuracao

Guia detalhado do `.env` e dos dados necessarios:

- [docs/INDEX.md](docs/INDEX.md)
- [docs/USO-COMO-FERRAMENTA.md](docs/USO-COMO-FERRAMENTA.md)
- [docs/CONFIGURANDO-ENV.md](docs/CONFIGURANDO-ENV.md)
- [docs/ENVIRONMENT-GUIDE.md](docs/ENVIRONMENT-GUIDE.md)
- [docs/CONTINUE-CODEX.md](docs/CONTINUE-CODEX.md)
- [docs/SYSTEM-TRAY-NATIVE-INPUT.md](docs/SYSTEM-TRAY-NATIVE-INPUT.md)
- [docs/AI-WORKER-COMMAND-PROTOCOL.md](docs/AI-WORKER-COMMAND-PROTOCOL.md)
- [docs/PORTABILIDADE.md](docs/PORTABILIDADE.md)
- [docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md](docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md)
- [docs/TRANSACTIONAL-UPGRADE.md](docs/TRANSACTIONAL-UPGRADE.md)

Instalacao portatil recomendada:

```bash
python3 -m venv "$HOME/.local/share/ai-presence-monitor/venv"
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install /caminho/para/ai-presence-monitor
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --help
```

Para uma futura atualizacao privada no Linux, valide primeiro os dois wheels
locais sem alterar a instalacao:

```bash
ai-presence --dry-run upgrade \
  --package /caminho/absoluto/novo.whl \
  --rollback-package /caminho/absoluto/instalado.whl \
  --json
```

A execucao real exige `--authorize-once` e cria manifesto, hashes e snapshot
SQLite privados antes de parar os servicos gerenciados. O rollback manual
restaura o banco anterior, descarta dados posteriores e exige tambem
`--restore-database`. Leia o guia transacional antes dessas operacoes.

No Windows PowerShell, sem privilegios administrativos:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\install-user-command.ps1
& "$env:LOCALAPPDATA\ai-presence-monitor\venv\Scripts\ai-presence.exe" --help
```

A instalacao preserva os adaptadores, mas comandos operacionais Windows ficam
bloqueados. Ative-os somente para desenvolvimento controlado no `.env`:

```env
PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true
```

Durante o desenvolvimento no proprio checkout:

```bash
cd /caminho/para/ai-presence-monitor
python3 main.py
```

O menu pergunta os dados no terminal e pode criar o `.env`, inicializar o banco, registrar ponto, registrar inicio/fim de tarefa e rodar o monitor.

A versao 0.6.1 tambem oferece entrada direta por `codex queue`, sem controlar
mouse ou teclado, e uma bandeja opcional. Instale e inicie com:

```bash
python -m pip install '/caminho/para/ai-presence-monitor[tray]'
ai-presence tray --check
ai-presence tray
```

O guia da bandeja explica os checkboxes, o comando `send-input`, o transporte
local/remoto e a autorizacao do procedimento `continue`.

Quando o alvo e a propria sessao Codex, o comando retorna `dispatch_started`
sem bloquear o turno e sem antecipar atividade. Um hook posterior registra
atividade da sessao, mas a autoria de uma mensagem exige correlacao adicional.

Atalho equivalente no Linux:

```bash
./run_interactive.sh
```

Atalho no Windows:

```powershell
.\run_interactive.bat
```

Se quiser testar sem enviar mensagens reais:

```bash
python3 main.py --dry-run
```

## Operacao por AI-worker

O pacote fornece o comando de terminal instalavel `ai-presence`. Para
disponibiliza-lo no `PATH` do usuario Linux:

```bash
./scripts/install-user-command.sh
ai-presence --help
```

Uma IA responsavel por operar o monitor deve ler [AGENTS.md](AGENTS.md),
[docs/USO-COMO-FERRAMENTA.md](docs/USO-COMO-FERRAMENTA.md) e
[docs/AI-WORKER-COMMAND-PROTOCOL.md](docs/AI-WORKER-COMMAND-PROTOCOL.md).
O protocolo define inicio, atividade observada, perguntas, continuidade,
encerramento, codigos de saida e limites da automacao GUI.

Configuracao manual:

```bash
cd /caminho/para/ai-presence-monitor
cp .env.example .env
```

Edite `.env` e preencha pelo menos:

```env
DISCORD_POINT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

No Discord, crie um webhook em cada canal desejado. Um webhook pertence a um canal; por isso o canal de ponto e o canal de alertas precisam de URLs diferentes.

Para cobrar alertas somente durante um expediente e repetir avisos enquanto o worker continuar atrasado, configure:

```env
PRESENCE_WORK_WINDOW_ENABLED=true
PRESENCE_WORK_WINDOW_START=13:00
PRESENCE_WORK_WINDOW_END=18:00
PRESENCE_WORK_WINDOW_TIMEZONE=America/Sao_Paulo
PRESENCE_ALERT_REPEAT_ENABLED=true
PRESENCE_ALERT_REPEAT_SECONDS=300
PRESENCE_ALERT_REPEAT_LEVELS=yellow,orange
```

Amarelo e laranja podem repetir pelo intervalo configurado. O vermelho e
enviado somente uma vez por episodio continuo de inatividade e e rearmado por
uma nova atividade valida da IA.

## Uso

Inicializar o banco:

```bash
python3 -m ai_presence_monitor init
```

Listar protocolos:

```bash
python3 -m ai_presence_monitor protocols
```

Rodar o monitor uma vez:

```bash
python3 -m ai_presence_monitor monitor --once
```

Rodar o monitor continuamente:

```bash
python3 -m ai_presence_monitor monitor
```

Ver estado atual:

```bash
python3 -m ai_presence_monitor status
```

## Perguntas e Respostas Remotas

O monitor pode publicar uma pergunta em um canal dedicado do Discord, aceitar
somente resposta direta de usuario autorizado e devolver o texto para a sessao
exata do Codex salva na pergunta. O transporte nativo usa `codex queue` sem
mouse ou teclado; `store` e GUI sao alternativas explicitas.

Enquanto existir pergunta pendente, uma mensagem invalida de usuario
autorizado recebe uma unica orientacao no Discord. O aviso explica como usar
**Responder** e aponta `Message Content Intent` quando a API entregar texto
vazio. Bots, webhooks, usuarios nao autorizados e canais sem pergunta pendente
permanecem silenciosos.

O recurso e desativado por padrao. Configure e teste primeiro em modo `store`.
Para entrega nativa, informe `--thread` quando a sessao nao puder ser herdada
sem ambiguidade. Falha nativa nao aciona GUI nem retry automatico. Siga
[docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md](docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md).

```bash
ai-presence --dry-run ask-user --worker worker-id --thread SESSAO --question "Posso prosseguir?"
ai-presence ask-user --worker worker-id --thread SESSAO --question "Posso prosseguir?"
ai-presence observe-replies --once
ai-presence observe-replies
ai-presence questions
```

Para a execucao continua separada em qualquer plataforma:

```bash
ai-presence --dry-run install-background-service --component reply-observer
ai-presence install-background-service --component reply-observer
```

No Linux, execute os comandos `systemctl` impressos. No Windows, execute o
comando `schtasks.exe /Run` impresso para iniciar a tarefa imediatamente.
No Linux, o observer tenta novamente a cada 30 segundos e interrompe o ciclo
depois de tres falhas em cinco minutos. Depois de corrigir credenciais ou rede,
execute `systemctl --user reset-failed
ai-presence-reply-observer.service` antes de inicia-lo novamente. O monitor
principal preserva sua politica de reinicio independente.

## Continue Integrado

O pacote incorpora o envio programado de `continue` ao mesmo monitor:

```bash
ai-presence --dry-run continue \
  --worker ID_EXATO_DO_WORKER \
  --window-title 'Codex'

ai-presence continue \
  --worker ID_EXATO_DO_WORKER \
  --window-title 'Codex'
```

O atraso padrao e 60 segundos. O alvo deve ser uma unica janela visivel e e
revalidado depois da espera. Linux usa X11; Windows usa a API Win32 nativa e
digita Unicode sem substituir o clipboard.

Se o terminal muda dinamicamente o titulo, `--allow-title-change` pode ser
combinado com `--window-id` explicito. Nesse modo, o mesmo ID e o padrao de
titulo ainda sao revalidados; apenas a igualdade do titulo completo e relaxada.

Quando a emissao termina com sucesso e o worker indicado esta `active`, o
comando registra `observation:automation:continue`. No Protocolo 2 isso atualiza
`last_activity_at` e reinicia a contagem de inatividade. Se nenhuma atividade
posterior ocorrer, os alertas de 5/10/15 minutos retornam normalmente.

No Protocolo 1, `last_signal_at` nao e alterado; o heartbeat publico continua
obrigatorio. Agendamento, `dry-run`, falha GUI e worker inativo nao contam como
atividade.

Consulte [docs/CONTINUE-CODEX.md](docs/CONTINUE-CODEX.md) para configuracao,
execucao em segundo plano, sincronizacao e rollback.

## Protocolo 1: exemplo

Quando a IA começar a trabalhar:

```bash
python3 -m ai_presence_monitor start \
  --ai codex \
  --protocol protocol1 \
  --task "refatoracao-x" \
  --message "iniciando a tarefa"
```

Enquanto estiver trabalhando, enviar batida de ponto a cada 5 minutos:

```bash
python3 -m ai_presence_monitor heartbeat \
  --ai codex \
  --protocol protocol1 \
  --task "refatoracao-x" \
  --message "continuo trabalhando na tarefa"
```

Ao terminar:

```bash
python3 -m ai_presence_monitor finish \
  --ai codex \
  --protocol protocol1 \
  --message "tarefa concluida"
```

## Protocolo 2: exemplo

Inicio:

```bash
python3 -m ai_presence_monitor start \
  --ai codex \
  --protocol protocol2 \
  --task "algoritmo-y" \
  --message "execucao iniciada"
```

Atividade silenciosa, sem postar no Discord:

```bash
python3 -m ai_presence_monitor touch \
  --ai codex \
  --protocol protocol2 \
  --task "algoritmo-y" \
  --message "passo interno executado"
```

Fim:

```bash
python3 -m ai_presence_monitor finish \
  --ai codex \
  --protocol protocol2 \
  --message "execucao finalizada"
```

## Observer do Codex

Para o Codex, o caminho recomendado e usar hooks como observer passivo. O hook recebe eventos do Codex por JSON, registra atividade local no SQLite e sai rapidamente. Ele nao envia Discord/Telegram diretamente; os alertas continuam sendo enviados pelo monitor.

Isso melhora o Protocolo 2: tarefas longas nao precisam depender apenas de `touch` manual, desde que o Codex gere eventos de prompt, ferramenta ou turno.

### Configurar `.env`

Exemplo para Protocolo 2:

```env
PRESENCE_DEFAULT_PROTOCOL=protocol2
PRESENCE_CODEX_WORKER_ID=seu-computador:codex
PRESENCE_CODEX_AI_NAME=codex
PRESENCE_CODEX_PROTOCOL=protocol2
PRESENCE_CODEX_TASK=
PRESENCE_CODEX_WORKER_SCOPE=project
PRESENCE_CODEX_AUTO_START=false
PRESENCE_CODEX_HOOK_FAIL_CLOSED=false
```

Por padrao, `PRESENCE_CODEX_AUTO_START=false`. Isso significa que o hook so registra atividade quando o worker ja esta ativo. Use `start` e `finish` como marcos publicos:

```bash
python3 -m ai_presence_monitor start --ai codex --protocol protocol2 --task "tarefa-longa"
# o hook registra atividade silenciosa enquanto o Codex trabalha
python3 -m ai_presence_monitor finish --ai codex --protocol protocol2 --task "tarefa-longa"
```

Se quiser que qualquer evento do Codex crie/reative o worker automaticamente:

```env
PRESENCE_CODEX_AUTO_START=true
```

Com `PRESENCE_CODEX_WORKER_SCOPE=project`, execute `start` e `finish` dentro da
raiz do projeto. O hook usa o `cwd` recebido do Codex para chegar ao mesmo worker.
Os outros escopos sao `global`, `session` e `project-session`.

### Diagnosticar a inatividade atual

Depois de coletar evidencias para um worker ativo, execute primeiro o dry-run e
informe a sessao exata quando puder existir evidencia de mais de uma sessao:

```bash
ai-presence --dry-run diagnose \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --json

ai-presence diagnose \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA
```

A severidade vem do relogio do protocolo do worker. O comando registra um fato
limitado desse relogio, um diagnostico imutavel e abre, atualiza ou resolve o
unico incidente do worker. Ele nao envia Discord/Telegram, nao toca alarme, nao
envia input ao Codex e nao executa retry ou recuperacao.

### Notificar o incidente diagnostico atual

Revise primeiro sem rede e sem criar registro de entrega:

```bash
ai-presence --dry-run notify-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --json
```

Sem `--dry-run`, amarelo e laranja usam `DISCORD_ALERT_WEBHOOK_URL`; vermelho
usa `DISCORD_RED_WEBHOOK_URL` quando configurado e, do contrario, usa o webhook
de alerta. A chave semantica combina incidente, causa, confianca e severidade.
Um novo UUID com o mesmo significado nao envia novamente; mudanca de causa,
confianca ou severidade pode enviar uma nova mensagem uma unica vez.

O registro e reservado antes do HTTP. Somente sucesso confirmado atualiza
`last_notified_at`. Rejeicao, resultado incerto ou interrupcao ficam registrados
sem retry automatico. Esse fluxo nao usa Telegram, alarme, telefone, input do
Codex ou recuperacao.

### Recuperar um incidente diagnostico elegivel

Primeiro avalie a elegibilidade sem reservar tentativa nem enviar input:

```bash
ai-presence --dry-run recover-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --json
```

A tentativa real envia um unico `continue` local por `codex queue` para a
sessao exata persistida no incidente e exige autorizacao desta invocacao:

```bash
ai-presence recover-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --authorize-once \
  --json
```

Somente `codex_closed` com confianca media/alta e `codex_crashed` com confianca
alta sao elegiveis. O worker deve estar ativo, o diagnostico atual deve estar
valido e a notificacao Discord do mesmo evento semantico deve estar confirmada.
A reserva ocorre antes do envio e qualquer tentativa reservada bloqueia novo
despacho para o mesmo incidente, inclusive apos resultado incerto ou
interrupcao. O comando nao usa GUI ou transporte remoto, nao atualiza os
relogios de presenca e nao resolve o incidente. Um hook posterior e novo
diagnostico devem comprovar a retomada. O E2E real da release Linux privada
0.8.0 confirmou um marcador unico, um despacho nativo, relogio isolado
inalterado e hook posterior da sessao exata.

### Instalar hook no Codex

Use [examples/codex/hooks.json](examples/codex/hooks.json) como base. Copie as entradas para `~/.codex/hooks.json` ou para o `.codex/hooks.json` do projeto que o Codex esta usando.

Depois, no Codex, use `/hooks` para revisar e confiar no hook. Hooks nao gerenciados precisam ser revisados/confiados quando sao novos ou mudam.

Instalacao automatica com backup/idempotencia:

```bash
python3 -m ai_presence_monitor install-codex-hook
```

Teste sem escrever:

```bash
python3 -m ai_presence_monitor --dry-run install-codex-hook
```

Remover o hook:

```bash
python3 -m ai_presence_monitor uninstall-codex-hook
```

O instalador preserva hooks de terceiros e remove/substitui tanto hooks antigos
que apontam para `codex_presence_hook.py` quanto hooks novos baseados no modulo
instalado.

### Monitor continuo

O comando portatil escolhe systemd no Linux e Task Scheduler no Windows:

```bash
ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor
```

No Windows, a tarefa `AI Presence Monitor` e registrada para o usuario atual no
logon. Para iniciar imediatamente:

```powershell
schtasks.exe /Run /TN "AI Presence Monitor"
```

Para remover em qualquer plataforma:

```bash
ai-presence uninstall-background-service --component monitor
```

Comandos legados especificos do Linux continuam disponiveis. Depois de instalar
o pacote, gere um servico systemd de usuario:

```bash
ai-presence --dry-run install-systemd-service
ai-presence install-systemd-service
systemctl --user daemon-reload
systemctl --user enable --now ai-presence-monitor.service
```

### Testar hook manualmente

```bash
printf '%s\n' '{"hook_event_name":"PostToolUse","tool_name":"Bash","session_id":"teste","cwd":"/tmp/projeto"}' \
  | python3 -m ai_presence_monitor codex-hook --verbose
```

### Limites

- O hook prova eventos do Codex, nao qualidade do trabalho.
- Se o Codex ficar muito tempo sem gerar eventos, o monitor ainda pode alertar.
- Um comando muito longo pode gerar `PreToolUse` no inicio e `PostToolUse` so no fim; nesse intervalo, o sistema ainda pode interpretar ausencia de eventos como risco. Observers adicionais de processo/workspace podem ser adicionados depois.

## Alerta vermelho com alarme ou telefonema

O Discord e o Telegram enviam mensagens, mas telefonema real exige um provedor externo. O monitor deixa dois caminhos:

O alerta vermelho, incluindo sua mensagem e escalada externa, ocorre uma unica
vez enquanto a IA permanecer continuamente inativa. `start`, `heartbeat`,
`touch` ou uma observacao valida do Codex rearma um futuro alerta vermelho.

- `RED_NOTIFICATION_MODE=alarm` executa `RED_ALERT_COMMAND`, por exemplo `paplay` com um som local.
- `RED_NOTIFICATION_MODE=phone` envia um JSON para `PHONE_WEBHOOK_URL`, que pode apontar para Twilio, Make, Zapier ou n8n.

Exemplo de alarme local:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
```

Exemplo Windows:

```env
RED_ALERT_COMMAND=ffplay.exe -nodisp -loop 0 "C:\Sounds\alarm.mp3"
```

Cada episodio vermelho inicia o som uma vez, por no maximo 15 segundos. Linux
usa GNU `timeout`; Windows usa um runner Python e encerra a arvore controlada
com `taskkill`. O limite e aplicado mesmo a um `ffplay -loop 0`. Ajuste
`RED_ALERT_MAX_DURATION_SECONDS` para outra duracao positiva. Para interromper
antes do limite:

```bash
ai-presence stop-alarm
```

O menu interativo oferece a mesma operacao na opcao 19.

Exemplo de telefonia por webhook externo:

```env
RED_NOTIFICATION_MODE=phone
PHONE_WEBHOOK_URL=https://seu-servico-de-telefonia.example/webhook
```

## Teste sem enviar mensagens

Use `--dry-run` para ver os payloads sem chamar Discord/Telegram:

```bash
ai-presence --dry-run heartbeat --ai codex --message "teste"
ai-presence --dry-run monitor --once
ai-presence --dry-run continue --worker worker-id --window-title 'Codex'
```

## Desenvolvimento

O codigo do pacote fica em `src/ai_presence_monitor`. Para executar o gate
local:

```bash
python3 -m pip install -e '.[dev]'
./scripts/quality-check.sh
```
