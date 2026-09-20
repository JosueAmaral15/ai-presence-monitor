# Architecture

## Visao Geral

O AI Presence Monitor tem cinco blocos:

- **Producers**: CLI manual, menu interativo e observers.
- **Input Transports**: `codex queue` para sessoes exatas e X11/Win32 como
  fallback GUI explicito.
- **Event Store**: SQLite local via `PresenceStore`.
- **Rule Engine**: protocolos e limiares em `protocols.py`, janela de expediente em `work_window.py` e avaliacao em `cli._check_once`.
- **Notifiers**: Discord, Telegram e escalonamento vermelho.

## Observer Architecture

Observers nao decidem alertas. Eles apenas registram evidencias de atividade.

```text
Codex lifecycle hook
        |
        v
python absoluto -m ai_presence_monitor.codex_hook
        +-----------------------------+
        |                             |
        v                             v
PresenceStore.record_observation()  DiagnosticStore.record_evidence()
        |                             |
        +---------------+-------------+
                        |
                        v
              SQLite workers/events/diagnostics
        |
        v
monitor -> protocolos -> notificadores
```

## Cause-aware Diagnostic Foundation

Task 022 extends the observer boundary without changing the existing presence
protocols:

```text
source observers -> diagnostic evidence -> diagnosis engine
                                             |
                                             v
                                      incident lifecycle
                                             |
                                             v
                                      notification policy
                                             |
                                             v
                              explicit recovery coordinator
```

Observers remain fact producers. They do not choose severity, notify Discord or
trigger recovery. `DiagnosticStore` persists four separate concepts:

- `DiagnosticEvidence`: a bounded fact, source, state, worker, optional exact
  session, observation time and optional expiry;
- `Diagnosis`: a typed interpretation with confidence and immutable ordered
  links to one or more evidence records;
- `DiagnosticIncident`: one open episode per worker, with current diagnosis,
  severity, notification timestamp and resolution state.
- `DiagnosticRecovery`: one reserved action per incident/action pair, with
  bounded transport state and failure code.

Evidence and diagnoses are append-only. An open incident can change its current
diagnosis as stronger evidence arrives, preventing parallel observers from
creating contradictory user notifications. Each downstream stage remains an
explicit consumer: evidence collection cannot diagnose, diagnosis cannot
notify, and notification cannot invoke recovery.

The diagnostic tables are additive to the same SQLite database and do not
modify `workers.last_activity_at`, `workers.last_signal_at`, protocol alerts or
remote-question delivery. They store concise summaries rather than raw Codex
events or transcripts.

### Codex App Server feasibility boundary

The Task 022 Phase 2 probe uses a dedicated `codex app-server --stdio` child
with a hard method allowlist. Metadata-only `thread/read` and structured
`account/rateLimits/read` work from that process. An active GUI-owned thread is
`notLoaded` in the child, and `thread/resume` is rejected as
`thread_already_active`; therefore the child cannot receive the live event
stream for that existing session.

The supported near-term Codex evidence path is existing same-session hooks plus
safe account-limit polling. A live event adapter requires the Codex session to
be hosted through the same managed/multiplexed App Server boundary and remains
disabled until that topology passes its own E2E. The probe never records
evidence, updates presence clocks, sends notifications or performs recovery.

### Codex evidence observers

Phase 3 maps only recognized lifecycle hooks to constant diagnostic states.
These facts have a configured TTL and contain neither raw hook payloads nor
prompt, message, command or tool text. The legacy presence observation remains
separate and continues to update Protocol 2 activity only when the worker was
explicitly started.

The account-limit observer uses a fresh dedicated App Server child per poll and
calls only `account/rateLimits/read`. It stores an allowlisted account state as
diagnostic evidence for an exact active worker. The default mode performs one
poll; `--watch` revalidates the worker before every poll and stops after
`finish`.

```text
observe-codex-limits -> account/rateLimits/read -> sanitize/classify
                                                   |
                                                   v
                                      diagnostic_evidence only
```

Neither source updates `last_activity_at` or `last_signal_at` through its
diagnostic record. The limit observer does not subscribe to thread events,
diagnose a cause, create an incident, notify Discord, play an alarm or send
Codex input.

