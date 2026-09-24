# AI Presence Monitor como Ferramenta para Humanos e AI-workers

## Objetivo

Este guia explica como um ser humano ou uma inteligencia artificial pode usar
o AI Presence Monitor como ferramenta operacional. Ele cobre:

- registro de inicio, atividade e fim de trabalho;
- monitoramento pelos Protocolos 1 e 2;
- perguntas correlacionadas pelo Discord;
- envio direto de texto a uma sessao Codex sem ocupar mouse ou teclado;
- automacao autorizada da mensagem `continue`;
- interpretacao correta dos estados e das evidencias;
- validacao E2E sem confundir entrada humana com entrada automatizada.

O monitor mede evidencia de atividade. Ele nao prova qualidade, progresso util,
conclusao correta nem autoria de uma mensagem apenas porque um hook ocorreu.

## Modelo Operacional

```text
ser humano ou AI-worker
          |
          +---- ai-presence start/touch/finish
          |
          +---- ai-presence continue/send-input
          |
          +---- bandeja do sistema
          |
          +---- pergunta Discord correlacionada
                         |
                         v
hooks Codex -> SQLite -> protocolos -> alertas Discord/Telegram/alarme
```

Os componentes sao independentes:

| Componente | Responsabilidade |
|---|---|
| CLI `ai-presence` | interface deterministica para humanos, scripts e IAs |
| hooks do Codex | registrar atividade local silenciosa e evidencia diagnostica reconhecida |
| observer de limites | registrar estado sanitizado da conta sem alterar presenca |
| observer Linux | registrar processo, rota local, retomada e servicos selecionados |
| motor de diagnostico | correlacionar fatos atuais e manter um incidente por worker |
| politica de notificacao diagnostica | enviar uma mensagem Discord deduplicada por mudanca semantica |
| monitor | avaliar atrasos e produzir alertas |
| observer Discord | receber respostas correlacionadas de usuarios permitidos |
| `codex queue` | enviar texto para uma sessao sem mouse ou teclado |
| fallback GUI | usar X11/Win32 somente com autorizacao explicita |
| bandeja | alterar permissoes e compor mensagens manualmente |

## Instalacao e Descoberta

Em outro computador Linux, use somente um bundle verificado e siga
[INSTALL-LINUX.md](INSTALL-LINUX.md). O bundle 0.9.0 inclui instalador e
verificador offline; nao instale um artefato com `source_dirty=true`.

No Linux, confirme primeiro o comando instalado:

```bash
command -v ai-presence
ai-presence --help
```

Se ele nao estiver no `PATH`:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --help
```

Antes de operar ou atualizar, execute:

```bash
ai-presence --version
ai-presence schema-status --json
ai-presence doctor --json
```

`--version` usa a constante do pacote e nao metadata gerada no checkout.
`schema-status` e `doctor` inspecionam o banco sem inicializa-lo ou migra-lo.
O relatorio nao inclui tokens, URLs de webhook, comandos de alarme, IDs de
sessao ou valores do `.env`.

Para atualizar o produto no Linux, use primeiro o dry-run e dois wheels locais
confiaveis:

```bash
ai-presence --dry-run upgrade \
  --package /caminho/absoluto/novo.whl \
  --rollback-package /caminho/absoluto/instalado.whl \
  --json
