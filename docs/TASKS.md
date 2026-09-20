# Tasks - AI Presence Monitor

## Concluidas em 2026-09-20

### Task 023 - E2E de recuperacao e release Linux privada 0.8.0

**Prioridade**: Critica
**Status**: concluida; release privada Linux 0.8.0 validada, publicada em
`develop` e `main`, com excecao CI externa limitada e documentada
**Objetivo**: comprovar um unico recovery nativo na sessao Codex exata,
validar o pacote instalado e promover a release Linux privada 0.8.0.

- [x] E2E isolado usa marcador unico, banco temporario e um unico despacho.
- [x] Usuario confirma uma notificacao Discord e o marcador automatico no
      Codex; hook posterior da mesma sessao confirma atividade.
- [x] Versao, changelog, decisoes, seguranca e rollback sao atualizados.
- [x] Gate completo, matriz Python, build, instalacao isolada e smokes Linux
      passam no candidato final.
- [x] Excecao de CI privada 0.8.0 e registrada porque o run `35514873721`
      continuou bloqueado externamente.
- [x] Task branch e integrada e publicada em `develop`; `main` recebe somente
      o candidato integralmente validado.

**Plano**: `docs/planning/TASK-023-recovery-e2e-release-080.md`.

### Task 022 - Diagnostico de causa por observers

**Prioridade**: Alta
**Status**: fases 1 a 8 e E2E real de recuperacao concluidos; adapter live
deferido como tarefa futura nao bloqueante da release Linux privada 0.8.0
**Objetivo**: distinguir causas conhecidas de uma interrupcao de atividade e
gerenciar um unico incidente correlacionado antes de enviar notificacoes.

**Fase 1**:

- [x] Tipos de evidencia, diagnostico, confianca, severidade e incidente.
- [x] Schema SQLite aditivo e inicializacao compativel com `PresenceStore`.
- [x] Correlacao obrigatoria por worker e sessao Codex.
- [x] Um unico incidente aberto por worker, atualizavel e resolvivel.
- [x] Testes focados de migracao, validacao e ciclo de incidente.
- [x] Gate local completo: 177 testes nas versoes Python 3.10, 3.11 e 3.12,
      87% de cobertura, Ruff, mypy, build e diff aprovados.
- [x] Commit da sessao e integracao local em `develop`.

**Fase 2**:

- [x] Cliente stdio com allowlist que nao oferece envio de input.
- [x] `thread/read(includeTurns=false)` da sessao exata validado localmente.
- [x] Leitura estruturada e sanitizada dos limites da conta validada.
- [x] Sanitizacao de status, erros, uso agregado e compactacao testada.
- [x] Tentativa controlada de assinatura rejeitada com
      `thread_already_active`; child separado nao observa sessao ativa da GUI.
- [x] Limite arquitetural e instrucoes para humanos e AI-workers documentados.
- [x] Gate completo: 189 testes nas versoes Python 3.10, 3.11 e 3.12,
      86% de cobertura, Ruff, mypy, build e diff aprovados.

**Fase 3**:

- [x] Hooks Codex reconhecidos tambem registram evidencia diagnostica curta e
      expiram sem armazenar payload, prompt, mensagem ou nome de ferramenta.
- [x] `observe-codex-limits` consulta somente `account/rateLimits/read` em um
      App Server filho e persiste estado sanitizado para o worker exato.
- [x] Polling e TTL possuem configuracao positiva, modo one-shot padrao e
      `--watch` explicito que encerra quando o worker deixa de estar ativo.
- [x] Evidencia diagnostica nao atualiza `last_activity_at`, `last_signal_at`
      nem rearma alertas de presenca.
- [x] Live subscription, diagnostico, incidentes, notificacao, alarme, input e
      recuperacao permanecem desabilitados.
- [x] Gate completo: 203 testes nas versoes Python 3.10, 3.11 e 3.12,
      86% de cobertura, Ruff, mypy, build e diff aprovados.
- [x] Dry-run real do App Server retornou `usage_available` sem escrever SQLite.
- [x] Commit da sessao e integracao local em `develop`.

**Fase 4**:

- [x] Processo Linux exige PID explicito e pode validar nome e troca por start
      ticks sem ler `cmdline`, ambiente ou arquivos abertos.
- [x] Rede observa apenas rota e links locais, sem afirmar acesso a Internet.
- [x] Energia detecta retomada entre amostras pelos relogios de boot e
      monotonic; coleta one-shot nao inventa historico de suspensao.
- [x] Servicos `.service` explicitos usam `systemctl --user show` sem shell e
      persistem somente estados sanitizados.
- [x] `observe-linux-state` oferece one-shot, dry-run e `--watch`, revalidando o
      worker antes e depois de cada coleta.
- [x] Configuracao, seguranca, arquitetura e guias humanos/AI foram atualizados.
- [x] Dry-run local validou processo, rota, energia e dois servicos ativos sem
      escrever SQLite.
- [x] Gate completo: 226 testes nas versoes Python 3.10, 3.11 e 3.12,
      87% de cobertura, Ruff, mypy, build e diff aprovados.
- [x] Commit da sessao e integracao local em `develop`.

**Fases finais e escopo deferido**:

- [ ] **Deferido, nao bloqueante**: adapter live somente para sessoes hospedadas
      em endpoint compartilhado, com autenticacao e E2E proprios.
- [x] E2E real de recuperacao usou sessao exata nao critica, marcador unico,
      autorizacao explicita, um despacho, relogio de presenca inalterado e hook
      posterior da mesma sessao.
- [x] Motor de diagnostico, precedencia, confianca e transicoes, com 242 testes
      aprovados em Python 3.10, 3.11 e 3.12, 87% de cobertura total e dry-run
      real sem escrita.
- [x] Notificacao Discord deduplicada com 259 testes em Python 3.10, 3.11 e
      3.12, 87% de cobertura total, 98% no modulo novo e dry-run real sem
      mensagem externa nem registro de tentativa.
- [x] Teste Discord E2E autorizado entregou uma mensagem, deduplicou a
      repeticao e teve exatamente um marcador confirmado pelo usuario no canal
      `warnings-worker-robot`; fault injection e gates passaram.
- [x] Recuperacao one-shot opcional implementada e validada com 271 testes em
      Python 3.10, 3.11 e 3.12, 88% de cobertura total, 93% no coordenador e
      dry-run real `no_open_incident`; nenhum input real foi autorizado ou
      emitido. Integrada localmente em `develop` pelo commit de task `e526782`.

**Plano**: `docs/planning/TASK-022-cause-aware-diagnostics.md`.

## Concluidas em 2026-09-13

### Task 021 - E2E nativo Discord e release Linux

**Prioridade**: Critica
**Status**: concluida; release 0.7.0 integrada e publicada em `develop` e
`main`
**Objetivo**: provar uma entrega unica da resposta Discord para a sessao exata
do Codex, estabilizar o observer e promover o resultado validado ate `main`.

**Criterios de aceite**:

- [x] Runtime local atualizado de 0.6.1 para 0.7.0 com rollback privado.
- [x] Observer recuperado da falha DNS e preflight Discord aprovado.
- [x] Sessao, transporte nativo/local e marcador exclusivo congelados.
- [x] Primeira pergunta invalidada antes da entrega; uma unica pergunta valida
      aceita e entregue, com GUI e retry automatico desabilitados.
- [x] Resposta direta aceita e entregue uma vez a sessao exata.
- [x] Hook da mesma sessao produz `delivery_confirmed`.
- [x] Observer reiniciado e estavel depois do teste.
- [x] Gate local completo passa com 171 testes e 86% de cobertura.
- [x] Evidencia final integrada em `develop` e promovida a `main`.

**Plano**: `docs/planning/TASK-021-native-discord-e2e-release.md`.

### Task 020 - Entrega nativa de respostas Discord

**Prioridade**: Alta
**Status**: concluida; implementacao e E2E real publicados na release 0.7.0
**Objetivo**: devolver cada resposta autorizada do Discord para a sessao exata
do Codex que publicou a pergunta, sem depender de foco, mouse ou teclado.

**Criterios de aceite**:

