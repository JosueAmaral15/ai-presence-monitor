# Guia de Configuracao do `.env`

Este guia explica quais dados o usuario precisa preencher para usar o AI Presence Monitor em monitoramento real, principalmente com Discord, Telegram e Codex.

## Visao Geral

O arquivo `.env` guarda configuracoes locais e segredos. Ele controla:

- onde o banco SQLite fica;
- qual protocolo sera usado por padrao;
- quais canais recebem mensagens de ponto e alerta;
- como o alerta vermelho deve escalar;
- como o observer do Codex registra atividade.

O `.env` real nao deve ser compartilhado nem commitado. Use `.env.example` como modelo.

Desde a versao 0.2.0, a configuracao e procurada nesta ordem:

1. caminho passado por `--env-file`;
2. variavel `PRESENCE_ENV_FILE`;
3. `.ai-presence-monitor.env` existente no diretorio atual;
4. no Linux, `$XDG_CONFIG_HOME/ai-presence-monitor/.env` ou
   `~/.config/ai-presence-monitor/.env`;
5. no Windows, `%APPDATA%\ai-presence-monitor\.env`.

O `.env` comum no diretorio atual e reconhecido automaticamente apenas dentro
do checkout do proprio AI Presence Monitor. Essa compatibilidade evita que a
ferramenta leia por engano o `.env` de outra aplicacao.

## Politica de Plataforma

Linux e a plataforma operacional suportada na versao 0.6.2. O codigo Windows
permanece instalado, mas o runtime e desabilitado por padrao:

```env
PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=false
```

Use `true` somente para desenvolvimento controlado no Windows. O opt-in libera
os adaptadores existentes, sem declarar suporte estavel. `--dry-run` nao
contorna essa politica. Ajuda, diagnostico, encerramento de worker, parada de
alarme e desinstalacao continuam disponiveis com o valor `false`.

Para instalar e reutilizar em outros projetos ou computadores, consulte
`docs/PORTABILIDADE.md`.

```bash
cp .env.example .env
```

Depois edite `.env` com seus valores.

## Como Funciona na Pratica

O AI Presence Monitor tem quatro partes principais:

- comandos de registro: `start`, `heartbeat`, `touch` e `finish`;
- banco local SQLite, configurado por `PRESENCE_DB_PATH`;
- monitor de atraso, executado por `python3 -m ai_presence_monitor monitor`;
- notificadores, que enviam mensagens para Discord, Telegram e escalonamentos vermelhos.

Os comandos gravam eventos no banco SQLite. O monitor le esse banco em ciclos e verifica apenas workers com `status=active`. Quando encontra atraso suficiente, ele envia um alerta e grava esse alerta no banco para evitar repetir o mesmo nivel indefinidamente.

O monitor nao roda sozinho depois de um `start`. Para alertas reais, mantenha
este comando aberto em outro terminal ou instale a execucao continua com
`install-background-service`, que usa systemd no Linux e Task Scheduler no
Windows:

```bash
python3 -m ai_presence_monitor monitor
```

Para uma checagem unica:

```bash
python3 -m ai_presence_monitor monitor --once
```

Se a janela de expediente estiver ativada, o monitor so cobra alertas dentro do horario configurado. Isso fica fora dos protocolos: Protocolo 1 e Protocolo 2 continuam definindo o que conta como atraso; a janela de expediente define quando esse atraso deve ser cobrado.

### O Que Cada Comando Faz

`start` marca o worker como ativo, registra inicio de tarefa e posta no canal de ponto.

`heartbeat` registra uma sinalizacao publica. No Protocolo 1, este e o sinal esperado a cada 5 minutos.

`touch` registra atividade interna sem postar no Discord por padrao. No Protocolo 2, este e o sinal silencioso usado para demonstrar que a IA ainda esta ativa durante uma tarefa longa. Use `--notify` se quiser que o `touch` tambem apareca no canal de ponto.

`finish` marca o worker como `idle`, limpa a tarefa atual e posta fim de tarefa. Workers `idle` nao geram novos alertas de atraso.

### Como os Protocolos Calculam Atraso

No Protocolo 1, o relogio monitorado e `last_signal_at`.

Isso significa que o sistema espera sinal publico. Se a IA nao fizer `heartbeat` dentro dos limites, o monitor escala:

- amarelo depois de 7 minutos;
- laranja depois de 15 minutos;
- vermelho depois de 30 minutos.

No Protocolo 2, o relogio monitorado e `last_activity_at`.

