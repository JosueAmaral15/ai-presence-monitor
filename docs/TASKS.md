# Tasks - AI Presence Monitor

## Em andamento

### Task 053 - Release Linux 0.12.0

**Prioridade**: Critica
**Status**: em andamento
**Plano**: `docs/planning/TASK-053-release-0120.md`
**Objetivo**: publicar a sincronizacao bidirecional do chat e o schema 3 sob
uma versao minor propria, atualizar o runtime transacionalmente e promover
somente depois dos gates locais, hospedados e operacionais.

- [x] Validar o E2E Discord -> observer -> sessao Codex exata.
- [x] Incrementar os metadados para 0.12.0.
- [ ] Passar quality gate, matriz Linux e CI remoto da branch de release.
- [ ] Gerar e verificar o bundle canonico ligado ao commit candidato.
- [ ] Validar dry-run, upgrade 0.11.3 -> 0.12.0 e migracao 2 -> 3.
- [ ] Provar rollback 0.12.0 -> 0.11.3 com restauracao do banco.
- [ ] Reaplicar 0.12.0 e validar servicos, hooks, controles, bandeja e alarme.
- [ ] Promover por fast-forward para `develop` e `main` com CI verde.

### Task 052 - Sincronizacao bidirecional do chat com Discord

**Prioridade**: Alta
**Status**: concluida e validada com E2E Discord real
**Plano**: `docs/planning/TASK-052-bidirectional-discord-chat-sync.md`
**Objetivo**: manter perguntas e respostas explicitas do agente e do usuario
visiveis no chat local e no canal Discord configurado, preservando correlacao,
allowlist, sessao exata e estados de entrega independentes.

**Criterios de aceite**:

- [x] Mensagens explicitas do agente sao persistidas e espelhadas no Discord.
- [x] Mensagens humanas da bandeja chegam a sessao exata e sao espelhadas.
- [x] Respostas Discord continuam exigindo resposta direta correlacionada.
- [x] Falhas parciais ficam auditaveis sem duplicar mensagens ou repetir envio.
- [x] Estado do Discord aparece na bandeja e nos exports da CLI.
- [x] Configuracao, seguranca, rollback e protocolo do AI-worker documentados.
- [x] Testes automatizados e gates de pacote aprovados.

**Evidencia local (2026-11-03)**: 362 testes passaram em Python 3.10, 3.11 e
3.12; cobertura global de 86%; Ruff, mypy, compilacao, sintaxe shell, build de
wheel/sdist e `git diff --check` passaram. A janela de chat foi construida em
sessao grafica real usando HOME, configuracao e banco isolados.

O workflow remoto `Quality` da branch de tarefa tambem passou nos tres jobs
Linux (run `41721734878`).

**Evidencia E2E real (2026-11-03)**: uma resposta explicita do agente foi
persistida e publicada no Discord. A pergunta
`981016f5-2514-41a9-b3f6-1384c52f8657` recebeu uma resposta direta autorizada,
foi projetada no transcript sem duplicacao e despachada uma vez para a sessao
Codex exata. A sessao recebeu o envelope gerado pelo monitor
`[AI-PRESENCE-DISCORD-ANSWER:981016f5-2514-41a9-b3f6-1384c52f8657]`, seguido
do texto humano, e o hook operacional registrou atividade posterior as
21:06:11. Depois da inclusao do envelope, os 362 testes, a cobertura de 87%, o
quality gate e a matriz Python 3.10-3.12 passaram novamente.

### Task 051 - Release Linux 0.11.3

**Prioridade**: Critica
**Status**: concluida e promovida; publicacao externa nao executada
**Objetivo**: publicar a estabilizacao do alarme sob uma versao patch distinta,
atualizar o runtime transacionalmente e produzir um bundle inequivoco.

- [x] Incrementar metadados de 0.11.2 para 0.11.3.
- [x] Passar quality gate, matriz Linux e CI remoto.
- [x] Atualizar o runtime dedicado e verificar servicos/bandeja.
- [x] Gerar e verificar o bundle local ligado ao commit final.
- [x] Promover por fast-forward para `develop` e `main`.

**Plano**: `docs/planning/TASK-051-release-0113.md`.

### Task 050 - Corrida de identidade ao iniciar alarme Linux

**Prioridade**: Critica
**Status**: concluida e validada
**Objetivo**: impedir que o controlador grave o fingerprint pre-`exec` do
processo filho e classifique um alarme recem-iniciado como estado obsoleto.

- [x] Reproduzir a falha no release gate e no teste isolado.
- [x] Confirmar a transicao de `/proc/<pid>/cmdline` entre `fork` e `exec`.
- [x] Aguardar de forma limitada o fingerprint esperado do GNU `timeout`.
- [x] Adicionar regressao deterministica para o fingerprint transitorio.
- [x] Passar suite repetida, release gate, CI remoto e verificacao do bundle.

**Plano**: `docs/planning/TASK-050-alarm-spawn-race.md`.

### Task 049 - Fechamento do candidato 0.11.2

**Prioridade**: Alta
**Status**: concluida pela Task 050; publicacao externa nao executada
**Objetivo**: alinhar o commit promovido, a evidencia hospedada e o bundle
local verificavel sem confundir promocao de branches com publicacao.

