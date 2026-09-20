# Security Checklist

## Task 022 - Diagnostic foundation

- [x] Diagnostic tables are additive and do not alter presence clocks.
- [x] Evidence stores typed state and a bounded summary, not raw observer
      payloads, prompts or transcripts.
- [x] Worker, session and state identifiers reject empty, multiline, NUL and
      oversized values.
- [x] A diagnosis requires persisted evidence from the same worker and cannot
      combine conflicting Codex sessions.
- [x] Foreign keys protect diagnosis-evidence and incident-diagnosis links.
- [x] A partial unique index permits at most one open incident per worker.
- [x] Phase 1 contains no network calls, notifications, Codex input, retry or
      recovery execution.

### Residual risk

Future observers must map external payloads to the existing bounded vocabulary
instead of persisting them verbatim. A concise summary can still contain a
secret if a producer violates that contract, so observer implementations need
source-specific allowlists and tests before live activation.

## Task 022 - Codex App Server feasibility probe

- [x] Requests use an argument vector and dedicated stdio child without a
      shell, remote listener or inherited input transport.
- [x] `turn/start`, `turn/steer`, item injection, queue and GUI input have no
      allowed request path.
- [x] `thread/read` forces `includeTurns=false`; rate-limit reads exclude reset
      credit details.
- [x] Message, reasoning, command, patch, plan, transcript and audio deltas are
      opted out; unknown notifications are dropped.
- [x] Output uses typed allowlisted fields and excludes account ID, balances,
      titles, previews, items, raw errors and arbitrary server messages.
- [x] Metadata must match the requested thread, and cross-thread events are
      discarded.
- [x] The probe does not write SQLite, update activity, notify, alarm or recover.
- [x] A failed subscription is not retried automatically.

### Residual risk

`thread/resume` is observational but still loads or rejoins a thread inside the
child App Server. Keep positive `--subscribe-seconds` values limited to explicit
development tests. A future shared-daemon adapter needs authentication, local
socket permissions, client isolation and exact-session E2E before activation.

## Task 022 - Codex evidence observers

- [x] Recognized hooks map to constant evidence states and summaries; raw hook
      payloads, prompts, messages, commands and tool names are not persisted.
- [x] Unknown hooks do not create diagnostic evidence.
- [x] Hook and account-limit evidence use positive configurable TTLs.
- [x] The account observer exposes only `account/rateLimits/read` through the
      existing hard allowlist and discards raw App Server payloads.
- [x] The observer requires the exact active worker and rechecks it before each
      continuous poll.
- [x] Dry-run performs no SQLite write, and an idle or missing worker fails
      before a persisted read.
- [x] Diagnostic evidence does not modify presence clocks or worker state.
- [x] Phase 3 has no thread subscription, notification, alarm, Codex input,
      automatic retry, diagnosis or recovery path.

### Residual risk

Account-limit fields and classifications may evolve in future Codex versions.
Unknown documented values are collapsed into bounded fallback states instead
of being persisted verbatim. The diagnosis engine must still correlate this
evidence with independent observers before notifying the user.

## Task 022 - Linux system evidence observers

- [x] Linux-only runtime guard fails before collector execution on other
      platforms, including experimental Windows.
- [x] Process observation reads only `comm` and `stat` for an explicit positive
      PID; it does not read command lines, environments or open files.
- [x] Expected process names and systemd units use bounded allowlists.
- [x] PID start ticks detect replacement during one watcher lifetime.
- [x] Network observation reads only local route and link state and sends no
      DNS, HTTP, ICMP or other network traffic.
- [x] Boot IDs, actual process names, stderr and raw systemd output are never
      persisted or printed.
- [x] `systemctl` uses a fixed argument vector without a shell and parses only
      `LoadState`, `ActiveState` and `Result`.
- [x] Every fact has a positive TTL; dry-run writes no SQLite; idle or missing
      workers fail before persistence.
- [x] Phase 4 does not update presence, diagnose, notify, alarm, retry input or
      recover a worker.

### Residual risk

PID identity before the first successful sample can still be stale; provide an
expected process name. A local default route does not prove upstream or DNS
availability. Suspend detection occurs only after resume and can be lost if the
watcher is terminated. Service inactivity is not a fault unless a later policy
knows that the selected unit was required.

## Task 022 - Diagnosis engine

- [x] Only non-expired evidence is considered.
- [x] Newest-batch reduction prevents an older fact of the same source/kind
      from overriding its replacement while retaining simultaneous services.
