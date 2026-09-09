# Changelog

## 2026-09-09 - v0.5.2

- Adicionada orientacao no Discord para mensagem invalida de usuario
  autorizado enquanto houver pergunta pendente.
- O aviso ensina a usar **Responder** e diagnostica texto vazio por ausencia de
  `Message Content Intent`.
- Mencoes ficam restritas ao autor validado pela allowlist.
- Bots, webhooks, usuarios nao autorizados e ausencia de pergunta pendente nao
  geram orientacao.
- Cada mensagem causa no maximo uma tentativa, inclusive depois de timeout
  incerto, sem entrada GUI ou retry automatico.
- Adicionados contadores operacionais e testes de regressao.

## 2026-09-08 - v0.5.1

- Limitado o reply observer Linux a tres falhas em cinco minutos.
- Aumentado para 30 segundos o intervalo de reinicio do observer e usado
  `Restart=on-failure`.
- Preservada a politica `Restart=always` do monitor principal.
- Corrigido o gate global de Ruff em `scripts/quality_check.py`.
- Adicionados plano operacional, testes, seguranca, rollback e troubleshooting
  para falhas persistentes e HTTP 403.

## 2026-08-12 - Protocolo normativo de continuidade

- Incorporadas ao guia integrado as condicoes de acionamento do antigo
  `prosseguir_tarefas.py`.
- Definidas pre-condicoes, situacoes proibidas, sequencia operacional e regras
  de encerramento para AI-workers em Linux e Windows.
- Preservada a falha fechada para janelas ambiguas; a janela ativa nao e usada
  como desempate.
- Explicitado que `continue` nao pode simular presenca, substituir sinais dos
  protocolos nem ser reenviado automaticamente depois de resultado incerto.

## 2026-08-11 - v0.5.0

- Adicionada Abstract Factory para familias operacionais Linux e Windows.
- Adicionado dispatcher Win32 com captura/revalidacao de `HWND`, clique,
  Unicode `SendInput` e falha fechada quando foreground e negado.
- Adicionado alarme Windows com runner limitado, identidade nativa e parada de
  arvore por `taskkill`.
- Adicionados Task Scheduler e comandos `install-background-service` e
  `uninstall-background-service` para monitor e observer de respostas.
- Configuracao Windows passa a usar `%APPDATA%`; estado usa `%LOCALAPPDATA%`.
- Windows instala `tzdata`, e sessoes SQLite passam a ser fechadas
  deterministicamente para permitir remocao segura dos arquivos.
- Adicionados instalador PowerShell, gate de qualidade Python portatil e CI em
  Ubuntu/Windows para Python 3.10, 3.11 e 3.12.
- Suite ampliada de 88 para 117 testes, mantendo 86% de cobertura local.

## 2026-08-02 - Documentacao internacional

- README raiz internacionalizado em ingles, com a versao portuguesa preservada
  em `README.pt-BR.md`.

## 2026-08-01 - v0.4.3

- Adicionada duracao maxima obrigatoria para o alarme local.
- Novo `RED_ALERT_MAX_DURATION_SECONDS`, com padrao de 15 segundos.
- Comandos em loop sao supervisionados por GNU `timeout` e terminam sozinhos.
- `stop-alarm`, deduplicacao, identidade do processo e reap permanecem ativos.
- Duracao invalida ou ausencia de `timeout` falha antes de iniciar o som.

## 2026-08-01 - v0.4.2

- Alerta vermelho passa a ser enviado uma unica vez por episodio continuo de
  inatividade.
- Discord, Telegram, alarme e telefonia deixam de repetir o vermelho.
- Nova atividade valida rearma um futuro alerta vermelho.
- Repeticao configuravel permanece disponivel para amarelo e laranja.
- Configuracoes antigas que listem `red` continuam aceitas, mas o nivel e
  ignorado para repeticao.

## 2026-07-30 - v0.4.1

- Adicionado controlador persistente do processo de alarme local.
- Adicionado comando `ai-presence stop-alarm` e opcao 19 no menu.
- Alarmes duplicados sao recusados enquanto o processo registrado estiver
  ativo.
- Processo filho passa a ser coletado para evitar estado zumbi.
- Parada valida PID, fingerprint e token de inicio antes de enviar sinal.

## 2026-07-29 - Operacao por AI-worker

- Adicionados `AGENTS.md` e protocolo de comandos para outra IA.
- Documentados ciclo `start`/hooks/`touch`/`finish` e codigos de saida.
- Adicionado instalador Linux para expor `ai-presence` em `~/.local/bin`.
- Documentados launcher Windows e limites atuais de systemd/X11.
- Registrada a decisao de adiar Abstract Factory ate existir um segundo
  adaptador concreto.

## 2026-07-29 - v0.4.0

- Integrado o antigo fluxo de `prosseguir_tarefas.py` ao AI Presence Monitor.
- Adicionados comandos `continue` e `continue-task`.
- Mensagem padrao definida como `continue` e delay padrao como 60 segundos.
- Extraido despacho textual X11 reutilizavel com alvo exato e clipboard
  restaurado.
- Emissao bem-sucedida pode registrar
  `observation:automation:continue` para worker ativo.