```

Uma execucao real exige `--authorize-once`. O rollback manual restaura o banco
anterior e tambem exige `--restore-database`, pois dados gerados depois do
snapshot serao descartados. Humanos e AI-workers devem ler
[TRANSACTIONAL-UPGRADE.md](TRANSACTIONAL-UPGRADE.md) antes da operacao, verificar
o status final do manifesto e nunca repetir automaticamente uma falha incerta.

No Windows PowerShell:

```powershell
$AiPresence = "$env:LOCALAPPDATA\ai-presence-monitor\venv\Scripts\ai-presence.exe"
& $AiPresence --help
```

Use [CONFIGURANDO-ENV.md](CONFIGURANDO-ENV.md) para criar a configuracao. Nunca
inclua `.env`, tokens, webhooks ou o banco em prompts, logs publicos ou commits.

## Preparacao pelo Ser Humano

1. Instale o pacote em ambiente virtual dedicado.
2. Crie o `.env` fora do repositorio ou use um arquivo local ignorado pelo Git.
3. Inicialize o banco com `ai-presence init`.
4. Instale os hooks com `ai-presence install-codex-hook` e revise-os no Codex.
5. Instale monitor e observer somente quando execucao continua for desejada.
6. Consulte as autorizacoes atuais antes de liberar automacao.

Comandos portateis para os processos de fundo:

```bash
ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor
ai-presence --dry-run install-background-service --component reply-observer
ai-presence install-background-service --component reply-observer
```

No Linux, a factory usa systemd de usuario. No Windows, usa Task Scheduler.

## Autorizacoes e Bandeja

Consulte a politica compartilhada:

```bash
ai-presence control show
ai-presence control show --json
```

As autorizacoes sao independentes:

| Controle | Efeito |
|---|---|
| `task-automation` | permite o procedimento real `continue` |
| `native-input` | permite `codex queue` |
| `gui-fallback` | permite controle X11/Win32 como fallback |
| `remote-input` | permite destino em computador cliente |
| `activity-sync` | permite sincronizacao depois de emissao sincrona confirmada |

Exemplos:

```bash
ai-presence control enable native-input
ai-presence control enable task-automation
ai-presence control disable gui-fallback
ai-presence control target --thread SESSAO_EXATA
```

Habilitar `task-automation` e uma autorizacao persistente, nao um timer. O
sistema nao envia `continue` sozinho em intervalos fixos.

Para usar a bandeja:

```bash
ai-presence tray --check
ai-presence tray
```

Ela oferece habilitar automacao, responder uma mensagem e sair. O compositor
usa despacho destacado para nao congelar a interface.

## Fluxos para Seres Humanos

### Acompanhar um AI-worker

```bash
ai-presence status
```

No Protocolo 1, o worker publica heartbeat a cada cinco minutos. No Protocolo
2, publica `start` e `finish`; hooks ou `touch` significativo registram
atividade silenciosa durante a tarefa.

### Observar evidencia diagnostica do Codex

Depois de iniciar o worker do projeto, uma leitura unica dos limites da conta
pode ser registrada com:

```bash
ai-presence observe-codex-limits \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA
```

Use `--watch` somente quando houver uma atribuicao explicita para manter esse
observer continuo. Ele confirma que o worker exato continua ativo antes de cada
poll e termina depois de `finish`:

```bash
ai-presence observe-codex-limits \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --watch
```

O comando consulta somente `account/rateLimits/read`. A evidencia expira e nao
atualiza `last_activity_at`, nao evita alertas do Protocolo 2 e nao envia
Discord, alarme, `continue` ou recuperacao. Hooks reconhecidos registram a sua
propria evidencia diagnostica curta, alem da observacao de presenca existente.
Esses producers nao decidem a causa sozinhos; a correlacao ocorre no comando
separado `diagnose`.

### Observar estado local do Linux

Rede e energia sao coletadas por padrao. Processo e servicos exigem alvos
explicitos:

```bash
ai-presence observe-linux-state \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --process-pid PID_EXATO \
  --expected-process-name codex \
  --service ai-presence-monitor.service \
  --service ai-presence-reply-observer.service