- [x] Confirmar `develop` e `main` no mesmo commit por fast-forward.
- [x] Passar o workflow remoto na branch de tarefa, em `develop` e em `main`.
- [x] Regenerar e verificar o bundle local 0.11.2 a partir do commit final.
- [x] Manter tag e prerelease fora do escopo sem autorizacao especifica.

**Plano**: `docs/planning/TASK-049-release-closeout.md`.

### Task 048 - Gate CI com bandeja opcional

**Prioridade**: Alta
**Status**: concluida; matriz Linux remota aprovada
**Objetivo**: manter o CI Linux reproduzivel sem instalar a dependencia grafica
opcional, preservando tipagem estrita para o restante do produto.

- [x] Reproduzir a falha nos tres jobs Linux do GitHub Actions.
- [x] Confirmar que testes, cobertura e Ruff passam antes da falha de tipagem.
- [x] Limitar a excecao do mypy exclusivamente aos modulos `PySide6.*`.
- [x] Passar o quality gate local e o CI remoto em Python 3.10, 3.11 e 3.12.
- [x] Promover o `develop` validado para `main`.

**Plano**: `docs/planning/TASK-048-optional-tray-ci-gate.md`.

### Task 047 - Prompt rule nao despachou apos 52 minutos

**Prioridade**: Critica
**Status**: concluida no runtime Linux 0.11.2; regras falhadas exigem decisao humana
**Objetivo**: reproduzir e corrigir a regra configurada perto de 10:00 com
atraso de 52 minutos que nao forneceu prompt ate 13:03, sem confundir regra
vencida, tentativa de transporte e confirmacao do Codex.

- [x] Inspecionar metadados sanitizados da regra, runtime, servico e logs.
- [x] Reproduzir o estado em HOME, banco e controles isolados.
- [x] Identificar a causa na configuracao, ownership, scheduler ou transporte.
- [x] Implementar a menor correcao e teste de regressao correspondente.
- [x] Corrigir o preflight transacional para aceitar schema 1 integro e
      continuar rejeitando schema 1 corrompido.
- [x] Corrigir a unidade systemd para usar o caminho absoluto do Codex e
      limitar loops de reinicio quando a dependencia falha.
- [x] Reutilizar o mesmo executavel absoluto no App Server e no transporte
      `codex queue`, sem fallback ao PATH do systemd.
- [x] Validar quality gate, matriz Python e pacote instalado.
- [x] Executar E2E exato autorizado e registrar a evidencia.

**Plano**: `docs/planning/TASK-047-prompt-rule-missed-dispatch.md`.

**Diagnostico**: `docs/PROMPT-RULE-INCIDENT-2026-11-02.md`.

### Task 046 - Integracao e release do chat e da retomada automatica

**Prioridade**: Critica
**Status**: concluida e promovida para `develop` e `main`
**Objetivo**: validar o produto integrado, atualizar o runtime Linux e provar
os fluxos reais sem confundir emissao de input com processamento pelo Codex.

- [x] Passar quality gate, matriz Python e build local.
- [x] Testar migracao de banco e rollback com copia privada verificavel.
- [x] Instalar o candidato no runtime dedicado de forma transacional.
- [x] Instalar e ativar `prompt-rule-observer` sem duplicar processos.
- [x] Executar E2E de chat por sessao exata e E2E de retomada com marcador.
- [x] Verificar `doctor --strict`, bandeja, monitor e observers apos upgrade.
- [x] Promover para `develop`; promover para `main` somente com gates reais.

**Plano**: `docs/planning/TASK-046-integrated-chat-release.md`.

**Evidencia local (2026-11-02)**: 357 testes passaram em Python 3.10, 3.11 e
3.12; cobertura global de 87%; Ruff, mypy, compilacao, sintaxe shell, build e
`git diff --check` passaram. O release gate verificou o bundle 0.11.2 do commit
`83a5c66`. A migracao 1->2 e restauracao 2->1 passaram em copia isolada. O
runtime 0.11.2, schema 2, tres servicos, bandeja e hooks passaram em
`doctor --strict`; o observer permaneceu ativo com `NRestarts=0`.

O chat E2E persistiu e enviou um marcador exclusivo para a sessao exata e um
hook posterior confirmou `delivery_confirmed`. O observer E2E isolado obteve
`usage_available`, despachou um marcador exclusivo uma vez e persistiu
`dispatch_started`, desabilitado, com uma ocorrencia.

O GitHub Actions posteriormente passou em Python 3.10, 3.11 e 3.12 na branch
de tarefa, em `develop` e em `main`. O bundle final foi regenerado somente
depois do commit documental de fechamento, mantendo o manifesto ligado ao SHA
promovido final.

### Task 045 - Experiencia de chat na bandeja e projecao Discord

**Prioridade**: Alta
**Status**: concluida; E2E confirmado na Task 046
**Objetivo**: substituir o formulario isolado por uma conversa persistente,
legivel e vinculada ao projeto/agente/sessao exatos.