- [x] Pergunta congela transporte, sessao e destino antes da publicacao.
- [x] Entrega nativa reutiliza `codex queue` sem shell.
- [x] Sessao ausente, antiga ou ambigua falha fechada.
- [x] Falha nativa nao ativa GUI nem retry automatico.
- [x] Hook de outra sessao nao confirma entrega nativa.
- [x] GUI explicita e modo `store` permanecem disponiveis.
- [x] Migracao SQLite preserva perguntas existentes.
- [x] CLI, `.env.example`, arquitetura, seguranca e guias foram atualizados.
- [x] Gate local completo, build e instalacao isolada passam.
- [x] Commit da sessao e integracao funcional em `develop`.
- [x] E2E Discord-Codex real com marcador exclusivo e nova autorizacao.

**Plano**: `docs/planning/TASK-020-native-discord-answer-routing.md`.

## Concluida em 2026-09-12

### Task 019 - Release Linux com Windows experimental desabilitado

**Prioridade**: Critica
**Status**: concluida e integrada localmente em `develop`
**Objetivo**: habilitar oficialmente apenas Linux nesta release, preservando
todo o codigo Windows atras de opt-in experimental desabilitado por padrao.

**Criterios de aceite**:

- [x] Linux continua habilitado sem configuracao adicional.
- [x] Windows operacional falha antes de efeitos colaterais por padrao.
- [x] `PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true` libera os adaptadores
      preservados somente para validacao controlada.
- [x] Diagnostico, encerramento e rollback continuam disponiveis no Windows.
- [x] CI obrigatoria cobre Linux; Windows permanece manual e nao bloqueante.
- [x] Testes, seguranca, portabilidade, ambiente e rollback estao documentados.
- [x] Gate local completo, build e instalacao isolada passam.

**Plano**: `docs/planning/TASK-019-linux-stable-runtime-gate.md`.

**Conclusao (2026-09-12)**: 162 testes passaram em Python 3.10, 3.11 e
3.12; cobertura ficou em 87%; Ruff, mypy, build 0.6.2, instalacao isolada,
factory Linux, bandeja e servicos locais foram validados. O wheel preserva os
modulos Windows. A CI remota Linux continua indisponivel pelo bloqueio de
cobranca da conta GitHub e deve ser tratada na decisao de promocao para `main`.

### Task 017 - Despacho nativo nao bloqueante na propria sessao

**Prioridade**: Critica
**Status**: concluida; E2E nativo real aprovado na sessao exata
**Objetivo**: impedir que `codex queue` bloqueie o turno ativo ao enviar para a
propria sessao e evitar falso positivo de atividade antes do hook.

**Criterios de aceite**:

- [x] E2E com marcador exclusivo chega uma unica vez a sessao exata.
- [x] Mensagem identificavel e hook posterior confirmam o processamento no alvo.
- [x] Tentativa anterior foi reclassificada como inconclusiva depois que o
      usuario informou ter digitado manualmente o `continue` observado.
- [x] A propria sessao usa processo destacado no Linux e no Windows.
- [x] `dispatch_started` nao grava `observation:automation:continue` nem altera
      `last_activity_at`.
- [x] Bandeja nao bloqueia enquanto o Codex recebe a mensagem.
- [x] CLI oferece `--detach` e `--no-detach` para diagnostico.
- [x] Gate completo, wheel e instalacao isolada passam.
- [x] Trabalho funcional e integrado localmente em `develop`.

**Plano**: `docs/planning/TASK-017-native-self-queue.md`.

**Conclusao (2026-09-12)**: uma unica execucao autorizada retornou
`dispatch_started`; o marcador exclusivo apareceu uma vez como mensagem de
usuario na sessao `019f5691-c118-7370-a205-94cfde0a93d7`, sem digitacao humana,
e o hook `UserPromptSubmit` 2607 foi registrado em seguida para a mesma sessao.
Nao houve retry nem processo `codex queue` remanescente.

## Concluida em 2026-09-11

### Task 018 - Guia de uso para humanos e AI-workers