- Protocolo 2 reinicia `last_activity_at`; Protocolo 1 preserva
  `last_signal_at`.
- Falha, cancelamento, `dry-run` e worker inativo nao sincronizam atividade.
- Adicionada opcao 18 ao menu interativo.
- Pacote migrado para layout `src/`.
- Adicionados guia de continuidade, indice documental, gate local e workflow
  de qualidade.
- `.env.example` recebeu os campos `PRESENCE_CONTINUE_*`; o `.env` real nao foi
  alterado.
- Suite ampliada para 74 testes, aprovada em Python 3.10, 3.11 e 3.12.
- Cobertura total validada em 86%; lint, tipagem e build aprovados.
- Wheel 0.4.0 instalado no ambiente dedicado. SHA-256:
  `543477a9218aaff6578aaaade0dd0c5f7b50332633f97a8649719763f4ea9968`.
- Copia do banco e banco real preservados; servicos permaneceram inativos.

## 2026-07-16

- Criado planejamento da Task 001 para observer de hooks do Codex.
- Documentadas decisoes, arquitetura, seguranca e rollback antes da implementacao.
- Implementado `ai_presence_monitor.codex_hook`.
- Adicionado subcomando `codex-hook`.
- Adicionado wrapper `hooks/codex_presence_hook.py`.
- Adicionado exemplo `examples/codex/hooks.json`.
- Adicionados testes unitarios para parsing, auto-start e registro de atividade.
- Implementado instalador/desinstalador seguro de hooks do Codex com backup e dry-run.
- Instalado hook real em `/home/josue/.codex/hooks.json` com 5 eventos configurados.
- Criado `docs/ENVIRONMENT-GUIDE.md` com explicacao detalhada do `.env`, webhooks, Codex, fluxo interno, protocolos e possibilidades de uso.
- Atualizado `.env.example` com defaults recomendados para Codex/Protocolo 2 e criado `docs/CONFIGURANDO-ENV.md` com checklist de preenchimento do `.env`.
- Implementada janela de expediente via `.env` e repeticao configuravel de alertas enquanto o worker continuar atrasado.

## 2026-07-27 - v0.2.0

- Corrigida descoberta de pacotes e validada geracao de wheel.
- Adicionada resolucao portatil de `.env` e banco relativo ao arquivo.
- Adicionados escopos de worker `global`, `project`, `session` e
  `project-session`.
- Hook passou a usar o Python absoluto com `-m ai_presence_monitor.codex_hook`.
- Mantida remocao de hooks legados baseados em `codex_presence_hook.py`.
- Adicionado gerador idempotente de servico systemd de usuario com backup.
- Menu interativo passou a preservar expediente e repeticao ao regravar `.env`.
- Criado `docs/PORTABILIDADE.md`.
- Configuracao local migrada para o diretorio XDG do usuario, mantendo link
  simbolico no checkout para compatibilidade.
- Corrigida compatibilidade com Python 3.10 substituindo `datetime.UTC` por
  `timezone.utc`; a incompatibilidade foi encontrada no teste do wheel em tres
  versoes do Python.
- Adicionado `scripts/test-python-matrix.sh` para validar sequencialmente Python
  3.10, 3.11 e 3.12.
- Adicionados testes do transporte HTTP e persistencia completa do `.env`
  gerado pelo menu interativo.
- Auditoria final: 33 testes em cada uma das tres versoes do Python, lint e
  tipagem sem erros, 82% de cobertura no nucleo e smoke real do systemd.
- Cobertura total elevada de 61% para 89%, sem excluir CLI ou menu da medicao.
- Suite ampliada para 46 testes, aprovada em Python 3.10, 3.11 e 3.12.
- Adicionado gate permanente de cobertura total em 80% no `pyproject.toml`.

## 2026-07-29 - v0.3.0

- Adicionadas perguntas e respostas correlacionadas pelo Discord.
- Implementado polling REST com bot, allowlist e resposta direta obrigatoria.
- Adicionadas tabelas `remote_questions` e `observer_state`.
- Implementado fallback X11 com `xdotool`, `xclip` e restauracao do clipboard.
- Entrega exige o mesmo ID e titulo de janela capturados.
- Adicionados estados `input_emitted` e `delivery_confirmed` pelo hook do Codex.
- Falhas GUI ficam em `dispatch_failed` sem retry automatico.
- Adicionados comandos `ask-user`, `observe-replies`, `questions` e
  `dispatch-answer`.
- Adicionado gerador de unidade `ai-presence-reply-observer.service`.
- Menu e `.env.example` atualizados; recurso permanece desativado por padrao.
- Criado `docs/RESPOSTAS-REMOTAS-DISCORD-CODEX.md`.
- Suite ampliada para 62 testes, aprovada em Python 3.10, 3.11 e 3.12.
- Cobertura total validada em 86%; lint, tipagem e scripts aprovados.
- Wheel 0.3.0 instalado no ambiente dedicado. SHA-256:
  `220f651cf3c6567f40378c02b6f935f6fdf028db2d36e934420786a387d6ac17`.
- Migração validada em copia do banco real, sem alterar contagens anteriores.