Isso significa que uma tarefa pode durar mais de 15 minutos sem problema, desde que exista atividade registrada. Essa atividade pode vir de `touch` manual ou de hooks do Codex. O alerta vermelho so acontece se o worker ativo ficar sem atividade por 15 minutos.

Limites do Protocolo 2:

- amarelo depois de 5 minutos sem atividade;
- laranja depois de 10 minutos sem atividade;
- vermelho depois de 15 minutos sem atividade.

### O Papel do Hook do Codex

O hook do Codex nao envia Discord nem Telegram diretamente. Ele funciona como observer local:

1. O Codex dispara um evento de hook.
2. O hook recebe um JSON pelo `stdin`.
3. O AI Presence Monitor extrai metadados seguros, como evento, sessao, ferramenta e `cwd`.
4. O hook grava uma observacao no SQLite.
5. O monitor, rodando separadamente, decide se ha atraso e envia alertas.

Com `PRESENCE_CODEX_AUTO_START=false`, o hook so atualiza um worker que ja esteja ativo. Esse e o modo recomendado, porque preserva o controle manual de inicio e fim:

```bash
python3 -m ai_presence_monitor start --ai codex --protocol protocol2 --task "tarefa-longa"
# Codex trabalha; os hooks registram atividade silenciosa.
python3 -m ai_presence_monitor finish --ai codex --protocol protocol2 --task "tarefa-longa"
```

Com `PRESENCE_CODEX_AUTO_START=true`, qualquer evento do Codex pode criar ou reativar um worker automaticamente. Isso e mais automatico, mas tambem pode registrar como tarefa ativa uma sessao que o usuario nao pretendia monitorar.

### O Que Fica Salvo no SQLite

O banco local guarda:

- `workers`: estado atual de cada computador/IA;
- `events`: historico de inicio, ponto, toque, fim e observacoes;
- `alerts`: historico de alertas enviados.

Isso permite consultar `status`, evitar repeticao de alertas no mesmo nivel e manter uma trilha local do que aconteceu.

### O Que o Sistema Prova

O sistema prova que houve evento registrado: comando manual, `touch`, `heartbeat`, `start`, `finish` ou evento observado do Codex.

Ele nao prova qualidade do trabalho, acerto da implementacao ou conclusao real da tarefa. Para isso ainda e necessario validar artefatos, testes, logs, diffs e resultados do proprio projeto.

## Configuracoes Minimas

Para monitoramento real por Discord, os campos essenciais sao:

```env
PRESENCE_DB_PATH=./presence.db
PRESENCE_DEFAULT_PROTOCOL=protocol2
PRESENCE_COMPUTER_NAME=notebook-josue
DISCORD_POINT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### `PRESENCE_DB_PATH`

Caminho do banco SQLite local.

Recomendacao:

- use um caminho relativo ao `.env` para manter a configuracao portatil;
- use um caminho absoluto apenas quando quiser apontar para um local externo.

Exemplo recomendado:

```env
PRESENCE_DB_PATH=./data/presence.db
```

Desde a versao 0.2.0, o caminho relativo e resolvido a partir do diretorio do
arquivo `.env`, nao do `cwd` do processo ou do hook.

### `PRESENCE_DEFAULT_PROTOCOL`

Define o protocolo usado quando o comando nao passa `--protocol`.

Valores:

- `protocol1`: ponto publico continuo a cada 5 minutos;
- `protocol2`: inicio/fim publicos e atividade silenciosa durante a tarefa.

Recomendacao para Codex:

```env
PRESENCE_DEFAULT_PROTOCOL=protocol2
```

### `PRESENCE_COMPUTER_NAME`

Nome do computador exibido nos alertas.

Exemplos:

```env
PRESENCE_COMPUTER_NAME=notebook-josue
PRESENCE_COMPUTER_NAME=desktop-lab
PRESENCE_COMPUTER_NAME=servidor-gpu-01
```

Se ficar vazio, o sistema usa o hostname do sistema operacional.

### `PRESENCE_MONITOR_INTERVAL_SECONDS`

Intervalo, em segundos, entre verificacoes do monitor.

Exemplo:

```env
PRESENCE_MONITOR_INTERVAL_SECONDS=30
```

Este valor nao muda os limites dos protocolos. Ele so define de quanto em quanto tempo o daemon verifica atrasos.

## Janela de Expediente

Essas variaveis definem quando o monitor deve cobrar presenca.

```env
PRESENCE_WORK_WINDOW_ENABLED=true
PRESENCE_WORK_WINDOW_START=13:00
PRESENCE_WORK_WINDOW_END=18:00
PRESENCE_WORK_WINDOW_TIMEZONE=America/Sao_Paulo
PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR=suppress_alerts
```

Com `PRESENCE_WORK_WINDOW_ENABLED=true`, o monitor verifica se o horario atual esta dentro da janela.

`PRESENCE_WORK_WINDOW_START` e `PRESENCE_WORK_WINDOW_END` usam formato `HH:MM`. Se o inicio for maior que o fim, o sistema entende como janela que passa da meia-noite, por exemplo `22:00` ate `06:00`.

`PRESENCE_WORK_WINDOW_TIMEZONE` deve ser um timezone valido do sistema, como `America/Sao_Paulo`.

`PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR` aceita:

- `suppress_alerts`: nao envia novos alertas fora do expediente;
- `allow_alerts`: permite alertas mesmo fora do expediente.

## Repeticao de Alertas

Por padrao, o monitor evita repetir o mesmo nivel de alerta indefinidamente. Para continuar avisando enquanto o worker estiver atrasado dentro do expediente, use:

```env
PRESENCE_ALERT_REPEAT_ENABLED=true
PRESENCE_ALERT_REPEAT_SECONDS=300
PRESENCE_ALERT_REPEAT_LEVELS=yellow,orange
```

Com isso, se o worker continuar ativo e atrasado, amarelo e laranja podem ser
reenviados a cada 300 segundos. Uma nova atividade (`touch`, `heartbeat`,
`start` ou observacao do Codex) limpa o ultimo alerta e reinicia a contagem.

O vermelho e enviado uma unica vez por episodio continuo de inatividade. Ciclos
posteriores nao reenviam Discord, Telegram, alarme local nem telefonia. Uma nova
atividade valida rearma o vermelho para um futuro episodio.

## Discord

O Discord usa webhooks por canal. Cada URL aponta para um canal especifico.

### `DISCORD_POINT_WEBHOOK_URL`

Canal de ponto.

Recebe mensagens como:

- inicio de tarefa;
- ponto de atividade;
- fim de tarefa;
- `touch` quando o usuario pede para notificar.

Exemplo:

```env
DISCORD_POINT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### `DISCORD_ALERT_WEBHOOK_URL`

Canal de alertas.

Recebe:

- alerta amarelo;
- alerta laranja;
- alerta vermelho, se nao houver webhook vermelho dedicado.

Exemplo:

```env
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### `DISCORD_RED_WEBHOOK_URL`

Opcional. Canal exclusivo para alertas vermelhos.

Use se quiser separar incidentes graves dos alertas normais.

```env
DISCORD_RED_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## Telegram Opcional

O Telegram pode receber os mesmos avisos que o Discord.

### `TELEGRAM_BOT_TOKEN`

Token do bot criado no BotFather.

```env
TELEGRAM_BOT_TOKEN=123456:token...
```

### `TELEGRAM_CHAT_ID`

ID do chat, grupo ou canal onde o bot deve enviar mensagens.

```env
TELEGRAM_CHAT_ID=123456789
```

Se qualquer um dos dois estiver vazio, o Telegram fica desativado.

## Perguntas e Respostas Remotas

O fluxo de perguntas usa um canal dedicado do Discord. Um webhook publica a
pergunta e um bot le respostas pelo endpoint REST de mensagens.

```env
PRESENCE_REMOTE_QUESTIONS_ENABLED=false
DISCORD_QUESTION_WEBHOOK_URL=
DISCORD_BOT_TOKEN=
DISCORD_QUESTION_CHANNEL_ID=
DISCORD_ALLOWED_USER_IDS=
PRESENCE_QUESTION_POLL_INTERVAL_SECONDS=5
PRESENCE_QUESTION_TIMEOUT_SECONDS=1800

PRESENCE_GUI_ANSWER_ENABLED=false
PRESENCE_CODEX_GUI_WINDOW_TITLE=
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS=120
```

`PRESENCE_REMOTE_QUESTIONS_ENABLED` libera publicacao e leitura. Os quatro
campos Discord sao obrigatorios quando ele esta ativo.

`DISCORD_ALLOWED_USER_IDS` recebe IDs numericos separados por virgula. Somente
uma mensagem do autor permitido que use **Responder** na pergunta original e
aceita.

