# Como Preencher o `.env`

Este documento e um guia pratico para preencher o `.env` do AI Presence Monitor. Para a explicacao completa do funcionamento interno, veja `docs/ENVIRONMENT-GUIDE.md`.

## Passo Inicial

Crie o arquivo real a partir do modelo:

```bash
cp .env.example .env
```

Depois edite apenas o `.env`. O `.env.example` deve continuar sem segredos.

## Plataforma Suportada

Linux funciona sem configuracao adicional. Nesta release, preserve:

```env
PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false
```

O codigo Windows nao foi removido. Para desenvolvimento controlado em uma
maquina Windows, altere a copia local para `true`. Isso libera os adaptadores
Win32, Task Scheduler e alarme Windows, mas nao os torna parte do suporte
estavel da release. Mesmo `--dry-run` exige o opt-in.

Com `false`, comandos de diagnostico, `finish`, `stop-alarm`, controles de
desabilitacao e desinstaladores continuam disponiveis para recuperacao.

## Campos Obrigatorios para Discord

Para receber mensagens reais no Discord, preencha:

```env
DISCORD_POINT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Use dois webhooks diferentes, um para o canal de ponto e outro para o canal de alertas. O Discord cria cada webhook dentro de um canal especifico.

## Campos Recomendados para Codex

Para o Codex GUI, a configuracao recomendada e:

```env
PRESENCE_DB_PATH=./data/presence.db
PRESENCE_DEFAULT_PROTOCOL=protocol2
PRESENCE_MONITOR_INTERVAL_SECONDS=30
PRESENCE_WORK_WINDOW_ENABLED=true
PRESENCE_WORK_WINDOW_START=13:00
PRESENCE_WORK_WINDOW_END=18:00
PRESENCE_WORK_WINDOW_TIMEZONE=America/Sao_Paulo
PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR=suppress_alerts
PRESENCE_ALERT_REPEAT_ENABLED=true
PRESENCE_ALERT_REPEAT_SECONDS=300
PRESENCE_ALERT_REPEAT_LEVELS=yellow,orange
PRESENCE_CODEX_AI_NAME=codex
PRESENCE_CODEX_PROTOCOL=protocol2
PRESENCE_CODEX_TASK=
PRESENCE_CODEX_WORKER_SCOPE=project
PRESENCE_CODEX_AUTO_START=false
PRESENCE_CODEX_HOOK_FAIL_CLOSED=false
```

Desde a versao 0.2.0, um caminho relativo em `PRESENCE_DB_PATH` e resolvido em
relacao ao diretorio do `.env`. Portanto, hooks executados em outros diretorios
continuam usando o mesmo banco.

## Expediente e Repeticao de Alertas

Para cobrar presenca apenas durante um horario de trabalho, ative:

```env
PRESENCE_WORK_WINDOW_ENABLED=true
PRESENCE_WORK_WINDOW_START=13:00
PRESENCE_WORK_WINDOW_END=18:00
PRESENCE_WORK_WINDOW_TIMEZONE=America/Sao_Paulo
PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR=suppress_alerts
```

Com essa configuracao, o monitor envia alertas entre `13:00` e `18:00`. Fora desse intervalo, ele nao envia novos alertas.

Para continuar cobrando enquanto o worker estiver atrasado dentro do expediente:

```env
PRESENCE_ALERT_REPEAT_ENABLED=true
PRESENCE_ALERT_REPEAT_SECONDS=300
PRESENCE_ALERT_REPEAT_LEVELS=yellow,orange
```

Isso repete alertas amarelos e laranjas a cada 300 segundos, desde que o worker
continue ativo e atrasado. O vermelho e sempre unico por episodio continuo de
inatividade, mesmo se uma configuracao antiga ainda listar `red`. Nova atividade
valida rearma o vermelho.

Se voce quiser que o monitor alerte em qualquer horario, deixe:

```env
PRESENCE_WORK_WINDOW_ENABLED=false
```

## Nome do Computador e Worker

`PRESENCE_COMPUTER_NAME` aparece nas mensagens. Se ficar vazio, o programa usa o hostname do sistema.

`PRESENCE_CODEX_WORKER_ID` pode ficar vazio. Nesse caso, o worker sera derivado assim:

```text
<PRESENCE_COMPUTER_NAME ou hostname>:<PRESENCE_CODEX_AI_NAME>
```

Preencha `PRESENCE_CODEX_WORKER_ID` somente se quiser fixar manualmente o identificador, por exemplo:

```env
PRESENCE_CODEX_WORKER_ID=notebook-josue:codex
```

O valor funciona como identidade base. O escopo pode adicionar projeto e sessao:

```env
PRESENCE_CODEX_WORKER_SCOPE=project
```

Use `project` para separar repositorios. Os valores aceitos sao `global`,
`project`, `session` e `project-session`. Consulte `docs/PORTABILIDADE.md` para
os detalhes.

## Telegram

Telegram e opcional. Para ativar, preencha os dois campos:

```env
TELEGRAM_BOT_TOKEN=token-do-bot
TELEGRAM_CHAT_ID=id-do-chat
```

Se apenas um dos dois estiver preenchido, o Telegram fica desativado pelo codigo. Nesse caso, escolha uma das duas opcoes:

- preencher o campo que falta;
- deixar os dois campos vazios.

## Respostas Remotas pelo Discord

Esse recurso exige um bot alem do webhook. A configuracao recomendada devolve
a resposta para a sessao exata do Codex sem controlar mouse ou teclado:

```env
PRESENCE_REMOTE_QUESTIONS_ENABLED=true
DISCORD_QUESTION_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=token-do-bot
DISCORD_QUESTION_CHANNEL_ID=id-numerico-do-canal
DISCORD_ALLOWED_USER_IDS=id-numerico-do-usuario
PRESENCE_QUESTION_POLL_INTERVAL_SECONDS=5
PRESENCE_QUESTION_TIMEOUT_SECONDS=1800
PRESENCE_QUESTION_ANSWER_TRANSPORT=native
PRESENCE_QUESTION_ANSWER_DESTINATION=local
PRESENCE_QUESTION_SESSION_MAX_AGE_SECONDS=300