- [x] Ambiguous current Codex sessions fail before diagnostic writes.
- [x] Direct account and interaction states use bounded allowlists.
- [x] Local network degradation is limited to low or medium confidence and
      never claims that an upstream Internet probe succeeded or failed.
- [x] Positive process, route, power, service and account facts do not prove
      worker activity by themselves.
- [x] Every persisted diagnosis links evidence; overdue causes also link a
      bounded protocol-threshold fact.
- [x] Dry-run does not add evidence, diagnosis or incident rows.
- [x] Incident updates preserve `last_notified_at` and one-open-per-worker.
- [x] Phase 5 has no notification, alarm, input, retry or recovery call path.

### Residual risk

The diagnosis is limited to the observers that were actually running and may
remain `unexplained_inactivity`. A local route cannot distinguish DNS, proxy,
firewall or upstream service failures. A required service must be selected
intentionally; selecting an optional service makes its inactivity eligible as
observer-health evidence. Phase 6 must preserve confidence and deduplicate from
the incident state instead of notifying from raw evidence.

## Task 001 - Codex Hook Observer

### 1. Injection

- [x] Nao usa SQL dinamico com interpolacao; operacoes SQLite usam parametros.
- [x] Nao usa `eval()` ou `exec()`.
- [x] O hook nao executa comandos vindos do JSON do Codex.

### 2. Dados Sensiveis

- [x] Webhooks e tokens continuam no `.env`, que esta no `.gitignore`.
- [x] Hook nao imprime payload por padrao.
- [x] Metadata gravada deve ser curta e nao incluir transcript completo.

### 3. Controle de Acesso

- [x] O hook grava apenas no banco configurado.
- [x] Hook gerado usa Python e `.env` absolutos para evitar ambiguidade.

### 4. Configuracoes Inseguras

- [x] Sem dependencia externa nova.
- [x] Sem rede dentro do hook.
- [x] Erros recuperaveis nao interrompem Codex por padrao.

### 5. Logs/Monitoring

- [x] Eventos de observer ficam no SQLite para auditoria local.
- [x] Notificacoes continuam centralizadas no monitor.

## Limites

- A instalacao do hook em `~/.codex/hooks.json` exige confianca/revisao no Codex via `/hooks`.
- O observer prova atividade de lifecycle do Codex, nao qualidade do trabalho produzido.

## Task 003 - Janela de expediente e repeticao

- [x] Repeticao de alerta usa intervalo minimo configurado por `PRESENCE_ALERT_REPEAT_SECONDS`.
- [x] Fora do expediente, `suppress_alerts` evita novos alertas quando a janela esta ativa.
- [x] Vermelho nao repete mensagem nem escalada externa no mesmo episodio de inatividade.
- [x] Somente nova atividade valida rearma um futuro alerta vermelho.
- [x] Comandos locais continuam restritos ao valor explicito de `RED_ALERT_COMMAND` no `.env`.
- [x] Estado do alarme nao armazena o comando em texto e usa permissao `600`.
- [x] `stop-alarm` valida PID, fingerprint e inicio antes de sinalizar.
- [x] GNU `timeout` limita todo alarme local, inclusive comandos em loop.
- [x] Windows limita o alarme em runner dedicado e encerra somente sua arvore.
- [x] Windows revalida PID, horario nativo de criacao e executavel antes da parada.

## Task 004 - Portabilidade

- [x] Wheel inclui somente o pacote `ai_presence_monitor`.
- [x] Hook recebe apenas caminho de Python e `.env` definidos localmente.
- [x] Instaladores de hook e systemd criam backup antes de substituir.
- [x] Desinstalacao do systemd cria backup recuperavel antes de remover.
- [x] `.env`, banco, build e metadata de pacote ficam ignorados pelo Git.
- [x] Escopo usa hash de caminho, sem gravar conteudo dos arquivos do projeto.

## Task 006 - Respostas remotas

- [x] Recurso remoto e entrega GUI desativados por padrao.
- [x] Token do bot e webhook permanecem somente no `.env`.
- [x] Bot usa allowlist de IDs numericos.
- [x] Somente resposta com `message_reference.message_id` e aceita.
- [x] Mensagens de bot, respostas vazias e canal diferente sao ignorados.
- [x] `allowed_mentions` impede mencoes disparadas pela pergunta.
- [x] Texto da resposta nao e executado por shell.
- [x] X11 e Win32 exigem ID e titulo capturados, revalidados antes da entrega.
- [x] No Linux, o clipboard anterior e restaurado; no Windows, ele nao e usado.
- [x] Falha GUI nao causa retry automatico.
- [x] Estados e erro ficam auditaveis no SQLite.
- [x] `--dry-run` nao acessa rede, banco nem GUI nos comandos de resposta.