```

Use `--watch` para repetir no intervalo configurado. `finish` torna o worker
idle e encerra o watcher. `--skip-network`, `--skip-power` e `--no-services`
desabilitam fontes especificas. Se um shell substituir seu proprio processo ao
executar o ultimo comando, `$$` pode passar a identificar `python3`; confirme
PID e `/proc/PID/comm` antes de informar o nome esperado.

O observer nao testa DNS nem Internet, nao le linha de comando ou ambiente de
processos e nao consulta journal. Uma retomada de suspensao so pode ser
detectada entre duas coletas do mesmo watcher. Servico inativo e apenas um fato;
o motor o interpreta como problema somente porque as unidades observadas foram
selecionadas explicitamente como obrigatorias. Nenhuma dessas evidencias
atualiza presenca ou envia alertas.

### Correlacionar a causa atual

Use primeiro o modo sem escrita:

```bash
ai-presence --dry-run diagnose \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --json
```

Se o resultado e o alvo estiverem corretos, persista a transicao:

```bash
ai-presence diagnose \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA
```

O comando considera apenas evidencia nao expirada, mantem o lote mais novo de
cada fonte/tipo e falha fechado se encontrar sessoes Codex atuais conflitantes
sem `--session`. A severidade continua vindo do threshold do Protocolo 1 ou 2.
Fatos positivos isolados, como processo em execucao, rota default, sistema
acordado ou servico ativo, nao provam que a IA esta trabalhando. Na falta de
causa suficiente, o resultado correto e `unexplained_inactivity` com baixa
confianca.

`working` ou `long_running_operation` resolve um incidente aberto. Outras
causas atrasadas abrem ou atualizam um unico incidente. A Fase 5 nao envia
Discord/Telegram, nao toca alarme, nao envia input, nao repete uma acao e nao
recupera a sessao.

### Notificar um incidente diagnosticado

Revise primeiro a mensagem sem gravar uma tentativa nem acessar a rede:

```bash
ai-presence --dry-run notify-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --json
```

Somente depois de confirmar worker, causa, confianca e severidade, execute uma
tentativa real explicitamente:

```bash
ai-presence notify-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --session SESSAO_EXATA \
  --json
```

Amarelo e laranja usam `DISCORD_ALERT_WEBHOOK_URL`. Vermelho usa
`DISCORD_RED_WEBHOOK_URL` quando configurado e, caso contrario, o webhook
de alertas. Nao ha nova variavel de ambiente para esta fase.

O comando reserva no banco uma chave formada por incidente, causa, confianca e
severidade antes do unico POST. Uma repeticao equivalente retorna
`deduplicated`, mesmo que um novo diagnostico tenha outro UUID. Mudanca de
causa, confianca ou severidade permite uma nova tentativa no mesmo incidente;
um incidente novo tambem possui ciclo proprio.

Somente uma resposta HTTP confirmada marca `delivered` e atualiza
`last_notified_at`. Rejeicao HTTP, timeout, erro de rede ou interrupcao ficam
registrados como `rejected`, `uncertain` ou `pending` e nao sao repetidos
automaticamente. Corrija a causa e aguarde uma mudanca semantica ou um novo
incidente; nao transforme um resultado incerto em retry manual cego. Este
fluxo nao usa Telegram, alarme local, telefonia, input do Codex ou recuperacao.

### Recuperar um incidente elegivel uma unica vez

Este comando nao e observer nem servico continuo. Ele nunca e chamado por
`diagnose`, `notify-diagnostic-incident`, `monitor` ou por um timer. Avalie
primeiro sem escrita e sem transporte:

```bash
ai-presence --dry-run recover-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --json
```

O resultado `would_dispatch` significa somente que os gates atuais permitem
uma tentativa. Ele nao reserva o ledger, nao procura o executavel Codex e nao
envia input. A execucao real exige autorizacao explicita e descartavel:

```bash
ai-presence recover-diagnostic-incident \
  --project /caminho/absoluto/do/projeto \
  --authorize-once \
  --json
```

Pre-condicoes:

- worker exato ativo e um incidente aberto;
- diagnostico atual nao expirado;
- `codex_closed` com confianca media/alta ou `codex_crashed` com confianca alta;
- mesma sessao Codex explicita no incidente e no diagnostico;
- notificacao Discord `delivered` para o mesmo evento semantico;
- controle `native-input` habilitado e `codex` disponivel no `PATH`.

O coordenador reserva `native_continue` antes de chamar `codex queue`. Os
estados `pending`, `dispatch_started`, `input_emitted` e `uncertain` suprimem
qualquer repeticao no mesmo incidente. Timeout, falha incerta ou interrupcao
nao autorizam retry manual cego. A mensagem vem de
`PRESENCE_CONTINUE_MESSAGE`; nao ha opcao de mensagem, GUI, remoto, delay,
Telegram, alarme ou telefonia neste comando.

`dispatch_started` e `input_emitted` provam somente transporte. A recuperacao
nao atualiza `last_activity_at` ou `last_signal_at` e nao resolve o incidente.
Um hook posterior da mesma sessao e uma nova execucao de `diagnose` devem
comprovar a retomada. Uma IA nao pode executar a forma real sem autorizacao
especifica do usuario para aquela tentativa, mesmo quando a automacao de tarefa
persistente estiver habilitada.

### Enviar texto sem usar mouse ou teclado

```bash
ai-presence --dry-run send-input \
  --thread SESSAO_EXATA \
  --message 'texto de teste'