- [x] Exibir seletores de projeto/sessao e transcript paginado.
- [x] Persistir mensagem humana antes do transporte e atualizar seu estado.
- [x] Projetar perguntas/respostas Discord no mesmo historico sem duplicacao.
- [x] Atualizar incrementalmente sem roubar foco ou deslocar a leitura.
- [x] Exibir estados preliminares e confirmados com semantica correta.
- [x] Cobrir dominio, vazio, erro, troca de perfil, reinicio e isolamento.

**Plano**: `docs/planning/TASK-045-tray-agent-chat.md`.

### Task 044 - Dominio persistente e CLI do chat de agentes

**Prioridade**: Critica
**Status**: concluida; validacao integrada confirmada na Task 046
**Objetivo**: criar o contrato local de conversas e mensagens e permitir que o
humano e o AI-worker publiquem no proprio escopo de forma auditavel.

- [x] Migrar o SQLite de schema 1 para 2 sem perder tabelas existentes.
- [x] Criar conversas unicas por worker, agente e sessao Codex exata.
- [x] Criar mensagens append-only com papel, direcao, transporte, correlacao e
      estado de entrega.
- [x] Implementar listagem paginada e atualizacao de estado idempotente.
- [x] Adicionar CLI para listar conversas/mensagens e publicar resposta do
      agente somente no worker derivado do projeto corrente.
- [x] Adicionar servico de envio humano que persiste antes de usar a fila.
- [x] Adicionar exportacao com redacao opcional e arquivamento sem exclusao.
- [x] Cobrir validacao, isolamento entre projetos, paginacao e migracao.

**Plano**: `docs/planning/TASK-044-agent-chat-domain.md`.

### Task 043 - Chat persistente e retomada por recuperacao de uso

**Prioridade**: Critica
**Status**: concluida e integrada
**Objetivo**: substituir o compositor isolado da bandeja por conversas
persistentes por projeto/agente/sessao e permitir que uma prompt rule autorizada
retome a sessao exata quando o Codex voltar a informar uso disponivel, inclusive
depois de uma janela de cinco horas ou semanal.

**Retomada automatica**:

- [x] Identificar a limitacao: `observe-codex-limits --watch` encerrava quando o
      worker ficava inativo e a bandeja era o unico scheduler das regras.
- [x] Criar observer dedicado que continua avaliando regras vencidas mesmo com
      worker `idle`.
- [x] Consultar o App Server apenas quando houver regra habilitada, vencida,
      vinculada a sessao exata e com **Require available Codex usage**.
- [x] Preservar a regra em `waiting_for_usage` enquanto o estado for bloqueado,
      ausente ou desconhecido.
- [x] Enviar `continue` uma unica vez quando surgir evidencia fresca
      `usage_available`; desarmar antes do transporte e exigir hook posterior
      para confirmar atividade.
- [x] Separar a execucao: bandeja trata regras comuns e o observer trata regras
      condicionadas a uso, evitando disputa entre processos.
- [x] Disponibilizar `observe-prompt-rules` e o componente de servico
      `prompt-rule-observer`.
- [x] Instalar o novo servico no runtime dedicado e executar E2E real com
      marcador exclusivo sem esgotar tokens deliberadamente.

**Investigacao das prompt rules**:

- [x] Confirmar por leitura que alteracao de campo ou reabilitacao rearma a
      regra, enquanto salvar sem mudanca preserva o vencimento.
- [x] Confirmar por testes que regra one-shot envia uma vez, espera evidencia
      de uso exata/fresca e rejeita evidencia vencida ou de outro escopo.
- [x] Reproduzir a lacuna operacional de longa duracao: o produtor antigo
      dependia de worker ativo e a bandeja precisava permanecer aberta.
- [x] Cobrir a correcao com worker encerrado, limite atingido, recuperacao de
      uso e exatamente um despacho.
- [x] Passar 344 testes, 86% de cobertura, Ruff, mypy, shell e build no
      quality gate completo.
- [x] Passar os mesmos 344 testes em Python 3.10, 3.11 e 3.12.
- [x] Instalar o wheel 0.10.8 isoladamente e validar comando, ciclo ocioso e
      definicao systemd do novo componente.
- [x] Registrar E2E instalado do servico e atualizar a conclusao desta
      investigacao com evidencias reais.

**Chat completo**:

- [x] Criar modelo SQLite de conversa e mensagem por projeto, agente e sessao
      Codex exata, com direcao, transporte, correlacao e estado de entrega.
- [x] Migrar perguntas/respostas Discord existentes para a mesma leitura de
      historico sem perder os estados auditaveis de `remote_questions`.
- [x] Substituir **Respond to message** por uma janela de chat com lista de
      conversas, transcript paginado, compositor, estados vazio/erro/pendente e
      atualizacao incremental.
- [x] Permitir envio local pela fila Codex e projecao de pergunta/resposta
      correlacionada do Discord sem
      confundir `dispatch_started`, `input_emitted` e `delivery_confirmed`.
- [x] Adicionar comando para o AI-worker publicar respostas explicitas no
      transcript; capturar respostas arbitrarias somente quando existir uma API
      confiavel do Codex, sem inferi-las por hooks.
- [x] Implementar retencao, redacao/exportacao e limites de notificacao sem
      expor conteudo sensivel no desktop.