PRESENCE_GUI_ANSWER_ENABLED=false
PRESENCE_CODEX_GUI_WINDOW_TITLE=
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS=120
```

O bot deve ter `View Channel`, `Read Message History` e **Message Content
Intent**. Crie o bot somente no Discord Developer Portal oficial. O passo a
passo, os testes em duas fases e o rollback estao em
`docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md`.

`native` usa `codex queue`, exige `PRESENCE_NATIVE_INPUT_ENABLED=true` e vincula
a pergunta a uma sessao antes de publica-la. A ordem de resolucao e:

1. `--thread` explicito;
2. `CODEX_SESSION_ID` ou `CODEX_THREAD_ID` do processo que pergunta;
3. alvo persistido por `ai-presence control target --thread ...`;
4. uma unica sessao do mesmo worker observada por hook nos ultimos
   `PRESENCE_QUESTION_SESSION_MAX_AGE_SECONDS`.

Zero ou mais de uma sessao recente causa falha fechada. Use `store` para apenas
registrar a resposta ou `gui` para o fallback explicito. Ative
`PRESENCE_GUI_ANSWER_ENABLED=true` somente quando escolher `gui` e depois de
validar a correlacao Discord sem entrada automatica.

`PRESENCE_QUESTION_ANSWER_DESTINATION=client` usa o endpoint remoto e exige
`PRESENCE_REMOTE_INPUT_ENABLED=true`. O endpoint e o nome da variavel de token
sao congelados na pergunta; o valor do token nunca entra no banco.

## Continue Integrado

O envio de continuidade prefere a sessao nativa do Codex e deixa a GUI como
fallback opcional:

```env
PRESENCE_CONTINUE_MESSAGE=continue
PRESENCE_CONTINUE_DELAY_SECONDS=60
PRESENCE_CONTINUE_SYNC_ACTIVITY=true
PRESENCE_CONTROL_PATH=
PRESENCE_TASK_AUTOMATION_ENABLED=false
PRESENCE_NATIVE_INPUT_ENABLED=true
PRESENCE_GUI_FALLBACK_ENABLED=false
PRESENCE_REMOTE_INPUT_ENABLED=false
PRESENCE_CONTINUE_TRANSPORT=auto
PRESENCE_CONTINUE_DESTINATION=local
PRESENCE_CODEX_THREAD_ID=
PRESENCE_CODEX_REMOTE=
PRESENCE_CODEX_REMOTE_AUTH_TOKEN_ENV=CODEX_REMOTE_AUTH_TOKEN
CODEX_REMOTE_AUTH_TOKEN=
```

`PRESENCE_CONTROL_PATH` aponta para o estado alterado pela bandeja/CLI. Vazio,
usa `~/.local/state/ai-presence-monitor/control.json` no Linux ou
`%LOCALAPPDATA%\ai-presence-monitor\control.json` no Windows, sempre fora do
checkout. Um caminho relativo explicito e resolvido a partir do `.env`. Quando
esse JSON existe, ele prevalece sobre os defaults do `.env`.

`PRESENCE_TASK_AUTOMATION_ENABLED=false` bloqueia `continue` real ate o usuario
habilitar a opcao ou autorizar uma execucao com `--authorize-once`. Habilitar
nao cria timer e nao autoriza presenca artificial.

`PRESENCE_NATIVE_INPUT_ENABLED=true` permite `codex queue`.
`PRESENCE_GUI_FALLBACK_ENABLED=false` impede uso acidental de mouse/teclado.
`PRESENCE_REMOTE_INPUT_ENABLED=false` bloqueia o computador cliente.

`PRESENCE_CONTINUE_TRANSPORT=auto` prefere o nativo. `native` ou `gui` forcam
uma familia, desde que o respectivo gate esteja habilitado.

`PRESENCE_CONTINUE_DESTINATION=local` impede que apenas salvar um endpoint
remoto mude o destino. Use `client` somente quando quiser enviar ao computador
cliente e o gate remoto estiver ativo.

`PRESENCE_CODEX_THREAD_ID` recebe UUID ou nome exato da sessao. `continue` pode
inferir esse valor do hook do mesmo worker; `send-input` e o compositor exigem
um valor explicito ou persistido.

`PRESENCE_CODEX_REMOTE` recebe o endpoint autenticado do app-server.
`PRESENCE_CODEX_REMOTE_AUTH_TOKEN_ENV` guarda apenas o nome da variavel, e
`CODEX_REMOTE_AUTH_TOKEN` guarda o valor secreto no `.env` real.

Com sincronizacao ativa, somente um transporte bem-sucedido atualiza
`last_activity_at` de um worker ja ativo. O Protocolo 1 preserva
`last_signal_at`. Consulte `docs/CONTINUE-CODEX.md` e
`docs/SYSTEM-TRAY-NATIVE-INPUT.md`.

## Alerta Vermelho

Modo simples, apenas Discord/Telegram:

```env
RED_NOTIFICATION_MODE=none
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=
PHONE_WEBHOOK_URL=
```

Modo alarme local:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
PHONE_WEBHOOK_URL=
```