### Linux system evidence observers

Phase 4 adds `linux_evidence.py` and the Linux-only
`observe-linux-state` command. Four collectors remain independent:

```text
explicit PID -> /proc/PID/comm + stat --------> process evidence
/proc/net/route + /sys/class/net -------------> network evidence
CLOCK_BOOTTIME - monotonic elapsed gap --------> power evidence
explicit unit -> systemctl --user show --------> service evidence
                                                      |
                                                      v
                                           diagnostic_evidence only
```

The process collector binds an explicit positive PID to an optional expected
Linux process name and remembers kernel start ticks during one observer run.
This distinguishes missing, zombie, dead, mismatched and replaced processes
without reading command lines, environment variables or open files.

The network collector sends no packet. A default route or up link describes
only local kernel state and does not prove DNS or Internet reachability. The
power collector cannot run while the machine is suspended; in watch mode it
detects a resume afterward when `CLOCK_BOOTTIME` advanced farther than the
monotonic clock. The service collector accepts only bounded `.service` unit
names and parses allowlisted fields from `systemctl --user show` invoked without
a shell.

Network and power are enabled by default. Process and service targets are
explicit. The default command is one-shot; `--watch` checks the worker before
and after every sample, then stops after `finish`. Dry-run performs one local
sample without SQLite. Persisted facts expire and cannot update protocol
clocks, classify a cause, create incidents, notify or recover.

### Diagnosis engine and incident transitions

Phase 5 adds `diagnosis_engine.py` and the one-shot `diagnose` command:

```text
worker protocol clock + current diagnostic_evidence
                        |
                        v
       newest batch per source/kind + exact session filter
                        |
                        v
       deterministic cause + confidence + bounded summary
                        |
                        v
        immutable diagnosis -> one incident transition
```

The engine records a short workspace evidence fact for whether the worker is
inside or beyond its current protocol threshold. An overdue cause diagnosis
links both the cause fact and this threshold fact. Severity is not inferred by
an observer; it is the selected Protocol 1 or Protocol 2 threshold.

Multiple current session IDs fail closed unless the caller specifies one.
Session-neutral facts may support the selected session. Facts from another
session are excluded, and the persistence layer rejects any remaining
cross-session link. A healthy diagnosis resolves an existing incident;
non-healthy overdue diagnoses open or update the worker's one incident.

This phase does not call notification, alarm, Codex input or recovery code.
`last_notified_at` is preserved during updates for the Phase 6 notification
policy. `--dry-run` computes the same assessment and transition without adding
evidence, diagnosis or incident rows.

## Diagnostic Notification Policy

Phase 6 adds `diagnostic_notifications.py` as the only owner of cause-aware
Discord delivery:

```text
open diagnostic incident + current diagnosis
                    |
                    v
 semantic key(kind, confidence, severity)
                    |
                    v
 reserve diagnostic_notifications row
                    |
                    v
 one Discord POST -> delivered | rejected | uncertain
```

The database uniqueness boundary combines `incident_id`, semantic event key
and channel. It therefore ignores diagnosis UUID churn but rearms for a changed
cause, confidence, severity, or a new incident. Reservation happens before
network access, so concurrent commands and interrupted processes cannot create
an automatic duplicate. Existing `pending`, `rejected`, `uncertain` and
`delivered` rows are terminal for automatic dispatch of that event key.

Only confirmed delivery atomically updates both the ledger row and the
incident's `last_notified_at`. HTTP rejection and transport uncertainty retain
bounded status/failure codes without raw response bodies. Dry-run constructs
the same bounded payload but neither reserves a row nor accesses the network.
Missing webhook configuration fails before reservation.

This policy uses the existing alert webhook, with the configured red webhook
preferred for red severity. It does not call the general multi-channel
notifier, Telegram, alarm, phone, Codex input or recovery paths.

## One-Shot Recovery Coordinator

Phase 8 adds `recovery_coordinator.py` as an explicitly invoked consumer. It is
not called by observers, the diagnosis engine, notification delivery, the
monitor loop, or a background service:

```text
active worker + eligible current diagnosis + exact session
                         +
        delivered semantic Discord notification
                         |
                         v
       reserve diagnostic_recoveries(incident, native_continue)
                         |
                         v
        one local codex queue dispatch -> transport state
```

Eligibility is intentionally narrow: `codex_closed` at medium/high confidence
or `codex_crashed` at high confidence, with an unexpired diagnosis and matching
incident/diagnosis session. Real execution also requires the one-invocation
`--authorize-once` flag; persistent task automation is not authorization.

The unique boundary is `(incident_id, action)`. Reservation precedes transport,
so a concurrent invocation, interruption, detached dispatch, success, or
uncertain result cannot cause a second dispatch for that incident. Dry-run
evaluates the same domain gates without checking the Codex executable,
reserving a row, or sending input.

Only local native input is reachable. GUI, remote input, delay, Telegram,
alarm, phone and chained recovery are absent. A recovery attempt never mutates
presence clocks or resolves the incident. `dispatch_started` and
`input_emitted` remain transport evidence; a later same-session hook plus a new
diagnosis transition is required to establish resumed work.

## Tipos de Sinal

- `start`, `heartbeat`, `finish`: sinais publicos, podem postar no canal de ponto.
- `touch`: atividade silenciosa manual.
- `observation`: atividade silenciosa automatica de observer.
- `observation:automation:continue`: entrada de continuidade emitida com
  sucesso para um worker ja ativo.

No Protocolo 2, o relogio monitorado e `last_activity_at`. Portanto `touch` e `observation` evitam falsos alertas enquanto houver evidencia recente de atividade.

O evento de continuidade concede uma nova janela normal de inatividade, mas nao
mantem o worker ativo indefinidamente. Um hook posterior continua sendo a
evidencia de atividade subsequente do Codex. No Protocolo 1, observacoes
preservam `last_signal_at` e nao substituem heartbeat.

## Work Window Policy

A janela de expediente e uma politica do monitor, nao dos protocolos.

```text
monitor
  |
  v
work_window.py -> dentro do expediente?
  |
  v
protocolos -> thresholds -> repeticao/escalada -> notificadores
```

Com `PRESENCE_WORK_WINDOW_ENABLED=true`, o monitor pode suprimir alertas fora
do horario configurado. Dentro do expediente,
`PRESENCE_ALERT_REPEAT_ENABLED=true` permite reenviar amarelo e laranja depois
de `PRESENCE_ALERT_REPEAT_SECONDS`, enquanto o worker continuar ativo e
atrasado. Vermelho e one-shot por episodio de inatividade e so e rearmado por
atividade valida.

## CodexHookObserver

`ai_presence_monitor.codex_hook` implementa o observer do Codex. Ele:

- le JSON de hook via `stdin`;
- aceita `hook_event_name` e `hookEventName`;
- extrai metadata segura e curta;
- grava `observation:codex:<evento>` no SQLite;
- para hooks reconhecidos, grava tambem evidencia diagnostica curta e com TTL;
- nao envia notificacoes nem faz chamadas de rede.

Por padrao, `PRESENCE_CODEX_AUTO_START=false`. Assim, o observer nao cria ou reativa worker sozinho. Isso preserva o Protocolo 2: `start` e `finish` continuam sendo os sinais publicos de ciclo de tarefa.

## Portabilidade

`config.resolve_env_path` seleciona o `.env` explicito, local ou da configuracao
do usuario. Caminhos relativos de dados sao resolvidos contra o diretorio desse
arquivo.

`identity.scoped_worker_id` acrescenta projeto e/ou sessao a identidade base sem
alterar o esquema SQLite. O modo `global` preserva IDs da versao 0.1.

O instalador de hooks e o gerador systemd usam `sys.executable`. Assim, a
integracao aponta para o ambiente Python onde o pacote foi instalado, e nao para
o checkout do codigo-fonte.

## Remote Question Observer

O fluxo de respostas remotas e separado do monitor de presenca:

```text
ask-user -> webhook Discord -> remote_questions
                                  |
Discord REST polling -> validacao-+-> resposta autorizada
                                  |
                +-----------------+------------------+
                | native          | gui              | store
                v                 v                  v
    NativeCodexAnswerDispatcher   GuiQuestion...     SQLite
                |                 /        \
          codex queue           X11       Win32
                |                 |
                +--------+--------+
                         v
          input_emitted -> hook correlacionado -> delivery_confirmed
```

`discord_questions.py` encapsula HTTP. `remote_questions.py` aplica correlacao,
allowlist, resolucao imutavel do alvo e estados. `answer_dispatch.py` define a
Strategy de entrega. O nativo usa a sessao exata salva na pergunta; o GUI atua
somente no ID capturado e revalidado da janela da plataforma. Uma falha nativa
nunca seleciona a GUI nem gera retry automatico.

O alvo nativo e resolvido antes da publicacao pela ordem: argumento explicito,
ambiente Codex, controle persistido ou uma unica sessao recente do mesmo
worker. Endpoint remoto e nome da variavel de token podem ser persistidos, mas
o token continua somente no ambiente. Hooks confirmam entrega nativa apenas
quando `worker_id` e `session_id` correspondem ao registro da pergunta. Registros
GUI anteriores a esta estrategia preservam a confirmacao por worker.

O polling possui unidade systemd ou tarefa agendada separada. Assim, falha de
Discord ou da GUI nao interrompe o monitor de atrasos nem o hook passivo.
Mensagens humanas de usuarios permitidos passam por classificacao antes da
aceitacao. Se ainda houver pergunta pendente, ausencia de referencia,
referencia sem correspondencia ou conteudo vazio gera uma unica tentativa de
orientacao pelo webhook. O cursor avanca mesmo se o aviso falhar, evitando
duplicacao depois de timeout incerto. Bots, webhooks e autores fora da
allowlist nao recebem feedback.

No Linux, a unidade do observer usa `Restart=on-failure`, espera 30 segundos e
aceita no maximo tres inicios com falha em cinco minutos. O monitor principal
continua com `Restart=always` e espera de cinco segundos. No Windows, o Task
Scheduler ja limita a tres reinicializacoes em falha.

## Continue Integrado

```text
CLI/bandeja -> ControlStore -> resolve sessao/alvo -> delay
                                      |
                     +----------------+----------------+
                     |                                 |
                     v                                 v
       CodexQueueClient (`codex queue`)      dispatcher GUI opt-in
              |                  |                      |
      propria sessao       outra sessao                |
              |                  |                      |
              v                  +----------+-----------+
     dispatch_started                       |
              |                             v
              |                      input_emitted
              |                             |
              |          worker active? ---+--- nao -> sem sync
              |                 |
              |                 v
              |  observation:automation:continue -> last_activity_at
              |                 |
              +-----------------+----------------+
                                                 |
                                                 v
                                      hook posterior do Codex
```

`continue_task.py` coordena o caso de uso. `codex_input.py` encapsula o
subprocesso nativo sem shell e o destino local/remoto. `gui_answer.py` permanece
como fallback de despacho textual. A propria sessao e detectada pelas variaveis
do ambiente Codex e usa processo destacado. `dispatch_started` nao altera o
SQLite; somente o hook posterior registra atividade. Emissoes sincronas podem
sincronizar o worker depois do sucesso. Falha ou cancelamento nunca alteram o
SQLite.

## Bandeja e Politica de Automacao

`control.py` persiste `ControlSettings` em JSON por substituicao atomica. Por
padrao, o arquivo fica na area de estado do usuario, fora do checkout, e nao
armazena token, somente o nome da variavel de ambiente. CLI e `tray.py` leem o
mesmo arquivo.

`tray.py` importa PySide6 apenas ao iniciar a interface. Isso mantem a camada
grafica fora da dependencia base e permite executar monitor/hooks em ambientes
sem desktop. O menu oferece tres comandos; o dialogo de preferencias edita as
flags e o compositor chama o mesmo `send_native_message` usado pela CLI.

A permissao `task_automation_enabled` e um gate, nao um scheduler. A decisao de
executar `continue` continua pertencendo ao AI-worker e as pre-condicoes
normativas da tarefa.

## Source Layout