- [x] Validar isolamento entre dois projetos/agentes, reinicio da bandeja,
      ordenacao, concorrencia, Discord e sessao Codex exata.

**Plano**: `docs/planning/TASK-043-agent-chat-and-usage-recovery.md`.

### Task 040 - Condicao de disponibilidade de uso nas prompt rules

**Prioridade**: Alta
**Status**: candidato 0.10.6 aprovado e promovido para `origin/develop`;
runtime instalado permanece em 0.10.5 e `main` em 0.10.4 aguardando decisoes
separadas
**Objetivo**: permitir que cada regra exija disponibilidade agregada de uso do
Codex, alem do gatilho temporal ou vermelho, sem presumir saldo nem misturar
evidencia entre workers ou sessoes.

- [x] Adicionar checkbox opt-in persistente por regra e perfil.
- [x] Manter compatibilidade com controles antigos usando default `false`.
- [x] Exigir `usage_available` valido, exato e posterior ao vencimento.
- [x] Falhar fechado em estado ausente, expirado, desconhecido ou bloqueado.
- [x] Preservar regra, vencimento e ocorrencias enquanto aguarda uso.
- [x] Expor `waiting_for_usage` no estado e na bandeja.
- [x] Documentar o observer necessario e os limites de seguranca.
- [x] Passar 335 testes, 86% de cobertura e quality gate completo.
- [x] Passar 335 testes em Python 3.10, 3.11 e 3.12.
- [x] Confirmar leitura live `usage_available` em dry-run sem persistencia.
- [x] Construir e verificar o candidato 0.10.6 no commit `2651bdd`.
- [x] Passar E2E isolado instalado diretamente do wheel 0.10.6.
- [x] Registrar evidencia, publicar branch e promover para `develop`.
- [ ] Obter autorizacao separada para upgrade 0.10.6 e promocao para `main`.

**Plano**: `docs/planning/TASK-040-prompt-rule-usage-gate.md`.

### Task 038 - Desativacao de prompt rules pelo AI-worker

**Prioridade**: Alta
**Status**: candidato 0.10.5 aprovado e promovido para `develop`; runtime
instalado esta em 0.10.5; `main` permanece em 0.10.4 aguardando
decisao separada de promocao
**Objetivo**: permitir que uma IA desabilite todas as regras de prompt somente
do proprio worker derivado, sem desligar a automacao geral nem afetar perfis de
outros projetos.

- [x] Adicionar comando sem argumentos de identidade.
- [x] Derivar o mesmo worker corrente usado pelo limite de automacao.
- [x] Desabilitar regras e limpar estado pendente preservando configuracao.
- [x] Manter `task-automation` e outros perfis inalterados.
- [x] Implementar dry-run sem persistencia.
- [x] Cobrir isolamento, preservacao, parser e runtime desabilitado.
- [x] Passar quality gate com 333 testes e 86% de cobertura.
- [x] Passar 333 testes em Python 3.10, 3.11 e 3.12 e release gate 0.10.5.
- [x] Executar E2E instalado e isolado sem alterar controles reais.
- [x] Promover a implementacao validada para `origin/develop`.
- [x] Registrar a CI hospedada zero-step por billing como nao aprovada.
- [x] Obter autorizacao e aplicar upgrade transacional do runtime para 0.10.5.
- [ ] Obter decisao separada para promocao de `develop` para `main`.

**Plano**: `docs/planning/TASK-038-disable-current-prompt-rules.md`.

### Task 031 - Recuperacao do observer Discord e CI hospedada

**Prioridade**: Critica
**Status**: observer recuperado desde 0.10.2 e runtime atual 0.10.5; CI
hospedada pendente por bloqueio externo da conta GitHub
**Objetivo**: impedir que bloqueios SQLite e falhas transitórias de rede
derrubem o observer, validar sua recuperacao real sem duplicar input e restaurar
evidencia hospedada da matriz Linux.

- [x] Confirmar banco integro, Discord acessivel e ausencia de perguntas
      pendentes antes de qualquer reinicio.
- [x] Confirmar causas historicas: lock SQLite, timeout/DNS e StartLimitBurst.
- [x] Confirmar que a CI atual cria jobs sem steps e informa billing lock.
- [x] Adicionar espera SQLite explicita e backoff somente para polling seguro.
- [x] Cobrir lock, rede transitoria, erro permanente e reset do backoff.
- [x] Passar quality gate e matriz Python suportada.
- [x] Gerar e validar wheel de correcao.
- [x] Autorizar e aplicar upgrade local antes do reinicio do observer.
- [x] Confirmar observer ativo, polling estavel e doctor sem erro.
- [x] Classificar desconexao remota/reset de conexao como falha transitoria.
- [x] Instalar 0.10.2 e repetir recuperacao sustentada do observer.
- [ ] Desbloquear a conta GitHub quando o proprietario puder e obter um run
      hospedado Linux aprovado.

**Plano**: `docs/planning/TASK-031-observer-ci-recovery.md`.

## Concluidas em 2026-10-15

### Task 042 - Upgrade 0.10.7 e promocao privada para main