`PRESENCE_GUI_ANSWER_ENABLED` e um segundo bloqueio. Quando `false`, a resposta
fica no SQLite como `answered`; nenhum controle de GUI acontece.

Quando `true`, `PRESENCE_CODEX_GUI_WINDOW_TITLE` deve identificar uma unica
janela visivel. As proporcoes X/Y definem o clique dentro da janela. O alvo e
salvo por ID e titulo e revalidado antes de escrever o texto e pressionar
Enter. Linux usa X11 com `xdotool`/`xclip`; Windows usa Win32 e `SendInput`.

O observer continuo e separado do monitor de alertas:

```bash
python3 -m ai_presence_monitor observe-replies
```

Consulte o procedimento completo em
`docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md`.

## Automacao Local de Continue

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

`PRESENCE_CONTINUE_MESSAGE` define o texto usado quando `--message` nao e
informado. `PRESENCE_CONTINUE_DELAY_SECONDS` define a espera antes da emissao.

Com `PRESENCE_CONTINUE_SYNC_ACTIVITY=true`, uma emissao bem-sucedida
registra `observation:automation:continue` para um worker existente e ativo. No
Protocolo 2, isso atualiza `last_activity_at` e reinicia os limites 5/10/15
minutos. Sem atividade posterior, os alertas retornam normalmente. No Protocolo
1, `last_signal_at` nao muda.

Agendamento, `dry-run`, falha de transporte e worker inativo nao atualizam o
monitor. `auto` prefere `codex queue`; o fallback GUI precisa ser habilitado.
`control.json` fica na area de estado do usuario quando
`PRESENCE_CONTROL_PATH` esta vazio, guarda a decisao atual da bandeja/CLI e nao
guarda token. O guia
completo esta em `docs/CONTINUE-CODEX.md` e
`docs/SYSTEM-TRAY-NATIVE-INPUT.md`.

## Alerta Vermelho

O alerta vermelho pode apenas mandar mensagem ou escalar para alarme/telefonema.

### `RED_NOTIFICATION_MODE`

Valores:

- `none`: nao faz acao extra alem de Discord/Telegram;
- `alarm`: executa um comando local de som;
- `phone`: chama um webhook externo para telefonia.

Exemplos:

```env
RED_NOTIFICATION_MODE=none
```

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
```

```env
RED_NOTIFICATION_MODE=phone
PHONE_WEBHOOK_URL=https://seu-servico-de-telefonia.example/webhook
```

### `RED_ALERT_COMMAND`

Comando local executado quando `RED_NOTIFICATION_MODE=alarm`.

Exemplo Linux:

```env
RED_ALERT_COMMAND=paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
```

Use comandos simples e seguros. Evite comandos destrutivos.

Exemplo Windows com FFmpeg/ffplay instalado:

```env
RED_ALERT_COMMAND=ffplay.exe -nodisp -loop 0 "C:\Sounds\alarm.mp3"
```

`RED_ALERT_MAX_DURATION_SECONDS` limita obrigatoriamente a execucao local. O
padrao e 15 segundos. Mesmo se `RED_ALERT_COMMAND` usar um loop continuo, o
backend da plataforma encerra a arvore ao atingir esse limite. Linux usa GNU
`timeout` e `/proc`; Windows usa um runner dedicado, identidade nativa de
processo e `taskkill /T /F`. O valor precisa ser positivo.

O monitor registra PID, fingerprint do comando e identidade do processo em:

```text
~/.local/state/ai-presence-monitor/red-alarm.json
```

No Windows, o estado fica em
`%LOCALAPPDATA%\ai-presence-monitor\state\red-alarm.json`.

O arquivo possui permissao `600` e nao contem o comando em texto. Se um alarme
ja estiver ativo, um novo processo nao e iniciado. Para interromper:

```bash
ai-presence stop-alarm
```

No Linux, o comando envia `SIGTERM`, aguarda tres segundos e usa `SIGKILL`
somente se o processo continuar ativo. Use `--no-force` para desativar o
fallback. No Windows, a arvore dedicada e encerrada imediatamente por
`taskkill /T /F`:

```bash
ai-presence stop-alarm --no-force
```

### `PHONE_WEBHOOK_URL`

Webhook de telefonia quando `RED_NOTIFICATION_MODE=phone`.

O AI Presence Monitor nao faz ligacao por conta propria. Ele envia JSON para um servico externo como Twilio, Make, Zapier ou n8n.

## Observer do Codex

O observer do Codex usa hooks do Codex para registrar atividade silenciosa. Isso ajuda o Protocolo 2 a diferenciar uma tarefa longa de uma IA parada.

Configuracao recomendada:

```env
PRESENCE_CODEX_AI_NAME=codex
PRESENCE_CODEX_PROTOCOL=protocol2
PRESENCE_CODEX_AUTO_START=false
PRESENCE_CODEX_HOOK_FAIL_CLOSED=false
```

### `PRESENCE_CODEX_WORKER_ID`

ID fixo do worker do Codex.

Se ficar vazio, o sistema usa:

```text
<PRESENCE_COMPUTER_NAME>:<PRESENCE_CODEX_AI_NAME>
```

Exemplo:

```env
PRESENCE_CODEX_WORKER_ID=notebook-josue:codex
```

Use um valor fixo quando quiser garantir que todos os eventos do Codex sejam agrupados no mesmo worker.

### `PRESENCE_CODEX_WORKER_SCOPE`

Define como a identidade base e separada:

- `global`: um worker por computador e IA;
- `project`: adiciona o diretorio do projeto, recomendado;
- `session`: adiciona o `session_id` do Codex;
- `project-session`: combina as duas dimensoes.

```env
PRESENCE_CODEX_WORKER_SCOPE=project
```

Em `project`, execute `start` e `finish` a partir da raiz do projeto ou use
`--project /caminho/do/projeto`.

### `PRESENCE_CODEX_AI_NAME`

Nome da IA exibido no status e nos alertas.

```env
PRESENCE_CODEX_AI_NAME=codex
```

### `PRESENCE_CODEX_PROTOCOL`

Protocolo usado pelos eventos observados do Codex.

Recomendado:

```env
PRESENCE_CODEX_PROTOCOL=protocol2
```

### `PRESENCE_CODEX_TASK`

Tarefa padrao usada pelos eventos do hook.

Se ficar vazio, o sistema tenta usar o nome da pasta do `cwd` recebido do Codex.

Exemplo:

```env
PRESENCE_CODEX_TASK=refatoracao-ai-tools
```

### `PRESENCE_CODEX_AUTO_START`

Define se o hook pode criar ou reativar worker sozinho.

Recomendacao:

```env
PRESENCE_CODEX_AUTO_START=false
```

Com `false`, o usuario precisa registrar o inicio:

```bash
python3 -m ai_presence_monitor start --ai codex --protocol protocol2 --task "tarefa-longa"
```

Depois disso, os hooks do Codex podem atualizar atividade silenciosa enquanto o worker estiver ativo.

No fim:

```bash
python3 -m ai_presence_monitor finish --ai codex --protocol protocol2 --task "tarefa-longa"
```

Use `true` somente se quiser que qualquer evento do Codex crie/reative worker automaticamente:

```env
PRESENCE_CODEX_AUTO_START=true
```

Risco do `true`: uma sessao qualquer do Codex pode aparecer como tarefa ativa mesmo sem o usuario ter marcado inicio.

### `PRESENCE_CODEX_HOOK_FAIL_CLOSED`

Define se falha do hook deve retornar erro.

Recomendacao:

```env
PRESENCE_CODEX_HOOK_FAIL_CLOSED=false
```

Com `false`, o hook falha aberto: se houver erro no monitor, ele nao quebra o fluxo do Codex.

Use `true` apenas se quiser enforcement rigido:

```env
PRESENCE_CODEX_HOOK_FAIL_CLOSED=true
```

Risco do `true`: problema no banco ou no `.env` pode atrapalhar execucoes do Codex.

## Como Criar Webhooks no Discord

1. Abra o servidor do Discord.
2. Entre no canal que recebera mensagens.
3. Abra configuracoes do canal.
4. Va em Integracoes.
5. Crie um Webhook.
6. Copie a URL.
7. Cole no `.env`.

Crie pelo menos dois canais:

- canal de ponto;
- canal de alertas.

Opcional:

- canal separado para alerta vermelho.

## Fluxo Recomendado para Codex

1. Configure `.env`.
2. Instale o hook:

```bash
python3 -m ai_presence_monitor install-codex-hook
```

3. No Codex, abra `/hooks`.
4. Revise e confie nas entradas novas.
5. Inicie uma tarefa:

```bash
python3 -m ai_presence_monitor start --ai codex --protocol protocol2 --task "minha-tarefa"
```

6. Rode o monitor em outro terminal:

```bash
python3 -m ai_presence_monitor monitor
```

7. Quando terminar:

```bash
python3 -m ai_presence_monitor finish --ai codex --protocol protocol2 --task "minha-tarefa"
```

## Testar sem Enviar Mensagens

Use `--dry-run`:

```bash
python3 -m ai_presence_monitor --dry-run heartbeat --ai codex --message "teste"
python3 -m ai_presence_monitor --dry-run monitor --once
python3 -m ai_presence_monitor --dry-run install-codex-hook
```

## Modelo Pronto para Codex + Discord

```env
PRESENCE_DB_PATH=./data/presence.db
PRESENCE_DEFAULT_PROTOCOL=protocol2
PRESENCE_COMPUTER_NAME=notebook-josue
PRESENCE_MONITOR_INTERVAL_SECONDS=30
PRESENCE_WORK_WINDOW_ENABLED=true
PRESENCE_WORK_WINDOW_START=13:00
PRESENCE_WORK_WINDOW_END=18:00
PRESENCE_WORK_WINDOW_TIMEZONE=America/Sao_Paulo
PRESENCE_OUTSIDE_WORK_WINDOW_BEHAVIOR=suppress_alerts
PRESENCE_ALERT_REPEAT_ENABLED=true
PRESENCE_ALERT_REPEAT_SECONDS=300
PRESENCE_ALERT_REPEAT_LEVELS=yellow,orange

