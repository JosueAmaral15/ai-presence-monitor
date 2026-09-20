# Decisions

## 2026-09-20 - Linux system observers report local facts only

**Decision**: implement process, network, power and user-service collection as
independent read-only sources behind one Linux-only `observe-linux-state`
command. Enable local network and power sampling by default; require explicit
PID and service targets. Do not add a background-service installer in Phase 4.

**Reason**:

- local route/link state is useful evidence but cannot prove Internet or DNS;
- an observer cannot execute while suspended, but two clocks can prove a resume
  gap after execution continues;
- process-name discovery is ambiguous across concurrent Codex sessions, while
  explicit PID plus expected `comm` and start ticks is bounded and auditable;
- optional systemd units must not be treated as required without operator
  selection;
- one explicit watcher is enough to validate collection before adding daemon
  lifecycle and diagnosis policies.

**Consequence**:

The observer is one-shot by default and writes only expiring diagnostic facts
for an active exact worker. `--watch` preserves process and power baselines and
stops after `finish`. No collector updates presence, calls external networks,
reads sensitive process payloads, diagnoses a cause, notifies or recovers.

## 2026-09-14 - Diagnostic evidence never extends presence

**Decision**: recognized Codex hooks may produce both their existing presence
observation and a separate expiring diagnostic fact. Account-limit polling
produces only diagnostic evidence. Persisting either diagnostic record must not
update protocol clocks, worker lifecycle, alert rearming or public heartbeat.

**Reason**:

- a hook is direct evidence of session activity and already owns a presence
  observation, while its diagnostic interpretation has a separate lifetime;
- an account limit is context about a possible interruption, not proof that the
  worker performed useful work;
- coupling observer polling to `last_activity_at` would hide genuine Protocol 2
  inactivity indefinitely;
- diagnosis, notification and recovery still need correlation and dedicated
  policies in later phases.

**Consequence**:

Hook diagnostic evidence uses constant allowlisted mappings and a configured
TTL. `observe-codex-limits` is one-shot by default; explicit `--watch` rechecks
the exact worker and stops after `finish`. Neither path can subscribe to live
thread events, notify, alarm, send input or recover a session.

## 2026-09-14 - App Server polling and live observation are separate adapters

**Decision**: use a dedicated stdio App Server only for bounded persisted
thread and account-limit reads. Do not treat it as a live observer for a Codex
GUI/CLI session owned by another process. Keep a shared-endpoint live adapter
disabled until its session topology and exact-thread events pass E2E.

**Reason**:

- metadata-only `thread/read` and `account/rateLimits/read` succeeded locally;
- the child reported the current GUI-owned thread as `notLoaded`;
- explicit `thread/resume(excludeTurns=true)` was rejected with JSON-RPC
  `-32600`, classified without raw text as `thread_already_active`;
- connection-scoped event subscriptions cannot prove activity in an
  independently owned GUI session;
- existing same-session hooks already provide authoritative lifecycle evidence
  without taking ownership of the session.

**Consequence**:

Task 022 Phase 3 may combine Codex hooks with sanitized account-limit polling.
It must not infer `codex_closed` from the child-local `notLoaded` state. Live
App Server events require sessions intentionally hosted by a managed or
multiplexed endpoint, and no failed attach may trigger retry or recovery.

## 2026-09-13 - Evidence observers do not diagnose or recover

**Decision**: diagnostic observers will persist bounded facts. A separate
diagnosis engine will correlate evidence, and a separate incident state machine
will own notification lifecycle. Recovery remains an optional downstream
component that is disabled by default.

**Reason**:

- process, network and Codex signals can coexist or contradict one another;
- inactivity alone cannot prove why an AI-worker stopped producing evidence;
- one policy owner is required to deduplicate Discord notifications;
- collection must remain safe even when a notification or recovery integration
  is unavailable;
- recovery needs stricter authorization and E2E evidence than observation.

**Alternatives considered**:

- let each observer send its own alert: rejected because it creates duplicate
  and contradictory incidents;
- encode the final cause directly in protocol alerts: rejected because presence
  severity and interruption cause are independent concerns;
- retry `continue` whenever hooks stop: rejected because network failure,
  pending user input, sleep and usage limits require different actions.