**Prioridade**: Critica
**Status**: concluida; runtime 0.10.7 operacional e candidato promovido por
fast-forward para `origin/develop` e `origin/main`
**Objetivo**: provar upgrade e rollback transacionais, estabilidade da bandeja
e dos servicos, e promover o candidato Linux privado por fast-forward.

- [x] Validar os wheels autenticos 0.10.5 e 0.10.7 por SHA-256.
- [x] Executar dry-run e upgrade real de 0.10.5 para 0.10.7.
- [x] Validar schema, doctor, servicos, controles e hooks apos o upgrade.
- [x] Executar rollback manual com restauracao do banco e validar 0.10.5.
- [x] Executar novo dry-run e upgrade final para 0.10.7.
- [x] Confirmar uma bandeja ativa, tres componentes com `NRestarts=0` e
      disponibilidade grafica no Linux Mint.
- [x] Passar E2E isolado do observer de notificacoes no runtime instalado.
- [x] Passar 342 testes, 86% de cobertura e quality gate completo.
- [x] Passar 342 testes em Python 3.10, 3.11 e 3.12.
- [x] Construir e verificar bundle limpo 0.10.7.
- [x] Confirmar CI hospedada zero-step por billing e registrar excecao 0.10.7.
- [x] Repetir o release gate no commit documental exato `950e50f`.
- [x] Publicar o task branch e promover por fast-forward para `develop` e
      `main`.

**Plano**: `docs/planning/TASK-042-runtime-upgrade-main.md`.

### Task 041 - Notificacoes de desktop orientadas a eventos

**Prioridade**: Alta
**Status**: concluida; notificacoes instaladas no runtime 0.10.7 e promovidas
para `origin/main` pela Task 042
**Objetivo**: oferecer notificacoes locais opt-in e deduplicadas para eventos
confiaveis do monitor, sem confundir inicio de transporte com processamento da
mensagem pela IA.

- [x] Adicionar checkbox persistente no menu acima de **Respond to message...**.
- [x] Manter o controle global e desabilitado por padrao em arquivos antigos.
- [x] Notificar inicio/fim de tarefa e `Stop` observado do Codex.
- [x] Notificar alertas de inatividade e transicoes de perguntas Discord.
- [x] Colocar resultados das prompt rules sob o mesmo interruptor mestre.
- [x] Persistir cursores para nao repetir eventos depois de reiniciar a bandeja.
- [x] Suprimir backlog criado enquanto o recurso estiver desabilitado.
- [x] Limitar rajadas visuais e omitir prompt, pergunta e resposta do texto.
- [x] Passar quality gate com 342 testes e 86% de cobertura.
- [x] Passar 342 testes em Python 3.10, 3.11 e 3.12.
- [x] Confirmar disponibilidade da bandeja no Linux Mint com `tray --check`.
- [x] Passar release gate 0.10.7 sobre o commit candidato `84f6d34` limpo.
- [x] Verificar bundle e instalacao isolada do wheel 0.10.7.
- [x] Publicar a branch validada e promover para `develop`.
- [x] Obter autorizacao separada para upgrade 0.10.7 e promocao para `main`.

**Plano**: `docs/planning/TASK-041-desktop-notifications.md`.

### Task 039 - Upgrade transacional do runtime para 0.10.5

**Prioridade**: Alta
**Status**: concluida; runtime 0.10.5 instalado e componentes operacionais
revalidados
**Objetivo**: atualizar a instalacao Linux dedicada de 0.10.4 para 0.10.5 com
rollback verificavel, preservando banco, configuracao, servicos e bandeja.

- [x] Confirmar runtime 0.10.4, schema integro e tres componentes ativos.
- [x] Validar os wheels 0.10.5 e 0.10.4 e o manifesto do release gate.
- [x] Obter `would_upgrade` no dry-run antes da transacao.
- [x] Parar a bandeja antiga e executar uma unica transacao autorizada.
- [x] Confirmar manifesto `completed` e runtime instalado 0.10.5.
- [x] Confirmar schema atual, doctor estrito `ok` e servicos restaurados.
- [x] Iniciar uma unica bandeja nova com a versao atualizada.
- [x] Obter `would_rollback` para 0.10.4 sem executar a reversao.
- [x] Confirmar o novo comando no runtime instalado.

**Plano**: `docs/planning/TASK-039-runtime-upgrade-0105.md`.

## Concluidas em 2026-10-14

### Task 037 - Upgrade transacional do runtime para 0.10.4

**Prioridade**: Alta
**Status**: concluida; runtime 0.10.4 instalado e componentes operacionais
revalidados
**Objetivo**: atualizar a instalacao Linux dedicada de 0.10.3 para 0.10.4 com
rollback verificavel, preservando banco, configuracao, servicos e bandeja.

- [x] Confirmar runtime 0.10.3, schema integro e tres componentes ativos.
- [x] Validar o wheel 0.10.4 contra o manifesto limpo do release gate.
- [x] Validar o wheel 0.10.3 preservado contra o manifesto anterior concluido.
- [x] Obter `would_upgrade` no dry-run antes de autorizar a transacao.
- [x] Parar a bandeja antiga e executar uma unica transacao autorizada.
- [x] Confirmar manifesto `completed` e runtime instalado 0.10.4.
- [x] Confirmar schema atual, doctor estrito `ok` e servicos restaurados.
- [x] Iniciar uma unica bandeja nova com a versao atualizada.
- [x] Obter `would_rollback` sem restaurar pacote ou banco.

