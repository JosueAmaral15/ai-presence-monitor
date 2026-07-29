# Architecture

## Visao Geral

O AI Presence Monitor tem cinco blocos:

- **Producers**: CLI manual, menu interativo e observers.
- **GUI Automation**: entrada X11 local para respostas e continuidade.
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

Com `PRESENCE_WORK_WINDOW_ENABLED=true`, o monitor pode suprimir alertas fora do horario configurado. Dentro do expediente, `PRESENCE_ALERT_REPEAT_ENABLED=true` permite reenviar o mesmo nivel de alerta depois de `PRESENCE_ALERT_REPEAT_SECONDS`, enquanto o worker continuar ativo e atrasado.

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
                     X11GuiAnswerDispatcher
                                  |
                                  v
                     input_emitted -> hook -> delivery_confirmed
```

`discord_questions.py` encapsula HTTP. `remote_questions.py` aplica correlacao,
allowlist e estados. `gui_answer.py` atua somente no ID X11 capturado e
revalidado.

O polling possui unidade systemd separada. Assim, falha de Discord ou da GUI nao
interrompe o monitor de atrasos nem o hook passivo.

## Continue Integrado

```text
CLI/menu -> captura alvo X11 unico -> delay -> revalidacao
                                           |
                                           v
                               clique + clipboard + Enter
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