**Prioridade**: Alta
**Status**: concluida e integrada localmente em `develop`
**Objetivo**: oferecer uma referencia unica para seres humanos, AI-workers e
adaptadores utilizarem o monitor como ferramenta sem superestimar evidencias.

**Criterios de aceite**:

- [x] Guia cobre instalacao, controles, bandeja e fluxos humanos.
- [x] Guia cobre `start`, hooks, `touch`, perguntas, `continue` e `finish` para
      AI-workers.
- [x] Existe contrato para wrappers, MCP e function calling.
- [x] Estados `dry-run`, `dispatch_started`, `input_emitted`, hook e
      `delivery_confirmed` possuem limites explicitos.
- [x] E2E nativo exige marcador exclusivo e distingue `prossiga` manual de
      `continue` automatizado.
- [x] Registro anterior foi corrigido para tentativa inconclusiva.
- [x] AGENTS, READMEs, indice, seguranca e guias relacionados apontam para a
      nova norma.
- [x] Gate completo passa com 152 testes e 86% de cobertura.
- [x] Commit `c4197fe` foi integrado em `develop` pelo merge `aab9f4c`.

**Guia**: `docs/USO-COMO-FERRAMENTA.md`.

### Task 016 - Bandeja do sistema e entrada nativa do Codex

**Prioridade**: Alta
**Status**: concluida em `develop`; promocao para `main` aguarda os gates Linux
da Task 019; a validacao Windows foi reclassificada como experimental
**Objetivo**: permitir que usuario e AI-worker controlem autorizacoes de
automacao em uma bandeja e enviem texto para uma sessao exata do Codex sem
ocupar mouse ou teclado.

**Criterios de aceite**:

- [x] Transporte nativo usa `codex queue` sem shell ou automacao fisica.
- [x] `continue` seleciona transporte nativo ou fallback GUI explicitamente.
- [x] CLI e bandeja compartilham uma politica persistente fora do repositorio.
- [x] Menu da bandeja oferece habilitar automacao, responder mensagem e sair.
- [x] Preferencias permitem habilitar ou desabilitar cada ferramenta.
- [x] O compositor envia localmente ou a endpoint remoto autenticado.
- [x] Testes e documentacao cobrem seguranca, portabilidade e operacao.

**Plano**: `docs/planning/TASK-016-system-tray-native-input.md`.

### Task 012 - Adaptadores operacionais para Windows

**Prioridade**: Alta
**Status**: implementacao preservada como experimental; CI real pendente e
nao bloqueante para a release Linux da Task 019
**Objetivo**: oferecer no Windows as integracoes locais que antes existiam
somente no Linux, preservando os mesmos protocolos, banco e regras de alerta.

**Criterios de aceite**:

- [x] Uma Abstract Factory seleciona automaticamente a familia Linux ou Windows.
- [x] O dispatcher Windows captura e revalida uma unica janela visivel por
      identificador e titulo antes de clicar, digitar e pressionar Enter.
- [x] O alarme Windows possui duracao maxima, deduplicacao, identidade de
      processo e interrupcao manual sem depender de `/proc` ou GNU `timeout`.
- [x] O monitor e o observer de respostas podem ser registrados no Task
      Scheduler para iniciar no logon do usuario.
- [x] Comandos Linux existentes continuam compativeis.
- [x] A CLI oferece comandos portateis para instalar e remover execucao
      continua, alem dos comandos legados de systemd.
- [x] O menu interativo informa e usa a integracao da plataforma atual.
- [ ] A CI executa testes em Linux e Windows com Python suportado.
- [x] README, arquitetura, portabilidade, seguranca, rollback, decisoes e
      changelog documentam a implementacao.
- [x] Testes, cobertura, lint, tipos, build e verificacao de diff passam.

**Plano**: `docs/planning/TASK-012-windows-platform-adapters.md`.

**Checkpoint experimental**: os runs `31540396474` e `34660530783` nao iniciaram
nenhum job porque a conta GitHub esta bloqueada por problema de cobranca. O
segundo run foi criado pelo push de `develop` em 2026-09-11 e repetiu o mesmo
resultado nos seis jobs. A validacao Windows permanece pendente ate um run real
em `windows-latest` passar, mas nao bloqueia a release Linux 0.6.2.