**Consequence**:

Task 022 first adds an unused additive persistence foundation. Live observers,
classification, Discord messages and recovery require later phases and their
own validation. At most one diagnostic incident may remain open for a worker,
while immutable diagnoses preserve why that incident changed over time.

## 2026-09-13 - Excecao de CI para release Linux privada 0.7.0

**Decisao**: permitir a promocao da versao 0.7.0 para `main` sem uma execucao
GitHub-hosted da CI, exclusivamente para o uso privado e Linux autorizado pelo
usuario nesta release.

**Motivo**:

- a conta GitHub continua impedindo que os jobs iniciem por uma restricao de
  cobranca, nao por falha observada do codigo;
- a matriz local executa os 171 testes em Python 3.10, 3.11 e 3.12;
- cobertura, Ruff, mypy, build e verificacao de diff passam localmente;
- o E2E real Discord-observer-Codex comprova a integracao externa critica;
- Windows permanece experimental e desabilitado por padrao.

**Limite**:

Esta e uma excecao explicita e revogavel para a release privada 0.7.0. Ela nao
transforma CI remota indisponivel em sucesso, nao autoriza publicacao publica e
nao comprova o runtime Windows. Uma release publica ou a habilitacao Windows
deve restaurar os gates externos correspondentes.

**Consequencia**:

Depois do E2E e da estabilizacao do observer, o trabalho pode seguir de uma
branch de tarefa para `develop` e entao para `main`, preservando a evidencia
local e a limitacao da release nos documentos.

## 2026-09-12 - Linux estavel e Windows com opt-in experimental

**Decisao**: publicar a versao 0.6.2 com Linux habilitado e suportado por
padrao, preservando integralmente os adaptadores Windows atras de
`PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true`.

**Motivo**:

- a implementacao Windows existe, mas o gate externo real ainda nao foi
  executado por bloqueio da conta GitHub;
- remover o codigo perderia trabalho reutilizavel e dificultaria a validacao
  futura;
- permitir o runtime por padrao faria a release prometer um suporte ainda nao
  comprovado;
- um gate central e reversivel evita condicionais espalhadas nos casos de uso.

**Alternativas consideradas**:

- apagar Windows: rejeitado porque o problema e de maturidade, nao de desenho;
- manter Windows como gate obrigatorio: rejeitado para esta release porque
  impediria a publicacao Linux por uma integracao externa nao validada;
- tratar `--dry-run` como excecao: rejeitado porque comandos historicos podem
  criar estado local mesmo sem rede ou GUI.

**Consequencia**:

A Abstract Factory continua contendo as familias Linux e Windows. O guard
central bloqueia efeitos operacionais no Windows, enquanto ajuda, diagnostico,
`finish`, `stop-alarm`, desabilitacao de controles e desinstaladores permanecem
disponiveis. A CI Linux e obrigatoria; a matriz Windows permanece manual,
experimental e nao bloqueante.

## 2026-09-11 - Despacho destacado para a propria sessao Codex

**Decisao**: detectar quando o alvo de `codex queue` e a sessao do processo
chamador e iniciar o CLI em segundo plano, retornando `dispatch_started` sem
sincronizar presenca.

**Motivo**:

- o E2E demonstrou que a chamada sincrona pode esperar pelo turno que ela
  propria precisa encerrar;
- timeout e um resultado incerto: a mensagem chegou depois do limite e nao
  poderia ser reenviada com seguranca;
- criar atividade no momento do spawn produziria falso positivo no Protocolo 2;
- a bandeja nao pode bloquear seu event loop aguardando uma sessao ocupada.

**Alternativas consideradas**:

- aumentar o timeout: descartado porque nao remove a dependencia circular;
- marcar `input_emitted` no spawn: rejeitado porque criacao de processo nao
  prova aceite ou processamento;
- retry depois do timeout: rejeitado por risco de duplicacao;
- sempre executar sincronicamente: preservado apenas via `--no-detach` para
  diagnosticos que nao rodem dentro do proprio alvo.

**Consequencia**:

`CODEX_SESSION_ID` e `CODEX_THREAD_ID` ativam o modo automaticamente. POSIX usa
uma nova sessao de processo e Windows usa um novo grupo sem janela. O hook
posterior e evidencia de atividade e atualiza o monitor normalmente, mas um
teste de mensagem exige marcador exclusivo para atribuir a origem.