### Risco residual

Um usuario autorizado controla texto que sera enviado ao Codex. Conta Discord
comprometida ou allowlist incorreta pode alterar o trabalho da IA. O mecanismo
nao substitui revisao de permissoes, isolamento do canal e validacao humana para
acoes destrutivas.

## Task 007 - Continue integrado

- [x] Texto e enviado por clipboard no Linux ou `SendInput` no Windows, sem shell.
- [x] Uma unica janela deve corresponder ao titulo.
- [x] ID e titulo sao revalidados depois do delay.
- [x] No Linux, o clipboard anterior e restaurado; no Windows, ele nao e usado.
- [x] `--dry-run` nao espera, nao acessa GUI e nao grava banco.
- [x] Falha GUI nao atualiza atividade.
- [x] Sincronizacao exige worker existente e ativo.
- [x] Sincronizacao preserva `last_signal_at` do Protocolo 1.
- [x] Evento diferencia automacao de hook posterior.
- [x] Nao existe retry automatico.
- [x] Configuracao real e segredos nao foram modificados.

### Risco residual

Uma emissao bem-sucedida prova que o sistema operacional aceitou os eventos de
entrada, nao que o Codex interpretou ou executou a mensagem. Por isso a
observacao reinicia apenas a janela normal do Protocolo 2; ausencia posterior de
hooks volta a produzir alerta.

## Task 012 - Windows

- [x] Win32 e acessado por argumentos tipados de `ctypes`, sem shell.
- [x] Texto remoto e enviado como Unicode por `SendInput`, nao como comando.
- [x] Falha de foreground impede clique e digitacao.
- [x] Tarefas usam `InteractiveToken` e `LeastPrivilege`, nao `SYSTEM`.
- [x] XML do Task Scheduler guarda caminhos, nao valores secretos do `.env`.
- [x] Desinstalacao remove somente os dois nomes de tarefa administrados.
- [x] `--dry-run` nao registra tarefa, nao escreve definicao e nao usa GUI.

### Risco residual Windows

Qualquer automacao de teclado pode influenciar a aplicacao alvo. A revalidacao
reduz selecao incorreta, mas nao substitui sessao desbloqueada, titulo especifico
e revisao humana antes de comandos destrutivos. O Windows tambem pode negar
foreground; o sistema falha fechado nessa situacao.

## Task 013 - Hardening operacional do observer

- [x] Limite de reinicio e aplicado somente ao observer de respostas.
- [x] Tres falhas em cinco minutos bloqueiam uma tempestade de reinicios.
- [x] O intervalo entre tentativas sobe de cinco para 30 segundos.
- [x] O monitor principal preserva sua politica independente.
- [x] Recuperacao exige corrigir a causa e executar `reset-failed`.
- [x] Nenhum token, webhook ou conteudo do `.env` entra na unidade.

### Risco residual

O limite interrompe recuperacao automatica depois de falhas persistentes. Essa
escolha evita carga e ruido indefinidos; depois de corrigir rede, canal ou
credenciais, o operador precisa liberar e iniciar a unidade explicitamente.

## Task 014 - Orientacao para respostas Discord invalidas

- [x] Orientacao exige pergunta pendente no mesmo canal.
- [x] Somente autor humano presente na allowlist pode receber o aviso.
- [x] Mensagens de bot e webhook nao geram resposta, evitando ciclo.
- [x] Mencao usa `parse=[]` e lista explicita com somente o autor validado.
- [x] Mensagem invalida nunca e persistida como resposta nem enviada a GUI.
- [x] Cursor avanca depois de uma tentativa de aviso, inclusive em timeout
      incerto, para impedir duplicacao automatica.
- [x] Nenhum token, webhook ou conteudo invalido e incluido no log.

### Risco residual

Um usuario permitido que converse normalmente no canal dedicado enquanto
existir pergunta pendente recebera orientacao. O canal deve permanecer dedicado
ao fluxo de perguntas. Falha do webhook pode impedir um aviso; por seguranca,
o sistema nao repete uma entrega cujo resultado externo seja incerto.

## Task 016 - Bandeja e entrada nativa

- [x] `codex queue` recebe lista de argumentos e nunca usa shell.
- [x] Sessao, endpoint e nomes de variavel rejeitam quebras de linha e NUL.
- [x] Endpoint remoto aceita somente `ws://`, `wss://` ou `unix://`.
- [x] Entrada remota exige nome de variavel e token presente no ambiente.
- [x] Valor do token nao entra em argumentos, `control.json` ou logs.
- [x] `control.json` usa gravacao atomica e modo `600` em POSIX.
- [x] Automacao de tarefas, entrada nativa, fallback GUI, destino remoto e sync
      possuem gates independentes.
