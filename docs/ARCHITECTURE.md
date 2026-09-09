# Architecture

## Visao Geral

O AI Presence Monitor tem cinco blocos:

- **Producers**: CLI manual, menu interativo e observers.
- **GUI Automation**: entrada local X11 ou Win32 para respostas e continuidade.
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
        |
        v
PresenceStore.record_observation()
        |
        v
SQLite workers/events
        |
        v
monitor -> protocolos -> notificadores
```

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
                                  v
                  GuiAnswerDispatcher (Protocol)
                    /                     \
     X11GuiAnswerDispatcher       Win32GuiAnswerDispatcher
                                  |
                                  v
                     input_emitted -> hook -> delivery_confirmed
```

`discord_questions.py` encapsula HTTP. `remote_questions.py` aplica correlacao,
allowlist e estados. O dispatcher selecionado atua somente no ID capturado e
revalidado da janela da plataforma.

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
CLI/menu -> captura alvo de janela unico -> delay -> revalidacao
                                           |
                                           v
                              adaptador GUI + texto + Enter
                                           |
                                           v
                              input_emitted localmente
                                           |
                       worker active? -----+----- nao -> sem sync
                             |
                             v
          observation:automation:continue -> last_activity_at
                             |
                             v
                    hook posterior do Codex
```

`continue_task.py` coordena o caso de uso. `gui_answer.py` oferece a operacao
generica de despacho textual, tambem reutilizada por respostas remotas. A
sincronizacao ocorre depois do despacho; falha ou cancelamento nao alteram o
SQLite.

## Source Layout

O pacote instalavel fica em `src/ai_presence_monitor`. Testes usam
`PYTHONPATH=src` ou uma instalacao editavel. `main.py` e o wrapper de hook
adicionam `src/` explicitamente somente para preservar os entrypoints locais de
compatibilidade.

## Fronteira de Plataforma

O entrypoint `ai-presence` e gerado pelo empacotamento Python no Linux e no
Windows. Alias de shell nao faz parte do contrato porque hooks, subprocessos e
servicos podem executar sem carregar configuracao interativa do shell.

O nucleo de configuracao, identidade, protocolos e SQLite e independente da
plataforma. `platform_integration.py` implementa Abstract Factory e cria tres
produtos coerentes:

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