ai-presence send-input \
  --thread SESSAO_EXATA \
  --message 'texto autorizado'
```

`send-input` exige `native-input` habilitado. O humano que executa esse comando
esta realizando a acao explicitamente; scripts e IAs ainda precisam respeitar
a autorizacao definida pelo seu ambiente.

### Autorizar uma unica continuidade

```bash
ai-presence --dry-run continue \
  --project /caminho/absoluto/do/projeto \
  --thread SESSAO_EXATA

ai-presence continue \
  --project /caminho/absoluto/do/projeto \
  --thread SESSAO_EXATA \
  --authorize-once
```

`--authorize-once` vale somente para aquela invocacao. Ele nao habilita
permissao persistente.

### Convencao de mensagens manuais

Neste projeto, recomenda-se:

- `prossiga`: mensagem digitada manualmente pelo usuario;
- `continue`: mensagem padrao da automacao;
- `[AI-PRESENCE-E2E:<id>] continue`: somente teste E2E automatizado.

Essa convencao reduz confusao cotidiana, mas nao e uma garantia tecnica. Uma
pessoa ainda poderia digitar `continue`. Para um E2E valido, use sempre um
marcador exclusivo e confirme que o humano nao o digitou.

## Contrato para AI-workers

Antes de operar, a IA deve ler:

1. `AGENTS.md`;
2. este documento;
3. `docs/AI-WORKER-COMMAND-PROTOCOL.md`;
4. `docs/security/SECURITY.md`.

A IA deve usar o caminho absoluto do projeto que esta executando, mesmo quando
o monitor estiver instalado globalmente:

```bash
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
TASK="descricao objetiva do trabalho"
```

### Inicio da responsabilidade

Execute uma vez:

```bash
ai-presence start \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "AI-worker iniciou a tarefa"
```

Nao use `start` como heartbeat. Com hooks funcionando, nao execute `touch` a
cada comando.

### Durante o trabalho

Confie nos hooks do Codex. Somente quando eles estiverem indisponiveis e houver
trabalho real concluido, use:

```bash
ai-presence touch \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "checkpoint verificavel concluido"
```

`touch` baseado apenas em relogio e proibido porque simula atividade.

Hooks reconhecidos tambem registram evidencia diagnostica com TTL. Quando a
tarefa incluir observacao de limites, a IA pode executar uma leitura one-shot
com `observe-codex-limits --project "$PROJECT" --session SESSAO_EXATA`. Ela nao
deve manter `--watch` sem essa responsabilidade ter sido atribuida e nao deve
interpretar a evidencia como autorizacao para notificar ou recuperar.

Para evidencia Linux, use `observe-linux-state --project "$PROJECT"` somente
com PIDs e servicos confirmados. Nao descubra automaticamente outro processo
Codex por nome, nao trate rota local como Internet disponivel e nao use um
servico opcional inativo como diagnostico final.

Quando a tarefa incluir correlacao de causa, execute `ai-presence --dry-run
diagnose --project "$PROJECT" --session SESSAO_EXATA` antes da chamada real.
Nao interprete a criacao ou atualizacao de um incidente como autorizacao para
notificar, tocar alarme ou enviar `continue`.

### Perguntar ao usuario

Prefira o mecanismo nativo de pergunta da plataforma da IA. Quando ele nao
existir, o fallback Discord e:

```bash
ai-presence ask-user \
  --project "$PROJECT" \
  --thread SESSAO_EXATA \
  --question "Pergunta objetiva que bloqueia a proxima decisao"
