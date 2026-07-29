# Tasks - AI Presence Monitor

## Concluidas

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
- [x] Abstract Factory foi adiada ate existir um adaptador Windows concreto.

### Task 007 - Unificacao com o comando de continuidade

**Prioridade**: Alta
**Status**: concluida
**Objetivo**: incorporar ao AI Presence Monitor o envio programado da mensagem
`continue` para o Codex GUI, eliminar a necessidade de executar o projeto
`mouse-control-clicker` separadamente e organizar o pacote no layout `src/`.

**Criterios de aceite**:

- [x] Existe um unico pacote e uma unica CLI para monitoramento e continuidade.
- [x] A mensagem padrao e `continue` e o atraso padrao e 60 segundos.
- [x] O alvo X11 e validado sem selecionar silenciosamente uma janela ambigua.
- [x] O envio oferece `--dry-run` e preserva o clipboard.
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
**Objetivo**: permitir que o monitor cobre presenca apenas durante um intervalo de expediente e repita alertas enquanto o worker continuar atrasado.

**Criterios de aceite**:

- [x] `.env` aceita janela de expediente com inicio, fim e timezone.
- [x] Monitor suprime alertas fora do expediente quando configurado.
- [x] Monitor pode repetir o mesmo nivel de alerta por intervalo configurado.
- [x] SQLite guarda `last_alert_at` para controlar repeticao.
- [x] Documentacao explica configuracao e comportamento.
- [x] Testes cobrem janela comum, janela noturna, supressao e repeticao.

## Backlog

- Criar observers adicionais para processo, workspace e logs.

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