## 2026-09-11 - Entrada nativa antes do fallback GUI

**Decisao**: usar `codex queue` como transporte preferencial para mensagens de
continuidade e composicao manual. Manter X11/Win32 como fallback opt-in.

**Motivo**:

- a entrada nativa nao ocupa mouse, teclado ou clipboard do usuario;
- uma sessao UUID/nome exato e um alvo mais estavel que coordenadas visuais;
- o mesmo comando funciona no Linux e Windows quando o Codex CLI esta presente;
- `--remote` permite direcionar um app-server autenticado no computador cliente.

**Alternativas consideradas**:

- PyAutoGUI global: descartado por interferir no desktop e depender de foco;
- acessibilidade/seletores graficos: mantidos fora desta fase porque a interface
  do Codex nao publica um contrato estavel de elementos para terceiros;
- timer periodico de `continue`: rejeitado porque pode simular trabalho e
  esconder inatividade real;
- fallback automatico depois de falha nativa: rejeitado por risco de duplicar
  uma entrada cujo resultado e incerto.

**Consequencia**:

`auto` usa nativo quando existe sessao do mesmo worker e somente considera GUI
quando o usuario habilita o fallback. `input_emitted` ainda exige hook posterior
para confirmar processamento. Como `queue`/`app-server` sao experimentais no
Codex CLI atual, a integracao deve ser revalidada apos atualizacoes.

## 2026-09-11 - Bandeja como painel de autorizacao

**Decisao**: compartilhar um `control.json` entre CLI e bandeja e manter PySide6
como extra opcional.

**Motivo**:

- o usuario precisa alterar permissoes sem editar `.env` ou reiniciar o app;
- outro AI-worker precisa consultar exatamente as mesmas decisoes pela CLI;
- a instalacao base nao deve carregar toolkit grafico em servidores;
- tokens nao devem ser duplicados em estado de interface.

**Consequencia**:

O arquivo e atomico, privado em POSIX e guarda flags, sessao, endpoint e nome da
variavel de token. A bandeja nao inicia automaticamente no login e nao agenda
mensagens por tempo; esses limites permanecem explicitos.

## 2026-08-11 - Abstract Factory para integracoes Linux e Windows

**Decisao**: selecionar dispatcher GUI, backend de alarme e gerenciador de
execucao continua por uma Abstract Factory de plataforma.

**Motivo**:

- agora existem duas familias concretas com os mesmos tres produtos;
- `continue`, respostas remotas e alarme nao devem conhecer APIs nativas;
- Windows precisa de Win32, Task Scheduler e identidade de processo propria;
- condicionais `if sys.platform` nos casos de uso aumentariam acoplamento.

**Alternativas consideradas**:

- apenas documentar o launcher `.exe`: rejeitado porque nao oferece GUI, alarme
  controlado nem execucao continua;
- adicionar condicionais em cada modulo: rejeitado por duplicar selecao;
- usar `pyautogui` e `psutil`: rejeitado para manter zero dependencias Python de
  runtime e usar garantias nativas.

**Consequencia**:

Linux preserva X11, `/proc`, GNU `timeout` e systemd. Windows usa Win32 via
`ctypes`, runner Python, `taskkill` e Task Scheduler. Wayland e macOS continuam
fora do escopo. O schema SQLite e o `.env` permanecem compativeis.

## 2026-08-01 - Duracao maxima obrigatoria do alarme local

**Decisao**: executar `RED_ALERT_COMMAND` sob GNU `timeout`, com limite padrao
de 15 segundos configurado por `RED_ALERT_MAX_DURATION_SECONDS`.

**Motivo**:

- um alerta vermelho deve produzir um disparo audivel, nao som permanente;
- comandos existentes podem conter `ffplay -loop 0`;
- uma thread no monitor perderia o temporizador se o servico reiniciasse;
- o limite externo sobrevive independentemente do processo pai.

**Consequencia**:

Todo alarme termina automaticamente. `stop-alarm` permanece como interrupcao
manual antecipada. Sem GNU `timeout` ou com duracao invalida, o sistema falha
fechado antes de iniciar o som.