**Plano**: `docs/planning/TASK-037-runtime-upgrade-0104.md`.

### Task 036 - Release 0.10.4 e promocao do launcher para main

**Prioridade**: Alta
**Status**: concluida; candidato 0.10.4 aprovado e promovido por fast-forward
para `origin/develop` e `origin/main` com excecao local versionada
**Objetivo**: transformar o launcher da bandeja em ativo verificado do bundle
Linux 0.10.4 e promover o mesmo candidato validado de `develop` para `main`.

- [x] Criar branch dedicada a partir do `develop` validado da Task 035.
- [x] Incluir `start-tray.sh` nos ativos do bundle Linux.
- [x] Exigir permissao executavel do proprietario e sintaxe Bash valida.
- [x] Cobrir o verificador com casos positivo, sem permissao e sintaxe invalida.
- [x] Sincronizar versao 0.10.4 e documentacao operacional.
- [x] Passar quality gate completo com 331 testes e 86% de cobertura.
- [x] Passar 331 testes em Python 3.10, 3.11 e 3.12 no release gate.
- [x] Gerar e verificar bundle limpo vinculado ao commit `1ff2c21`.
- [x] Registrar runs hospedados zero-step por billing como nao aprovados.
- [x] Documentar excecao privada e versionada para esta promocao 0.10.4.
- [x] Promover o candidato por fast-forward para `develop` e `main`.

**Plano**: `docs/planning/TASK-036-tray-launcher-main-promotion.md`.

### Task 035 - Launcher executavel da bandeja

**Prioridade**: Media
**Status**: concluida; testes e inicializacao real aprovados, branch publicada
e implementacao promovida para `develop`
**Objetivo**: permitir que o usuario inicie o icone da bandeja do Linux Mint
por um arquivo executavel na raiz do projeto, sem manter terminal aberto.

- [x] Localizar o runtime instalado e um `.env` legivel sem expor valores.
- [x] Exigir sessao grafica e validar dependencias antes da inicializacao.
- [x] Iniciar uma unidade transitoria do usuario com reinicio apenas em falha.
- [x] Evitar duplicata gerenciada pelo launcher ou iniciada diretamente.
- [x] Mostrar notificacao de desktop quando disponivel.
- [x] Passar 328 testes, quality gate e smoke real da unidade transitoria.
- [x] Registrar commit, publicar o branch e promover para `develop`.

## Concluidas em 2026-10-13

### Task 034 - Rearmamento de regras de prompt

**Prioridade**: Alta
**Status**: concluida; runtime 0.10.3 instalado, E2E isolado aprovado e codigo
promovido por fast-forward para `origin/develop` e `origin/main`
**Objetivo**: garantir que reabilitar ou editar uma regra inicie nova contagem,
sem reutilizar estado de falha ou um episodio vermelho anterior, e consolidar
270 minutos como atraso padrao.

- [x] Preservar alteracoes locais do novo default de 270 minutos.
- [x] Investigar o estado persistido da regra que gerou a notificacao.
- [x] Persistir o instante de armamento com compatibilidade aditiva.
- [x] Reiniciar contagem e estado ao reabilitar ou alterar qualquer campo.
- [x] Preservar o vencimento quando nenhuma configuracao mudou.
- [x] Nao reaproveitar vermelho anterior ao novo armamento.
- [x] Cancelar vencimento inicial se atividade valida retornar antes do envio.
- [x] Passar quality gate completo e matriz Python suportada.
- [x] Registrar commit da implementacao depois dos gates locais.
- [x] Gerar e verificar bundle 0.10.3 a partir de uma arvore limpa.
- [x] Enviar o branch e promover o codigo validado para `develop`.
- [x] Instalar a 0.10.3 e executar E2E operacional isolado antes de `main`.

**Plano**: `docs/planning/TASK-034-prompt-rule-rearm.md`.

## Concluidas em 2026-10-11

### Task 032 - Promocao de main com excecao local de CI

**Prioridade**: Critica
**Status**: concluida; versao 0.10.2 promovida por fast-forward para
`origin/develop` e `origin/main` pela excecao local documentada
**Objetivo**: promover a correcao 0.10.2 de `develop` para `main` sem tratar a
CI hospedada bloqueada por cobranca como aprovada, usando evidencia local e
operacional reproduzivel para esta promocao somente.

- [x] Registrar escopo, risco e obrigacao de revalidacao da excecao.
- [x] Passar quality gate completo no candidato exato.
- [x] Passar release gate, matriz Python e verificacao offline no candidato.
- [x] Confirmar runtime 0.10.2, banco, monitor, observer e bandeja saudaveis.
- [x] Confirmar novamente que a falha hospedada executa zero etapas por billing.
- [x] Promover por fast-forward para `develop` e `main` sem tag ou release.
- [x] Enviar as duas branches e verificar os commits remotos.

**Plano**: `docs/planning/TASK-032-main-ci-exception.md`.

## Concluidas em 2026-10-09

### Task 030 - Prerelease publica Linux 0.10.0

