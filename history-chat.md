# History Chat - AI Presence Monitor

## 2026-07-16

O usuario pediu um sistema para monitorar presenca artificial de IAs trabalhadoras com alertas por Discord/Telegram. O projeto foi criado como `ai-presence-monitor` dentro de `ai-tools`, com CLI, menu interativo, SQLite, protocolos de alerta e notificadores.

Decisao atual: seguir a recomendacao de arquitetura Observer para Codex. Hooks do Codex devem registrar evidencias silenciosas de atividade local, e o monitor existente continua responsavel por aplicar protocolos e enviar alertas.

Restricao importante: nao gravar webhooks, tokens ou segredos neste arquivo.

Implementacao adicionada: `codex-hook` e `hooks/codex_presence_hook.py` registram eventos de lifecycle do Codex como observacoes passivas. Por padrao, `PRESENCE_CODEX_AUTO_START=false`, preservando `start`/`finish` como marcos publicos do Protocolo 2. O usuario deve revisar/confiar no hook pelo comando `/hooks` do Codex apos instalar a configuracao.

Continuidade: foi criado instalador seguro `install-codex-hook` / `uninstall-codex-hook`. Nesta sessao, como nao existiam `.env` nem `~/.codex/hooks.json`, foi criado `.env` minimo sem segredos com banco absoluto do projeto e instalado `/home/josue/.codex/hooks.json` com 5 hooks. A reinstalacao foi idempotente (`changed=false`). O proximo passo operacional e abrir `/hooks` no Codex e confiar nas entradas novas.

Documentacao: o usuario pediu registrar em markdown os dados necessarios para monitoramento. Foi criado `docs/ENVIRONMENT-GUIDE.md`, explicando como o sistema funciona na pratica, comandos, banco SQLite, monitor, protocolos, cada variavel do `.env`, dados minimos para Discord, opcionais de Telegram/alarme/telefonia, configuracao do observer do Codex, fluxo recomendado e cuidados de seguranca.

Revisao de ambiente: o `.env` atual carrega corretamente para Discord/Codex, com banco absoluto e `protocol2`. Telegram esta parcialmente preenchido (`TELEGRAM_CHAT_ID` sem `TELEGRAM_BOT_TOKEN`), o que deixa Telegram desativado pelo codigo. Foi atualizado `.env.example` e criado `docs/CONFIGURANDO-ENV.md` com checklist de preenchimento e validacao.

Implementacao: adicionada politica de expediente no monitor. Novas variaveis `PRESENCE_WORK_WINDOW_*` limitam a cobranca de alertas ao horario configurado, e `PRESENCE_ALERT_REPEAT_*` permite repetir alertas dentro do expediente enquanto o worker permanecer ativo e atrasado. O banco SQLite agora guarda `last_alert_at`.

## 2026-07-27

Intencao da Task 004: tornar o monitor portatil e reutilizavel. A implementacao
deve corrigir o empacotamento, remover dependencias de caminhos locais, resolver
o banco em relacao ao `.env`, permitir isolamento por projeto/sessao e gerar
hooks e servico systemd com backup e rollback. O banco existente e o modo de
worker global devem continuar compativeis.

Resultado da Task 004: versao 0.2.0 empacotada em wheel e instalada em ambiente
virtual dedicado. Foram adicionados escopos `global`, `project`, `session` e
`project-session`; o `.env` ativo usa `project` e nao fixa mais uma tarefa. O
hook global foi migrado para o modulo instalado com backup e reinstalacao
idempotente. O arquivo systemd de usuario foi gerado e validado, mas o servico
nao foi habilitado nem iniciado para evitar alertas automaticos sem confirmacao.
O smoke test isolado confirmou `start -> hook -> SQLite -> finish` no mesmo
worker de projeto. Foram executados 28 testes automatizados com sucesso.

Durante o smoke test, foi encontrado e corrigido que
`python -m ai_presence_monitor.codex_hook` nao chamava `main()`. Um teste de
subprocesso foi adicionado para impedir regressao. Tambem foi adotado
`.ai-presence-monitor.env` para configuracao local por projeto, evitando ler por
engano o `.env` de outra aplicacao.

A configuracao real foi movida para
`~/.config/ai-presence-monitor/.env`, com permissao `600`; o caminho antigo no
checkout virou link simbolico para preservar compatibilidade. Hooks e servico
systemd foram regenerados para apontar para essa configuracao central e ficaram
idempotentes. O servico continuou desabilitado e inativo.