O pacote instalavel fica em `src/ai_presence_monitor`. Testes usam
`PYTHONPATH=src` ou uma instalacao editavel. `main.py` e o wrapper de hook
adicionam `src/` explicitamente somente para preservar os entrypoints locais de
compatibilidade.

## Product Health and Schema Contract

`store.py` owns `SCHEMA_VERSION` and records it in SQLite `PRAGMA user_version`
after the idempotent schema initialization succeeds. Runtime initialization
accepts legacy version 0, applies additive migrations and records version 1.
It rejects a database newer than the runtime before applying DDL.

`inspect_schema` opens existing databases with SQLite `mode=ro`, runs
`quick_check`, compares required tables and never creates a missing file.
`schema-status` exposes only bounded status fields.

`product_health.py` composes read-only checks for runtime, platform,
configuration permissions, SQLite, controls, hooks, `codex queue`, user
services and tray autostart. It receives sanitized states from existing
adapters and never serializes `.env` values, webhook URLs, tokens, prompts or
session IDs. Default exit status fails errors; strict mode also fails warnings.

## Transactional Package Lifecycle

`updater.py` implements the supported Linux package transaction around the
dedicated runtime interpreter. It accepts only local wheels, validates the
rollback version against the installed module from a clean child process, and
uses fixed argument vectors without a shell. Package installation uses
`--no-index --no-deps`.

Before mutation it copies target and rollback wheels, creates a SQLite backup
through the backup API, computes SHA-256 values and writes an atomic mode-0600
manifest under the user state directory. The transaction records which managed
services were active. Partial service stops are reversed before installation;
partial postflight starts are stopped before package/database rollback.

The postflight initializes additive migrations, verifies the installed version
and requires `doctor` not to report an error. Manual rollback validates the
managed manifest and all checksums, snapshots the current upgraded database,
then requires explicit acknowledgement before restoring the older snapshot.
The tray is a desktop process rather than a managed service and remains outside
this transaction.

## Fronteira de Plataforma

O entrypoint `ai-presence` e gerado pelo empacotamento Python no Linux e no
Windows. Alias de shell nao faz parte do contrato porque hooks, subprocessos e
servicos podem executar sem carregar configuracao interativa do shell.

O nucleo de configuracao, identidade, protocolos e SQLite e independente da
plataforma. `platform_integration.py` implementa Abstract Factory e cria tres
produtos coerentes:

Desde a versao 0.6.2, `ensure_runtime_enabled` atua antes da criacao desses
produtos: Linux e habilitado por padrao, enquanto a familia Windows preservada exige
`PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true`. O gate altera disponibilidade,
nao a estrutura das implementacoes concretas.

```text
PlatformIntegrationFactory
  +-- LinuxPlatformFactory
  |     +-- X11GuiAnswerDispatcher
  |     +-- LinuxAlarmProcessBackend
  |     `-- LinuxBackgroundServiceManager
  `-- WindowsPlatformFactory
        +-- Win32GuiAnswerDispatcher
        +-- WindowsAlarmProcessBackend
        `-- WindowsTaskSchedulerService
```

`continue_task.py`, `remote_questions.py`, `alarm.py` e a CLI dependem dos
contratos, nao da implementacao nativa. Imports de Win32 sao tardios para que o
pacote continue importavel no Linux.

## Controle do Alarme Local

`alarm.py` inicia o comando vermelho em uma nova sessao de processo e persiste
somente PID, fingerprint e token de inicio. Antes de iniciar outro alarme, o
controlador confirma que o processo registrado ainda e o mesmo.

No Linux, o comando e envolvido por GNU `timeout` e a identidade e lida em
`/proc`. No Windows, `CommandLineToArgvW` interpreta o comando, um runner Python
aplica o limite e `GetProcessTimes` mais `QueryFullProcessImageNameW` fornecem a
identidade. `taskkill /T /F` encerra somente a arvore do runner revalidado.

Uma thread chama `wait()` para coletar corretamente o filho e remover o estado
quando o som termina. `stop-alarm` revalida PID, fingerprint e token antes de
sinalizar o grupo, evitando encerrar um processo reutilizado por engano.