**Prioridade**: Critica
**Status**: concluida; wheel final instalado, tagueado, publicado e verificado
novamente a partir da prerelease publica
**Objetivo**: produzir, validar, instalar e publicar a prerelease Linux 0.10.0
com rollback verificavel a partir da versao instalada 0.9.0.

- [x] Confirmar `main`/`develop` sincronizados e runtime instalado 0.9.0.
- [x] Confirmar monitor, hooks, fila nativa e banco operacional saudaveis.
- [x] Manter o reply observer falho fora do escopo, sem reinicio automatico.
- [x] Confirmar que o CI Quality falhou com zero steps executados.
- [x] Autorizar excecao especifica e divulgada para a prerelease publica apesar
      da CI hospedada ter executado zero etapas.
- [x] Gerar bundle limpo, checksums e manifesto vinculados ao commit exato.
- [x] Verificar wheel, sdist, instalacao isolada e isolamento entre projetos.
- [x] Preservar e verificar o wheel autentico 0.9.0 para rollback.
- [x] Executar dry-run do upgrade transacional.
- [x] Autorizar e validar upgrade real, rollback com banco e upgrade final.
- [x] Reconstruir e validar artefatos apos sincronizar documentacao 0.10.0.
- [x] Revalidar o wheel final exato no runtime instalado.
- [x] Criar e enviar a tag anotada `v0.10.0` no commit `447f309`.
- [x] Publicar prerelease publica com arquivo canonico e sidecar SHA-256.
- [x] Corrigir o sidecar para usar somente o basename do arquivo.
- [x] Baixar e verificar novamente as duas camadas de checksum.

**Release**: `https://github.com/JosueAmaral15/ai-presence-monitor/releases/tag/v0.10.0`.
Arquivo canonico: 345657 bytes, SHA-256
`106d0aaf853381826d63416b61712cdd406c4602eb9088d79da3eb23fc4a3144`.
Sidecar portavel: 106 bytes, SHA-256
`5feefeb6720c8dc5694477617956e20d50af2043e4c2dd57e87cee5ab9a9cbf6`.

**Plano**: `docs/planning/TASK-030-linux-release-0100.md`.

## Concluidas em 2026-10-08

### Task 028 - E2E do scheduler 0.10.0 e promocao para main

**Prioridade**: Critica
**Status**: E2E real aprovado e candidato promovido por fast-forward para
`origin/develop` e `origin/main` no commit `e55658f`
**Objetivo**: validar o scheduler e o gate vermelho com estado isolado, registrar
a evidencia e promover o mesmo candidato de `develop` para `main`.

- [x] Confirmar sessao atual, hooks e disponibilidade de `codex queue`.
- [x] Confirmar que o observer Discord falho e independente deste fluxo.
- [x] Definir banco e `control.json` temporarios, sem alterar estado operacional.
- [x] Emitir um unico marcador exclusivo por uma regra com gatilho vermelho e
      atraso adicional.
- [x] Confirmar que o usuario nao digitou o marcador e observar hook posterior.
- [x] Registrar resultado; nenhum codigo mudou depois dos gates completos.
- [x] Promover por fast-forward e enviar `main`.

**Plano**: `docs/planning/TASK-028-scheduled-prompt-e2e-main.md`.

### Task 029 - Regras multiplas de prompt por projeto/agente

**Prioridade**: Critica
**Status**: implementacao, gates locais, E2E real e promocao para `main`
concluidos
**Objetivo**: permitir varias regras persistentes de prompt por worker e uma
desativacao de automacao limitada ao projeto corrente do AI-worker.

- [x] Persistir todos os campos e estados de varias regras em `control.json`.
- [x] Adicionar/remover regras pela bandeja sem perder outros perfis.
- [x] Oferecer gatilho por atraso ou pelo vermelho canonico do protocolo.
- [x] Configurar regra one-shot ou repetitiva, com intervalo e limite.
- [x] Exigir hook posterior da mesma sessao antes de cada repeticao.
- [x] Parar a regra em falha ou incerteza, sem retry automatico.
- [x] Permitir que um AI-worker desabilite somente a automacao do worker
      derivado do projeto corrente.
- [x] Impedir mutacao CLI arbitraria de outro perfil; manter consulta
      sanitizada e edicao humana pela bandeja.
- [x] Migrar uma configuracao legada visivel quando o usuario salvar o perfil.
- [x] Atualizar documentacao humana, protocolo de agentes, seguranca e rollback.
- [x] Aprovar 312 testes, cobertura de 86%, matriz Python 3.10/3.11/3.12,
      Ruff, mypy, compileall, shell syntax, build e smoke da bandeja.

**Plano**: `docs/planning/TASK-029-profile-prompt-rules.md`.

### Task 028 - Perfis de automacao e gate de inatividade vermelha

**Prioridade**: Alta
**Status**: implementacao, gates e E2E integrados ao candidato 0.10.0 promovido
para `main`
**Objetivo**: isolar todos os controles da bandeja por worker/projeto e permitir
que o prompt temporizado aguarde tambem a inatividade vermelha do protocolo.