```

A resposta valida precisa vir de usuario permitido, no canal correto, como
resposta direta a pergunta ainda aberta. A IA nao deve contornar correlacao,
allowlist ou expiracao. O transporte recomendado e `native`: a sessao fica
congelada antes da publicacao e a resposta retorna por `codex queue`. Use
`--answer-transport store` para somente registrar ou `gui` como fallback
explicitamente autorizado. Uma falha nativa nao permite trocar de transporte
automaticamente.

### Solicitar continuidade

A IA so pode executar `continue` quando:

1. o usuario autorizou a invocacao ou habilitou `task-automation`;
2. a etapa atual terminou e foi validada;
3. existe uma proxima tarefa concreta e documentada;
4. nao existe pergunta, aprovacao ou erro bloqueante;
5. nao existe outro `continue` pendente;
6. a sessao exata esta definida;
7. o trabalho ainda pertence ao mesmo escopo autorizado.

Sequencia recomendada:

```bash
ai-presence control show --json
ai-presence --dry-run continue \
  --project "$PROJECT" \
  --thread SESSAO_EXATA \
  --transport native

ai-presence continue \
  --project "$PROJECT" \
  --thread SESSAO_EXATA \
  --transport native \
  --authorize-once
```

Falha, timeout ou resultado incerto nunca autoriza retry automatico, fallback
GUI ou escolha de outra sessao.

### Encerramento da responsabilidade

Execute uma vez quando todo o trabalho autorizado terminar:

```bash
ai-presence finish \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "AI-worker concluiu a tarefa"
```

## Estados e Evidencias

| Estado/evidencia | O que comprova | O que nao comprova |
|---|---|---|
| `dry-run` | argumentos e selecao calculados | emissao ou processamento |
| `dispatch_started` | processo destacado foi criado | aceite, entrega ou atividade |
| `input_emitted` | transporte sincrono terminou com sucesso | interpretacao correta pelo agente |
| hook posterior | houve atividade posterior naquela sessao/worker | autoria da mensagem isoladamente |
| `delivery_confirmed` | observer correlacionou entrega e hook; nativo exige a mesma sessao | interpretacao correta ou qualidade da resposta |
| diagnosis `high/medium/low` | precedencia deterministica sobre fatos atuais | certeza absoluta fora das fontes observadas |
| incidente `open/resolved` | ciclo correlacionado do mesmo worker | notificacao, recuperacao ou acao automatica |

Para `continue` nativo, um hook isolado nao identifica qual entrada causou a
atividade. Nao declare E2E concluido apenas porque apareceu um hook depois do
comando.

No envio para a propria sessao Codex, `dispatch_started` e o comportamento
esperado. O monitor nao atualiza `last_activity_at` nesse momento; o proximo
hook registra atividade normal. Isso evita falso positivo no Protocolo 2.

## Protocolo E2E Nativo Correlacionado

### Preparacao

1. Obtenha autorizacao explicita para uma mensagem e sessao especificas.
2. Confirme que nao existe outra execucao pendente para o alvo.
3. Crie um identificador que ainda nao apareceu na conversa.
4. Combine que o humano usara `prossiga` e nao digitara o marcador.
5. Execute primeiro o dry-run.

Exemplo de marcador:

```text
[AI-PRESENCE-E2E:20260911-001] continue
```

Dry-run:

```bash
ai-presence --dry-run continue \
  --project /caminho/absoluto/do/projeto \
  --thread SESSAO_EXATA \
  --transport native \
  --detach \
  --delay 0 \
  --message '[AI-PRESENCE-E2E:20260911-001] continue'
```

Execucao unica autorizada:

```bash
ai-presence continue \
  --project /caminho/absoluto/do/projeto \
  --thread SESSAO_EXATA \
  --transport native \
  --detach \
  --delay 0 \
  --message '[AI-PRESENCE-E2E:20260911-001] continue' \
  --authorize-once