Auditoria adicional solicitada pelo usuario: a primeira instalacao limpa do
wheel em Python 3.10 revelou que `datetime.UTC` nao existe nessa versao, apesar
de `pyproject.toml` declarar Python 3.10+. A implementacao foi corrigida para
`timezone.utc` e recebeu um teste de importacao com Python 3.10. O teste
concorrente isolado confirmou dois projetos ativos com IDs distintos, eventos
de hook separados e encerramento sem workers ativos.

Resultado final da auditoria: 33 testes passaram sequencialmente em Python
3.10, 3.11 e 3.12, totalizando 99 execucoes. `ruff check` e `mypy` passaram sem
erros. A cobertura foi 61% no pacote completo e 82% no nucleo, excluindo o
parser CLI, o menu interativo e os entrypoints, que tambem receberam smoke tests
de processo. O transporte HTTP foi testado com mock, incluindo payload,
cabecalhos, dry-run sem rede e conversao de erro de rede.

O wheel final foi testado sem arquivos de segredo/desenvolvimento, instalado em
ambiente limpo Python 3.10 e validado com todos os entrypoints. SHA-256:
`7c7024163875194c47badbe3aea9d932d033f30675704d4020c3be6fe898139f`.
O banco real retornou `PRAGMA integrity_check=ok`. Os cinco eventos reais do
hook passaram em dry-run. A unidade systemd foi iniciada por dois segundos,
registrou a supressao fora do expediente no journal e foi encerrada; permaneceu
desabilitada e inativa.

Inicio da Task 005: o usuario pediu elevar a cobertura e validar novamente. A
meta registrada e cobertura total >= 80%, sem excluir CLI ou menu interativo.
Os testes novos devem evitar rede, alarmes e alteracoes externas reais.

Resultado da Task 005: cobertura total elevada de 61% para 89%, sem omissoes.
CLI chegou a 96% e menu interativo a 89%. Foram adicionados testes para parser,
comandos, status, instaladores, roteamento de todas as opcoes do menu,
persistencia completa do `.env`, prompts e falhas de notificacao. O
`pyproject.toml` agora reprova cobertura abaixo de 80%.

A suite final tem 46 testes e passou em Python 3.10, 3.11 e 3.12, totalizando
138 execucoes na matriz. `ruff`, `mypy`, `bash -n`, `pip check` e integridade do
wheel passaram. Os cinco hooks passaram em dry-run, o SQLite real retornou
integridade `ok` e nao havia workers ativos. O wheel final tem SHA-256
`84a93629f741900d4d5051f4c91c1ccbe790850c26e148d2f588c77b93fc8e92`.

## 2026-07-29

O usuario pediu um canal de pergunta/resposta em que o Codex possa perguntar no
Discord e receber a resposta na GUI por controle local de mouse e teclado. A
decisao foi manter MCP/App Server como preferencia futura e implementar o fluxo
GUI como fallback opcional.

A Task 006 adiciona pergunta por webhook, polling REST por bot, allowlist de
usuarios, resposta direta obrigatoria, persistencia SQLite, alvo X11 exato,
clipboard com `xclip`, controle com `xdotool` e confirmacao pelo proximo hook do
mesmo worker. Nao ha retry automatico depois de falha GUI.

Os interruptores `PRESENCE_REMOTE_QUESTIONS_ENABLED` e
`PRESENCE_GUI_ANSWER_ENABLED` permanecem desligados por padrao. Foi criado um
servico systemd separado para o polling, mas ele nao deve ser habilitado nem
iniciado automaticamente. Segredos nao foram registrados neste historico.

Resultado da Task 006: 62 testes passaram nas tres versoes Python, com 86% de
cobertura. `ruff`, `mypy`, scripts, wheel e instalacao dedicada passaram. A
migracao foi exercitada em copia do banco real e preservou workers, eventos e
alertas. O wheel 0.3.0 tem SHA-256
`220f651cf3c6567f40378c02b6f935f6fdf028db2d36e934420786a387d6ac17`.

O `.env` real continua sem as credenciais novas, os dois recursos continuam
desativados e a unidade de respostas nao foi instalada. O teste externo real
depende de criar o bot/canal, preencher a allowlist e autorizar o movimento de
mouse e o Enter.