- [x] Persistir perfis completos por `worker_id` sem invalidar controles globais.
- [x] Selecionar perfil e sessoes correspondentes na bandeja.
- [x] Adicionar checkbox opcional para exigir inatividade vermelha.
- [x] Usar 30 minutos no Protocolo 1 e 15 minutos no Protocolo 2.
- [x] Manter o atraso configurado como prazo minimo e o envio como one-shot.
- [x] Fazer CLI e automacao ordinaria resolverem o perfil do worker quando aplicavel.
- [x] Cobrir isolamento, compatibilidade, gate e ausencia de retry com testes.
- [x] Atualizar guias humanos, protocolo de AI-workers, arquitetura e seguranca.

**Plano**: `docs/planning/TASK-028-profiled-red-gated-prompts.md`.

### Task 027 - Prompt temporizado one-shot por sessao

**Prioridade**: Alta
**Status**: concluida na branch `codex/task-027-scheduled-prompt`; versao
0.10.0 preparada, ainda nao publicada nem implantada
**Objetivo**: permitir que o usuario programe pela bandeja um unico prompt
nativo para uma sessao Codex exata, com atraso e texto configuraveis.

- [x] Expor checkbox, atraso em minutos e texto na janela de preferencias.
- [x] Usar `210` minutos e `continue` como defaults.
- [x] Congelar a sessao selecionada e o vencimento ao habilitar.
- [x] Desarmar antes do transporte para impedir repeticao automatica.
- [x] Preservar compatibilidade com `control.json` existente.
- [x] Nao atualizar presenca antes de um hook posterior da sessao.
- [x] Documentar seguranca, operacao, limites e rollback.
- [x] Aprovar testes focados, suite, cobertura, Ruff e mypy.

**Plano**: `docs/planning/TASK-027-scheduled-session-prompt.md`.

## Concluidas em 2026-09-24

### Task 026 - Release profissional Linux 0.9.0

**Prioridade**: Critica
**Status**: concluida; release privada Linux 0.9.0 validada, implantada,
tagueada e publicada como prerelease privada
**Objetivo**: concluir um produto Linux privado, instalavel em outro computador
e reutilizavel por projetos independentes sem depender do checkout.

- [x] Contrato de suporte, instalacao, compatibilidade e upgrade publicado.
- [x] Instalador Linux de wheel local e verificador offline implementados.
- [x] Conjunto deterministico de artefatos 0.9.0 com checksums verificaveis.
- [x] Gate local, matriz Python, instalacao limpa e isolamento por projeto.
- [x] Upgrade e rollback reais autorizados no runtime dedicado.
- [x] Candidato exato promovido para `develop`, depois `main`, e tagueado.

**Plano**: `docs/planning/TASK-026-linux-product-release.md`.

## Planejadas

### Task 025 - Superficie de produto e atualizacao transacional

**Prioridade**: Alta
**Status**: diagnostico, implementacao transacional, E2E operacional e release
privada concluidos; CI hospedada permanece externa e necessaria somente antes
de futura distribuicao publica
**Objetivo**: transformar a instalacao tecnica em um produto atualizavel,
diagnosticavel e distribuivel com rollback deterministico.

- [x] Publicar o registro do upgrade operacional em `develop` e `main`.
- [x] Reconciliar autorizacao persistente de `continue` para AI-workers.
- [x] Habilitar `task-automation` sem habilitar fallback GUI ou remoto.
- [x] Configurar autostart XDG da bandeja no Linux Mint atual.
- [x] Validar um unico `continue` nativo pos-upgrade na sessao exata.
- [x] Adicionar `ai-presence --version` deterministico.
- [x] Implementar upgrade e rollback transacionais com manifesto de backup.
- [x] Expor versao e estado de migracao do schema SQLite.
- [x] Criar comando sanitizado `doctor` para saude operacional.
- [x] Publicar artefatos tagueados e checksums SHA-256.
- [ ] Restaurar CI Linux hospedada antes de distribuicao publica.
- [x] Definir politicas de instalacao, upgrade, suporte e compatibilidade.

**Fase imediata**:
`docs/planning/TASK-025-immediate-product-activation.md`.

**Fase de diagnostico**:
`docs/planning/TASK-025-product-diagnostics.md`.

**Fase transacional**:
`docs/planning/TASK-025-transactional-upgrade.md`.

## Concluidas em 2026-09-20

### Task 024 - Upgrade operacional Linux para 0.8.0

**Prioridade**: Alta
**Status**: concluida; runtime dedicado atualizado de 0.7.0 para 0.8.0 com
backup, migracao aditiva e servicos validados
**Objetivo**: implantar a release privada validada sem perder dados, expor
segredos ou ampliar permissoes de automacao silenciosamente.

- [x] Versao operacional anterior confirmada fora do checkout como 0.7.0.
- [x] Wheel anterior, checksums, unidades, dependencias e banco SQLite salvos.
- [x] Wheel 0.8.0 instalado no ambiente virtual dedicado.
- [x] Integridade SQLite, hooks, bandeja e instaladores validados.
- [x] Monitor e observer de respostas ativos, habilitados e sem reinicios.
- [x] Controles preservados; `task-automation` continua desabilitado.

**Plano e evidencias**:
`docs/planning/TASK-024-operational-upgrade-productization.md`.

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