## Concluidas

### Task 015 - E2E local do comando continue

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: validar, com autorizacao explicita, que o comando integrado
captura uma unica janela do Codex, aguarda o delay padrao, envia `continue` e
registra evidencia posterior de atividade.

**Criterios de aceite**:

- [x] Nao existe pergunta remota nem outra execucao de continuidade pendente.
- [x] O dry-run confirma mensagem, delay, worker, projeto e alvo esperados.
- [x] A janela configurada possui uma unica correspondencia visivel.
- [x] A execucao real termina com `input_emitted` sem retry automatico.
- [x] `continue` aparece como nova entrada no Codex GUI.
- [x] Um hook posterior confirma atividade do mesmo worker.
- [x] Evidencias e resultado final ficam registrados nesta tarefa.

**Conclusao (2026-09-11)**: a janela unica `ChatGPT` foi capturada no X11, o
delay padrao de 60 segundos terminou e `continue` apareceu nesta tarefa. O
banco registrou `observation:automation:continue` as `00:25:44` e
`observation:codex:UserPromptSubmit` as `00:25:45`, no mesmo worker, confirmando
a retomada sem retry automatico.

### Task 014 - Orientacao para respostas Discord invalidas

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: orientar no proprio Discord o usuario autorizado quando houver
pergunta dentro do prazo, mas sua mensagem nao estiver vinculada ou nao puder
ser lida.

**Criterios de aceite**:

- [x] Mensagem autorizada sem resposta direta recebe instrucao para usar
      **Responder**.
- [x] Conteudo ocultado pelo Discord recebe orientacao sobre
      `Message Content Intent`.
- [x] Bots, webhooks, usuarios nao autorizados e ausencia de pergunta pendente
      nao produzem lembrete.
- [x] Cada mensagem invalida causa no maximo uma tentativa, sem loop ou retry
      automatico.
- [x] Respostas validas e a protecao da GUI permanecem inalteradas.
- [x] Testes, documentacao, build e instalacao local passam.
- [x] E2E real confirma a orientacao e a resposta valida depois de habilitar
      `Message Content Intent`.

**Plano**: `docs/planning/TASK-014-discord-reply-guidance.md`.

**Conclusao (2026-09-10)**: `Message Content Intent` confirmado pela flag
`524288`. O fluxo orientou uma referencia incorreta e aceitou a resposta direta
seguinte, concluindo em `delivery_confirmed` sem retry ou falha GUI.

### Task 013 - Hardening operacional e E2E Discord-Codex

**Prioridade**: Critica
**Status**: concluida
**Objetivo**: impedir tempestade de reinicios do observer em falhas persistentes
e validar o fluxo real de pergunta, resposta correlacionada e entrega no Codex
GUI.

**Criterios de aceite**:

- [x] O reply observer limita reinicios sem alterar a recuperacao do monitor.
- [x] O gate de qualidade local passa integralmente.
- [x] Wheel atualizado e servicos reinstalados sao validados.
- [x] E2E Discord-Codex alcanca `delivery_confirmed` sem retry automatico.
- [x] Workers historicos sao reconciliados conforme decisao do usuario.
- [x] Evidencias, rollback e dependencias externas ficam documentados.

**Plano**: `docs/planning/TASK-013-operational-hardening-and-e2e.md`.

**Conclusao (2026-09-10)**: a resposta autorizada `MANTER AMBOS` foi entregue
e confirmada por hook. Os workers historicos de AmaralAgenda e Vinterholm
permanecem ativos conforme a decisao do usuario.

### Task 011 - Duracao limitada do alarme vermelho

**Prioridade**: Critica
**Status**: concluida
**Objetivo**: garantir que cada disparo sonoro vermelho termine
automaticamente, mesmo quando o comando configurado usa loop continuo.

**Criterios de aceite**:

- [x] Existe duracao maxima configuravel com padrao seguro.
- [x] Comando em loop termina automaticamente.
- [x] Estado e processo sao limpos depois do limite.
- [x] Parada manual continua disponivel.
- [x] Documentacao e testes cobrem o comportamento.