## 2026-08-01 - Vermelho unico por episodio de inatividade

**Decisao**: o alerta vermelho nao participa da repeticao periodica. Depois do
primeiro vermelho, Discord, Telegram e escalada externa permanecem silenciosos
ate uma atividade valida rearmar o worker.

**Motivo**:

- repeticao a cada cinco minutos gera ruido sem acrescentar informacao;
- o primeiro vermelho ja comunica a severidade maxima;
- atividade real separa um episodio antigo de uma nova inatividade.

**Alternativas consideradas**:

- aumentar apenas o intervalo do vermelho: descartado porque ainda repetiria;
- controlar somente alarme/telefonia: descartado porque Discord e Telegram
  continuariam ruidosos;
- adicionar coluna ao SQLite: desnecessario, pois atividade ja limpa
  `last_alert_level` e `last_alert_at`.

**Consequencia**:

Amarelo e laranja continuam configuraveis. Configuracoes antigas que listem
`red` permanecem legiveis, mas o motor ignora esse nivel para repeticao.

## 2026-07-16 - Observer passivo para hooks do Codex

**Decisao**: implementar hooks do Codex como observer passivo que grava atividade no SQLite, sem enviar notificacoes diretamente.

**Motivo**:

- O hook roda dentro do ciclo do Codex; ele deve ser rapido e confiavel.
- Postar em Discord/Telegram dentro do hook aumentaria risco de lentidao, falha de rede ou ruido.
- O monitor ja existe e e o lugar correto para aplicar regras de atraso e escalonamento.

**Alternativas consideradas**:

- Enviar Discord diretamente no hook: descartado por acoplamento e risco operacional.
- Detectar atividade por CPU/processo: fraco, pois processo vivo nao prova progresso real.
- Exigir `touch` manual: funciona, mas causa falsos alertas em tarefas longas quando a IA esta ativa.

**Consequencia**:

O Protocolo 2 passa a poder ser observado automaticamente para Codex quando os hooks estiverem configurados.

## 2026-07-26 - Expediente como politica do monitor

**Decisao**: implementar janela de expediente e repeticao de alertas como politica do monitor, nao como parte do Protocolo 2.

**Motivo**:

- O Protocolo 1 e o Protocolo 2 definem o que conta como atraso.
- O expediente define quando esse atraso deve ser cobrado.
- Separar as duas regras evita duplicacao e permite reutilizar a mesma janela nos dois protocolos.

**Alternativas consideradas**:

- Embutir expediente no Protocolo 2: descartado porque deixaria o Protocolo 1 sem a mesma capacidade.
- Repetir alertas sem guardar timestamp: descartado porque nao haveria controle confiavel de intervalo.

**Consequencia**:

O monitor passa a considerar `PRESENCE_WORK_WINDOW_*` antes de enviar alertas e usa `last_alert_at` para repetir o mesmo nivel somente depois do intervalo configurado.

## 2026-07-27 - Pacote instalado e identidade por escopo

**Decisao**: distribuir a versao 0.2 como wheel e derivar workers por escopo sem
alterar o esquema SQLite.

**Motivo**:

- hooks ligados a um caminho de checkout quebram quando o projeto e movido;
- um worker global mistura projetos simultaneos;
- manter o `worker_id` como chave permite evoluir sem migracao destrutiva.

**Alternativas consideradas**:

- copiar o wrapper para cada projeto: descartado por duplicacao e manutencao;
- criar tabela nova de projetos/sessoes: adiado porque o ID composto atende ao
  requisito atual com menor risco;
- tornar `project` obrigatorio: descartado para preservar compatibilidade.

**Consequencia**:

O modo `global` continua disponivel, enquanto `project`, `session` e
`project-session` oferecem isolamento. O hook usa o Python absoluto da
instalacao e o servico systemd e gerado pela CLI.

## 2026-07-29 - Resposta Discord por polling e fallback GUI

**Decisao**: usar polling autenticado da API REST do Discord e entrega X11
opcional, em processo separado.

**Motivo**:

- o projeto continua sem dependencia externa;
- polling de um canal dedicado dispensa Gateway e servidor HTTP publico;
- resposta direta, ID de usuario e ID da mensagem oferecem correlacao explicita;
- a GUI e fallback local enquanto nao existe entrada nativa integrada.

**Alternativas consideradas**:

- Discord Gateway: adiado por dependencia e lifecycle adicionais;
- aceitar qualquer mensagem no canal: descartado por ambiguidade;
- escolher a primeira janela por titulo: descartado por risco de envio incorreto;
- reenvio automatico em falha: descartado por possivel efeito parcial;
- unir o observer ao monitor de alertas: descartado para isolar falhas.

**Consequencia**:

O recurso exige bot, `MESSAGE_CONTENT`, allowlist e canal dedicado. A entrega
GUI permanece desativada por padrao e o proximo hook do worker confirma a
atividade posterior.

## 2026-07-29 - Continue integrado com sincronizacao limitada

**Decisao**: integrar o envio de `continue` ao monitor e registrar uma
observacao somente depois de uma emissao GUI bem-sucedida para um worker ja
ativo.

**Motivo**:

- executar a automacao sem atualizar o Protocolo 2 pode gerar alerta de
  inatividade enquanto o Codex recebe a nova entrada;
- atualizar no agendamento ou antes do Enter registraria atividade que ainda nao
  ocorreu;
- auto-start esconderia erro de identidade ou ciclo de tarefa;
- o Protocolo 1 exige sinal publico e nao pode aceitar a automacao como
  heartbeat.

**Alternativas consideradas**:

- atualizar `last_activity_at` ao iniciar o delay: descartado por evidenciar uma
  acao ainda nao emitida;
- aguardar somente hook posterior: mantido como confirmacao, mas insuficiente
  para evitar alerta durante o processamento inicial;
- criar tabela nova: descartado porque `events` e `record_observation` atendem
  ao requisito sem migracao;
- incorporar PyAutoGUI: descartado pela arvore de dependencias e pelo fallback
  global de coordenadas;
- escolher a primeira janela encontrada: descartado por ambiguidade.

**Consequencia**:

`observation:automation:continue` atualiza `last_activity_at`, preserva
`last_signal_at` e fica auditavel. Se nenhum hook ou outra atividade ocorrer, o
Protocolo 2 volta a alertar depois dos limites normais.

## 2026-07-29 - Layout `src/`

**Decisao**: mover o pacote instalavel para `src/ai_presence_monitor`.

**Motivo**:

- separar fonte importavel de artefatos na raiz;
- testar o pacote em condicoes mais proximas da instalacao;
- impedir que um diretorio antigo masque falhas de empacotamento.

**Consequencia**:

Comandos de desenvolvimento usam instalacao editavel ou `PYTHONPATH=src`.
Wrappers locais explicitam `src/`, e o wheel continua expondo o mesmo namespace
e os mesmos entrypoints.

## 2026-07-29 - Comando estavel para AI-workers

**Decisao**: usar o console script `ai-presence` como contrato de automacao e
documentar uma maquina de estados para AI-workers.

**Motivo**:

- aliases dependem de configuracao de shell interativo;
- hooks, CI, subprocessos e servicos precisam de um caminho executavel estavel;
- `pip` gera launchers adequados para Linux e Windows;
- a identidade por projeto e mais confiavel que o titulo visual de uma aba.

**Alternativas consideradas**:

- alias Bash: descartado como contrato principal por nao ser portatil nem
  carregado de forma consistente;
- controlar uma aba por seu rotulo: descartado porque uma aba do terminal pode
  nao ser uma janela X11;
- Abstract Factory imediata: foi adiada nesta decisao; a versao 0.5.0 passou a
  usa-la depois da implementacao dos adaptadores Windows concretos.

**Consequencia**:

`AGENTS.md` e `docs/AI-WORKER-COMMAND-PROTOCOL.md` definem os comandos. Esta
lacuna foi fechada na versao 0.5.0 com Task Scheduler e dispatcher Win32.

## 2026-07-30 - Alarme local controlado por PID

**Decisao**: iniciar o alarme em grupo proprio, persistir identidade minima do
processo e oferecer `stop-alarm`.

**Motivo**:

- comandos como `ffplay -loop 0` nao terminam sozinhos;
- `Popen` sem `wait()` pode deixar processo zumbi;
- buscar e matar qualquer `ffplay` pode interromper audio nao relacionado;
- alertas repetidos nao devem acumular processos de som.

**Consequencia**:

O estado usa permissao `600` e nao guarda o comando em texto. A parada valida
PID, fingerprint e token de inicio antes de `SIGTERM`; `SIGKILL` e fallback
configuravel.

## 2026-09-08 - Limite de reinicio exclusivo do reply observer

**Decisao**: manter a recuperacao rapida do monitor principal e aplicar ao
reply observer Linux tres tentativas em cinco minutos, com espera de 30
segundos e reinicio somente em falha.

**Motivo**:

- um `403` persistente produziu reinicios a cada cinco segundos;
- o observer depende de rede e permissoes externas, ao contrario do nucleo do
  monitor;
- Windows ja limita reinicios da tarefa a tres falhas;
- interromper o ciclo protege recursos e torna o erro observavel.

**Alternativas consideradas**:

- alterar o monitor e o observer juntos: descartado porque reduziria a
  resiliencia do monitor;
- retry infinito com backoff dentro do Python: adiado por adicionar estado e
  complexidade sem necessidade atual;
- manter cinco segundos sem limite: descartado depois do ciclo real de `403`.

**Consequencia**:

Depois de atingir o limite, o operador corrige a causa, executa `systemctl
--user reset-failed ai-presence-reply-observer.service` e inicia a unidade. A
definicao continua sem segredos e usa o mesmo Python instalado.

## 2026-09-09 - Orientar resposta Discord invalida sem relaxar a correlacao

**Decisao**: enquanto houver pergunta pendente no canal, publicar uma
orientacao para cada mensagem invalida de usuario autorizado.

**Motivo**:

- rejeitar silenciosamente nao ensina o usuario a usar **Responder**;
- texto vazio pode indicar `Message Content Intent` desativado;
- a allowlist permite direcionar a orientacao sem notificar terceiros;
- o E2E real demonstrou a lacuna sem provocar entrada GUI indevida.

**Alternativas consideradas**:

- aceitar mensagem solta mais recente: descartado por remover correlacao;
- orientar qualquer autor: descartado por ruido e divulgacao do fluxo;
- repetir aviso ate obter sucesso: descartado porque timeout de webhook tem
  resultado incerto e pode duplicar mensagens;
- persistir nova tabela de avisos: descartado porque o cursor existente ja
  fornece uma tentativa por mensagem e nao ha requisito de consulta historica.

**Consequencia**:

Ausencia de referencia, referencia sem pergunta pendente ou texto vazio gera
uma tentativa de orientacao e contadores no log. A mensagem invalida nao vira
resposta, nao toca a GUI e nao altera o estado da pergunta.

## 2026-09-13 - Vincular resposta Discord a sessao Codex imutavel

**Decisao**: selecionar `native`, `gui` ou `store` quando a pergunta e criada e
persistir o identificador exato da sessao para entrega nativa por `codex queue`.

**Motivo**:

- a janela em foco nao identifica de forma estavel a tarefa que perguntou;
- o projeto ja possui um cliente nativo sem shell e um E2E aprovado;
- varias sessoes podem compartilhar o mesmo worker com escopo de projeto;
- correlacao de confirmacao precisa incluir a sessao, nao apenas o worker;
- a escolha antecipada impede fallback silencioso depois de resultado incerto.

**Alternativas consideradas**:

- manter somente GUI: rejeitado por depender de foco, desktop e coordenadas;
- selecionar a sessao no momento da resposta: rejeitado porque o alvo poderia
  mudar durante a espera humana;
- fallback GUI automatico depois de timeout nativo: rejeitado por risco de
  duplicacao;
- exigir App Server direto nesta fase: adiado; `codex queue` ja oferece o
  contrato necessario e fica isolado pela Strategy de transporte.

**Consequencia**:

`ask-user` falha antes da publicacao quando um alvo nativo nao pode ser
determinado sem ambiguidade. O observer entrega uma vez ao alvo salvo e um hook
so confirma nativo quando pertence a mesma sessao. GUI continua disponivel por
opt-in e `store` desativa entrega preservando a resposta no SQLite.