No Windows, um exemplo equivalente com FFmpeg/ffplay instalado e:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=ffplay.exe -nodisp -loop 0 "C:\Sounds\alarm.mp3"
PHONE_WEBHOOK_URL=
```

Se o caminho do audio contiver espacos, coloque somente o caminho entre aspas.
Por exemplo:

```env
RED_ALERT_COMMAND=ffplay -nodisp -loop 0 "/caminho/com espacos/alarm.mp3"
```

Mesmo com `-loop 0`, o monitor encerra o processo automaticamente depois de
`RED_ALERT_MAX_DURATION_SECONDS`. O valor deve ser maior que zero. Para
interromper antes do limite:

```bash
ai-presence stop-alarm
```

Modo telefonia externa:

```env
RED_NOTIFICATION_MODE=phone
RED_ALERT_COMMAND=
PHONE_WEBHOOK_URL=https://seu-servico.example/webhook
```

O programa nao faz chamada telefonica diretamente. No modo `phone`, ele envia JSON para um servico externo.

## Checklist de Validacao

Antes de usar em producao local, confira:

- `PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false` para a release Linux;
- `PRESENCE_DB_PATH` aponta para o banco esperado;
- `PRESENCE_DEFAULT_PROTOCOL` e `PRESENCE_CODEX_PROTOCOL` usam `protocol1` ou `protocol2`;
- se `PRESENCE_WORK_WINDOW_ENABLED=true`, inicio/fim usam `HH:MM` e o timezone esta correto;
- `PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR` e `suppress_alerts` ou `allow_alerts`;
- se `PRESENCE_ALERT_REPEAT_ENABLED=true`, `PRESENCE_ALERT_REPEAT_SECONDS` e maior que zero;
- `DISCORD_POINT_WEBHOOK_URL` e `DISCORD_ALERT_WEBHOOK_URL` estao preenchidos;
- Telegram esta com os dois campos preenchidos ou os dois vazios;
- `RED_NOTIFICATION_MODE` e `none`, `alarm` ou `phone`;
- `RED_ALERT_MAX_DURATION_SECONDS` e maior que zero;
- se `RED_NOTIFICATION_MODE=alarm`, `RED_ALERT_COMMAND` esta preenchido;
- se `RED_NOTIFICATION_MODE=phone`, `PHONE_WEBHOOK_URL` esta preenchido;
- `PRESENCE_CODEX_AUTO_START=false` se voce quer controle manual por `start` e `finish`;
- `PRESENCE_CODEX_WORKER_SCOPE=project` se varios projetos usam o mesmo monitor;
- `PRESENCE_CODEX_HOOK_FAIL_CLOSED=false` ate confiar totalmente no fluxo.
- se respostas remotas estiverem ativas, webhook, token, canal e allowlist
  estao todos preenchidos;
- `DISCORD_QUESTION_CHANNEL_ID` aponta para o mesmo canal do webhook;
- o bot possui leitura de historico e Message Content Intent;
- `PRESENCE_GUI_ANSWER_ENABLED=false` durante o primeiro teste;
- o titulo configurado encontra exatamente uma janela do Codex.
- `PRESENCE_CONTINUE_MESSAGE` nao esta vazio;
- `PRESENCE_CONTINUE_DELAY_SECONDS` e zero ou maior;
- o worker informado ao comando `continue` ja esta ativo, caso a sincronizacao
  esteja ligada.

## Comandos de Teste

Ver o estado carregado:

```bash
python3 -m ai_presence_monitor status
```

Rodar uma checagem sem enviar mensagens:

```bash
python3 -m ai_presence_monitor --dry-run monitor --once
```

Testar uma mensagem de ponto sem envio real:

```bash
python3 -m ai_presence_monitor --dry-run heartbeat --ai codex --protocol protocol2 --message "teste"
```

Instalar hooks do Codex sem escrever:

```bash
python3 -m ai_presence_monitor --dry-run install-codex-hook
```

Testar os comandos remotos sem rede, banco ou GUI:

```bash
python3 -m ai_presence_monitor --dry-run ask-user \
  --worker teste:codex \
  --question "Pergunta de teste"
python3 -m ai_presence_monitor --dry-run observe-replies --once
```

Testar o fluxo integrado sem espera, GUI ou banco:

```bash
ai-presence --dry-run continue \
  --worker ID_EXATO_DO_WORKER \
  --window-title Codex
```

## Cuidados

- Nao publique webhooks, tokens ou URLs privadas.
- Nao commit o `.env`.
- Use `.env.example` apenas como modelo sem segredos.
- Depois de instalar hooks do Codex, revise e confie neles com `/hooks`.
- Para instalacao em outro computador, siga `docs/PORTABILIDADE.md`.