### Task 010 - Alerta vermelho unico por episodio

**Prioridade**: Critica
**Status**: concluida
**Objetivo**: impedir mensagens vermelhas repetitivas durante o mesmo periodo
continuo de inatividade e rearma-las somente apos atividade valida.

**Criterios de aceite**:

- [x] Primeiro vermelho e enviado normalmente.
- [x] Verificacoes seguintes permanecem silenciosas no mesmo episodio.
- [x] Nova atividade rearma o alerta vermelho.
- [x] Repeticao configuravel de amarelo e laranja continua funcionando.
- [x] Documentacao e testes refletem a politica.

### Task 009 - Interrupcao segura do alarme

**Prioridade**: Critica
**Status**: concluida
**Objetivo**: impedir alarmes locais interminaveis sem controle e processos
zumbis.

**Criterios de aceite**:

- [x] O processo do alarme e identificado sem armazenar o comando em texto.
- [x] Um alarme ativo impede o inicio de duplicata.
- [x] `stop-alarm` oferece parada normal e fallback forcado.
- [x] PID reutilizado ou estado obsoleto nao sinaliza processo incorreto.
- [x] O processo filho e coletado com `wait()`.
- [x] CLI, menu, documentacao e testes cobrem a interrupcao.

### Task 008 - UX de comandos para AI-workers

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: permitir que outra IA opere o monitor por um comando de terminal
estavel, com identidade explicita de projeto e protocolo documentado.

**Criterios de aceite**:

- [x] `ai-presence` pode ser exposto no `PATH` sem alias interativo.
- [x] `AGENTS.md` define regras operacionais e de seguranca.
- [x] O protocolo documenta `start`, hooks, `touch`, perguntas e `finish`.
- [x] Monitor, observer de respostas e dispatcher GUI sao diferenciados.
- [x] A limitacao de titulos de abas do terminal esta documentada.
- [x] Linux e Windows possuem limites de portabilidade explicitos.
- [x] Abstract Factory foi adiada ate existir um adaptador Windows concreto;
      a Task 012 implementa essa segunda familia.

### Task 007 - Unificacao com o comando de continuidade

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: incorporar ao AI Presence Monitor o envio programado da mensagem
`continue` para o Codex GUI, eliminar a necessidade de executar o projeto
`mouse-control-clicker` separadamente e organizar o pacote no layout `src/`.

**Criterios de aceite**:

- [x] Existe um unico pacote e uma unica CLI para monitoramento e continuidade.
- [x] A mensagem padrao e `continue` e o atraso padrao e 60 segundos.
- [x] O alvo GUI e validado sem selecionar silenciosamente uma janela ambigua.
- [x] O envio oferece `--dry-run`; Linux preserva o clipboard e Windows nao o
      altera.
- [x] Depois de uma emissao GUI bem-sucedida, um worker ja ativo recebe uma
      observacao auditavel de automacao.
- [x] No Protocolo 2, essa observacao sincroniza `last_activity_at` e reinicia
      a contagem de inatividade, evitando alerta falso logo apos `continue`.
- [x] Agendamento, `dry-run`, falha GUI e worker inativo nao atualizam
      `last_activity_at`.
- [x] No Protocolo 1, `continue` nao atualiza `last_signal_at` nem substitui o
      heartbeat publico obrigatorio.
- [x] Um hook posterior continua sendo a evidencia de que o Codex retomou
      atividade depois da entrada automatizada.
- [x] O menu interativo oferece o mesmo recurso.
- [x] O pacote usa layout `src/` com importacoes, hooks e scripts corrigidos.
- [x] O `.env` e o banco existentes permanecem compativeis e intocados.
- [x] Testes, cobertura, lint, tipos, wheel e instalacao isolada passam.
- [x] O projeto antigo nao e necessario para executar o fluxo integrado.
- [x] O projeto antigo permanece intacto; retirada ou arquivamento dependem de
      aprovacao explicita.

### Task 006 - Respostas remotas Discord para Codex GUI

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: correlacionar perguntas e respostas autorizadas no Discord e
entregar a resposta na janela exata do Codex GUI como fallback opcional.