DISCORD_POINT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_RED_WEBHOOK_URL=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

RED_NOTIFICATION_MODE=none
RED_ALERT_MAX_DURATION_SECONDS=15
RED_ALERT_COMMAND=
PHONE_WEBHOOK_URL=

PRESENCE_CODEX_WORKER_ID=notebook-josue:codex
PRESENCE_CODEX_AI_NAME=codex
PRESENCE_CODEX_PROTOCOL=protocol2
PRESENCE_CODEX_TASK=
PRESENCE_CODEX_WORKER_SCOPE=project
PRESENCE_CODEX_AUTO_START=false
PRESENCE_CODEX_HOOK_FAIL_CLOSED=false

PRESENCE_REMOTE_QUESTIONS_ENABLED=false
DISCORD_QUESTION_WEBHOOK_URL=
DISCORD_BOT_TOKEN=
DISCORD_QUESTION_CHANNEL_ID=
DISCORD_ALLOWED_USER_IDS=
PRESENCE_QUESTION_POLL_INTERVAL_SECONDS=5
PRESENCE_QUESTION_TIMEOUT_SECONDS=1800
PRESENCE_GUI_ANSWER_ENABLED=false
PRESENCE_CODEX_GUI_WINDOW_TITLE=
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS=120
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

## O Que o Usuario Pode Fazer

O usuario pode:

- usar apenas Discord;
- usar Discord + Telegram;
- separar canal de ponto, canal de alerta e canal vermelho;
- escolher se alerta vermelho toca alarme local, chama telefonia externa ou apenas envia mensagem;
- usar Protocolo 1 para ponto publico continuo;
- usar Protocolo 2 para ciclo de tarefa com atividade silenciosa;
- ativar hooks do Codex para registrar atividade automaticamente;
- manter `PRESENCE_CODEX_AUTO_START=false` para controle manual;
- usar `--dry-run` antes de enviar mensagens reais;
- remover os hooks com `uninstall-codex-hook`;
- voltar ao modo manual com `start`, `touch` e `finish`.
- publicar perguntas em canal dedicado do Discord;
- restringir respostas por ID de usuario e referencia;
- manter respostas apenas no SQLite ou entrega-las ao Codex GUI;
- executar o observer em terminal, systemd ou Task Scheduler separado;
- agendar `continue` na mesma CLI e sincronizar uma emissao bem-sucedida com o
  relogio de atividade do Protocolo 2.
- controlar autorizacoes pela bandeja ou CLI e enviar mensagens nativas a uma
  sessao Codex local ou a um app-server autenticado no computador cliente.

## Cuidados

- Nunca publique webhooks, tokens ou URLs privadas.
- Nao commit o `.env`.
- Revise hooks no Codex com `/hooks` depois de instalar.
- Caminhos relativos de `PRESENCE_DB_PATH` sao relativos ao `.env`.
- Use `PRESENCE_CODEX_WORKER_SCOPE=project` para separar projetos.
- Mantenha `PRESENCE_CODEX_HOOK_FAIL_CLOSED=false` ate confiar totalmente no fluxo.
- Lembre que hooks provam eventos do Codex, nao qualidade do trabalho.