```

### Criterios de confirmacao

O E2E somente esta confirmado quando todos forem verdadeiros:

1. houve exatamente uma invocacao real;
2. o texto exato com marcador apareceu uma vez no alvo;
3. o humano confirmou que nao digitou nem colou o marcador;
4. um hook posterior pertence a mesma sessao;
5. nao houve retry depois de timeout ou resultado incerto.

Classifique como **inconclusivo** quando a mensagem visivel puder ter sido
manual, o alvo nao puder ser provado, o marcador estiver ausente ou houver
somente hook. Classifique como **falha** apenas quando houver evidencia
positiva de rejeicao sem resultado incerto.

## Integracao por Subprocesso ou Ferramenta

Outra IA, orquestrador, MCP server ou function-calling adapter pode expor a CLI
como uma ferramenta local. O wrapper deve:

1. fornecer argumentos como lista, nunca concatenar shell com entrada externa;
2. limitar comandos e opcoes permitidos por allowlist;
3. exigir `--project` absoluto;
4. preservar o codigo de saida e a saida padrao/erro;
5. nunca carregar nem retornar o `.env` ao modelo;
6. pedir autorizacao humana antes de `continue`, `send-input`,
   `dispatch-answer` ou fallback GUI;
7. proibir retry automatico de entrada incerta;
8. registrar alvo, estado e marcador, mas nao tokens ou conteudo sensivel.

Interface minima recomendada para um adaptador:

```text
presence_start(project, protocol, task, message)
presence_touch(project, protocol, task, message)
presence_finish(project, protocol, task, message)
presence_status()
presence_ask_user(project, thread, question, timeout, answer_transport, destination)
presence_continue(project, thread, message, delay, authorize_once)
presence_stop_alarm()
```

O adaptador deve mapear cada funcao para um subcomando existente e retornar
codigo de saida, estado textual e erro sanitizado. Ele nao deve transformar
`dispatch_started` em sucesso de entrega.

Para entrega automatica da resposta, `presence_ask_user` deve exigir sessao
explicita quando o wrapper nao puder herdar com seguranca a sessao atual.

## Prompt Pronto para Outra IA

```text
Antes de trabalhar, leia AGENTS.md, docs/USO-COMO-FERRAMENTA.md,
docs/AI-WORKER-COMMAND-PROTOCOL.md e docs/security/SECURITY.md do
AI Presence Monitor. Use o comando ai-presence instalado e sempre informe
--project com o caminho absoluto do projeto em que voce esta trabalhando.
Execute start uma vez ao aceitar a tarefa, confie nos hooks durante o trabalho
e execute finish uma vez ao concluir. Nao use touch por temporizador. Nao
execute continue, send-input, dispatch-answer ou automacao GUI sem autorizacao
humana explicita. Nao repita entrada com resultado incerto. Interprete
dispatch_started apenas como processo criado e input_emitted apenas como
transporte sincrono concluido. Hook isolado comprova atividade posterior, nao a
autoria de uma mensagem. Para E2E, use marcador exclusivo e confirme que o
humano nao digitou esse marcador.
```

## Diagnostico e Recuperacao

Comandos sem controle de GUI:

```bash
ai-presence status
ai-presence questions
ai-presence stop-alarm
```

No Linux:

```bash
systemctl --user is-active ai-presence-monitor.service
systemctl --user is-active ai-presence-reply-observer.service
journalctl --user-unit ai-presence-reply-observer.service -n 30 --no-pager
```

Se o observer atingir o limite de reinicios, corrija a causa e execute:

```bash
systemctl --user reset-failed ai-presence-reply-observer.service
systemctl --user restart ai-presence-reply-observer.service
```

Se houver alarme audivel, execute `ai-presence stop-alarm` imediatamente.

## Limites e Documentos Relacionados

- [AI-WORKER-COMMAND-PROTOCOL.md](AI-WORKER-COMMAND-PROTOCOL.md): protocolo
  normativo resumido para AI-workers.
- [CONTINUE-CODEX.md](CONTINUE-CODEX.md): norma completa do procedimento
  `continue`.
- [SYSTEM-TRAY-NATIVE-INPUT.md](SYSTEM-TRAY-NATIVE-INPUT.md): bandeja,
  `codex queue` e controles.
- [RESPOSTAS-REMOTAS-DISCORD-CODEX.md](RESPOSTAS-REMOTAS-DISCORD-CODEX.md):
  perguntas e respostas correlacionadas.
- [CONFIGURANDO-ENV.md](CONFIGURANDO-ENV.md): preenchimento seguro do `.env`.
- [security/SECURITY.md](security/SECURITY.md): checklist e riscos residuais.
- [planning/TASK-017-native-self-queue.md](planning/TASK-017-native-self-queue.md):
  estado atual da validacao E2E nativa.