**Criterios de aceite**:

- [x] Pergunta e resposta persistidas e correlacionadas no SQLite.
- [x] Observer aceita somente resposta direta de usuario autorizado.
- [x] Entrega GUI desativada por padrao e sem selecao ambigua de janela.
- [x] Estados `input_emitted` e `delivery_confirmed` auditaveis.
- [x] CLI, configuracao, seguranca e rollback documentados.
- [x] Testes automatizados e cobertura total >= 80%.

### Task 001 - Observer de hooks do Codex

**Prioridade**: Alta  
**Status**: concluida  
**Objetivo**: registrar evidencias locais de atividade do Codex por hooks, para que o Protocolo 2 alerte por ausencia real de atividade e nao apenas por ausencia de `touch` manual.

**Criterios de aceite**:

- [x] Hook recebe JSON do Codex via `stdin`.
- [x] Hook grava atividade no SQLite sem enviar notificacoes diretamente.
- [x] Hook nao bloqueia o Codex em caso de erro recuperavel.
- [x] CLI permite testar o hook manualmente.
- [x] Exemplo de `hooks.json` documentado.
- [x] README explica quando usar o observer.
- [x] Testes cobrem parsing, worker padrao e registro no banco.

### Task 002 - Instalador seguro de hooks do Codex

**Prioridade**: Alta  
**Status**: concluida  
**Objetivo**: permitir instalar e remover o hook do AI Presence Monitor em um arquivo `hooks.json` do Codex com backup, idempotencia e validacao.

**Criterios de aceite**:

- [x] Instalar hooks em `~/.codex/hooks.json` ou alvo informado.
- [x] Criar backup antes de modificar arquivo existente.
- [x] Nao duplicar hooks em reinstalacoes.
- [x] Remover somente hooks do AI Presence Monitor.
- [x] Permitir `--dry-run` para inspecionar sem escrever.
- [x] Testes cobrem merge, backup, instalacao e desinstalacao.

### Task 003 - Janela de expediente e repeticao de alertas

**Prioridade**: Alta  
**Status**: concluida  
**Objetivo**: permitir que o monitor cobre presenca apenas durante um intervalo
de expediente e repita alertas amarelos/laranjas enquanto o worker continuar
atrasado.

**Criterios de aceite**:

- [x] `.env` aceita janela de expediente com inicio, fim e timezone.
- [x] Monitor suprime alertas fora do expediente quando configurado.
- [x] Monitor pode repetir amarelo e laranja por intervalo configurado.
- [x] SQLite guarda `last_alert_at` para controlar repeticao.
- [x] Documentacao explica configuracao e comportamento.
- [x] Testes cobrem janela comum, janela noturna, supressao e repeticao.

## Backlog

- Projetar o adapter live somente quando as sessoes Codex puderem ser
  hospedadas em endpoint compartilhado autenticado; manter desabilitado ate
  passar isolamento e E2E de sessao exata.

## Concluida em 2026-07-27

### Task 004 - Portabilidade e reutilizacao

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: permitir instalar o monitor como pacote, reutiliza-lo em outros
projetos e isolar workers por projeto ou sessao sem caminhos fixos desta maquina.

**Criterios de aceite**:

- [x] Wheel instalavel e comandos de console funcionais.
- [x] Configuracao e banco independentes do diretorio de execucao.
- [x] Hook portatil e compativel com instalacoes antigas.
- [x] Escopos global, projeto e sessao testados.
- [x] Servico systemd de usuario gerado de forma idempotente.
- [x] Documentacao e rollback atualizados.

## Concluida em 2026-07-27

### Task 005 - Cobertura e revalidacao

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: elevar a cobertura total para pelo menos 80% e repetir toda a
validacao de portabilidade.

**Criterios de aceite**:

- [x] Cobertura total sem omissoes >= 80%.
- [x] CLI, menu interativo e notificadores com fluxos positivos e de erro.
- [x] Matriz Python 3.10-3.12 aprovada.
- [x] Wheel e integracoes locais revalidados.