- [x] Uma falha nativa nao inicia fallback nem retry automatico.
- [x] Sessao inferida vem somente de hook do mesmo worker.
- [x] PySide6 e importado somente quando a bandeja e iniciada.

### Risco residual

Quem controla a sessao local do usuario pode alterar `control.json` ou a
variavel de token. O app-server remoto do Codex e experimental e precisa de
TLS/tunel, autenticacao, firewall e revisao depois de atualizacoes. Habilitar
automacao e uma autorizacao persistente: desabilite-a ao terminar a cadeia de
tarefas.

O texto de `--message` e um argumento do processo `codex queue` e pode ficar
temporariamente visivel a ferramentas locais de inspecao de processos. Nao use
esse transporte para enviar senhas, tokens ou outros segredos.

## Task 017 - Despacho destacado na propria sessao

- [x] A deteccao compara somente o alvo exato com `CODEX_SESSION_ID` e
      `CODEX_THREAD_ID`.
- [x] O subprocesso continua usando lista de argumentos e nunca usa shell.
- [x] Entrada e saidas do processo destacado sao isoladas em `DEVNULL`.
- [x] POSIX cria nova sessao; Windows cria novo grupo sem janela.
- [x] `dispatch_started` nao grava atividade nem simula trabalho no Protocolo 2.
- [x] Falha ao criar o processo e reportada sem retry.
- [x] Falha posterior, ausencia de hook ou resultado incerto nao causa retry.
- [x] A bandeja sempre usa despacho destacado e permanece responsiva.
- [x] Hook isolado nao e tratado como prova da autoria de uma mensagem.
- [x] E2E nativo exige marcador exclusivo e confirmacao de que o humano nao o
      digitou.

### Risco residual

Depois que o processo destacado e criado, seu erro de saida nao retorna ao
chamador. Isso e intencional para romper a espera circular. A ausencia de hook
mantem o relogio de atividade inalterado e permite que o monitor alerte; o
operador deve diagnosticar antes de autorizar um novo envio.

A convencao humana `prossiga` versus automacao `continue` reduz ambiguidades,
mas nao constitui controle de acesso nem correlacao criptografica. Um teste
formal continua dependendo de marcador unico e trilha de auditoria.

## Task 019 - Gate do runtime Windows

- [x] Windows fica desabilitado por default seguro.
- [x] O opt-in e um booleano explicito e nao contem segredo.
- [x] O bloqueio ocorre antes de banco, rede, GUI ou instalacao operacional.
- [x] `--dry-run` nao contorna o gate.
- [x] Hooks Windows desabilitados falham abertos sem criar atividade falsa.
- [x] Parada de alarme, encerramento e desinstalacao permanecem acessiveis.
- [x] Nenhum backend, teste ou fonte Windows foi removido.

### Risco residual

Definir `PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true` libera uma integracao que
ainda nao passou pelo gate externo real desta release. O operador deve usar uma
maquina de teste, desktop desbloqueado e dados nao sensiveis. O opt-in nao deve
ser distribuido em configuracoes Linux ou tratado como garantia de suporte.

## Task 020 - Entrega nativa de respostas Discord

- [x] Transporte e sessao sao congelados antes de publicar a pergunta.
- [x] Sessao ausente, antiga ou ambigua falha antes de acessar o Discord.
- [x] `codex queue` recebe lista de argumentos e nunca usa shell.
- [x] Resposta Discord nunca e interpretada como comando do sistema.
- [x] Falha nativa nao ativa fallback GUI nem retry automatico.
- [x] O observer aceita cada resposta correlacionada no maximo uma vez.
- [x] Hook de outra sessao nao confirma entrega nativa.
- [x] Destino remoto exige gate, endpoint e nome de variavel de token.
- [x] O valor do token remoto nao entra no SQLite, argumentos ou logs.
- [x] Bancos existentes recebem somente colunas nullable e preservam dados.
- [x] Modo `store` permite desativar entrega sem perder respostas autorizadas.

### Risco residual

O texto autorizado e passado como argumento de `codex queue` e pode ficar
temporariamente visivel a ferramentas locais de inspecao de processos. Nao use
o canal para senhas ou tokens. `input_emitted` comprova somente conclusao do
transporte; mesmo um hook posterior da sessao correta nao prova que o agente
interpretou corretamente a resposta. Timeout ou rejeicao permanecem incertos e
exigem verificacao humana antes de um retry manual.
