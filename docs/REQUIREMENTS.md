# Requirements

## Presenca Artificial

- O sistema deve registrar atividade de IAs/agentes em um banco local SQLite.
- O sistema deve suportar Protocolo 1 e Protocolo 2 de forma separada.
- O Protocolo 2 deve aceitar evidencia silenciosa de atividade para evitar falso alerta em tarefas longas.

## Codex Hook Observer

- Deve receber payload de hook do Codex via `stdin`.
- Deve aceitar campos `hook_event_name` e `hookEventName`.
- Deve registrar atividade sem enviar notificacao direta.
- Deve ser fail-open por padrao para nao quebrar o ciclo do Codex.
- Deve permitir fail-closed por configuracao quando o usuario desejar enforcement forte.
- Deve evitar gravar transcript completo ou secrets.
- Deve ter exemplo de configuracao de `hooks.json`.

## Diagnostico de Causa

- Observers de diagnostico devem registrar fatos e nao decidir alertas ou
  executar recuperacao diretamente.
- Evidencia deve identificar fonte, tipo, estado, worker, sessao opcional,
  horario e expiracao opcional sem armazenar payload bruto ou transcript.
- Todo diagnostico deve referenciar ao menos uma evidencia persistida.
- Evidencias de workers diferentes ou sessoes Codex conflitantes nao devem ser
  combinadas no mesmo diagnostico.
- Diagnosticos devem declarar causa, confianca e resumo curto.
- Deve existir no maximo um incidente de diagnostico aberto por worker.
- Incidentes devem preservar abertura, diagnostico atual, severidade, ultima
  notificacao e resolucao.
- `unexplained_inactivity` deve ser usado quando nao houver evidencia suficiente
  para uma causa especifica; o sistema nao deve declarar inatividade genuina
  como fato.
- Tabelas de diagnostico devem ser aditivas e compativeis com bancos existentes.
- Persistir evidencia ou diagnostico nao deve atualizar os relogios dos
  Protocolos 1 e 2.
- Recuperacao automatica deve permanecer fora da fundacao e desabilitada ate
  possuir autorizacao, politica one-shot e validacao E2E propria.
- O probe do Codex App Server deve permitir somente inicializacao, leitura de
  metadata sem turns, leitura de limites e assinatura/desassinatura
  observacional explicita.
- O probe nao deve expor `turn/start`, `turn/steer`, injecao de itens, queue ou
  fallback GUI e nao deve persistir payload bruto.
- Metadata retornada deve corresponder a sessao solicitada; eventos de outra
  sessao devem ser descartados.
- Uma sessao `notLoaded` no app-server filho nao deve ser classificada como
  Codex fechado, e conflito `thread_already_active` nao deve ser classificado
  como inatividade.
- Somente hooks Codex reconhecidos devem produzir evidencia diagnostica; o
  estado e o resumo devem vir de uma allowlist constante e possuir TTL.
- O observer de limites deve chamar somente `account/rateLimits/read`, exigir
  worker exato ativo, sanitizar o resultado e ser one-shot por padrao.
- O modo continuo de limites deve ser explicito, revalidar o worker antes de
  cada poll e encerrar quando o worker ficar idle.
- Creditos indisponiveis isoladamente nao devem sobrepor
  `ordinary_usage_allowed=true` nem provar limite excedido.
- Hook evidence e account-limit evidence nao devem atualizar
  `last_activity_at`, `last_signal_at` ou rearmar alertas de presenca.
- O observer Linux deve ser one-shot por padrao e oferecer `--watch` explicito
  com revalidacao do worker antes e depois de cada coleta.
- Processo deve exigir PID positivo, aceitar nome esperado validado e detectar
  troca de instancia pelos start ticks durante a mesma execucao.
- Rede deve usar apenas rota e links locais, sem DNS, HTTP ou ping, e nao deve
  afirmar conectividade com a Internet.
- Energia deve detectar retomada somente pela diferenca entre relogios de boot e
  monotonic em duas amostras do mesmo watcher.
- Servicos devem ser alvos `.service` explicitos, consultados por
  `systemctl --user show` sem shell e sanitizados para estados permitidos.
- Observers Linux nao devem ler `cmdline`, `environ`, journal, arquivos abertos
  ou payload de rede, nem atualizar relogios de presenca.
- O observer live do App Server deve permanecer desabilitado enquanto a sessao
  monitorada nao compartilhar o mesmo endpoint/daemon validado.
- O motor deve considerar apenas evidencia nao expirada e o lote mais novo por
  fonte/tipo, preservando fatos simultaneos de servicos distintos.
- Evidencias atuais de sessoes Codex diferentes devem falhar fechado sem uma
  sessao explicita; fatos sem sessao podem apoiar somente a sessao selecionada.
- A severidade do incidente deve vir do threshold atual do protocolo do worker,
  nunca de um observer individual.
- Causas atrasadas devem vincular a evidencia da causa e um fato limitado de
  que o relogio de presenca excedeu o threshold.
- Processo executando, rota default, sistema acordado, servico ativo e
  `usage_available` isolados nao devem provar trabalho nem conectividade.
- `diagnose --dry-run` nao deve criar evidencia, diagnostico ou incidente.
- A Fase 5 nao deve enviar notificacao, alarme, input, retry ou recuperacao.
- A notificacao diagnostica deve consumir somente o incidente aberto e seu
  diagnostico atual; observers e o motor nao devem enviar mensagens.
- A chave de deduplicacao deve considerar incidente, causa, confianca,
  severidade e canal sem depender do UUID mutavel do diagnostico atual.
- A tentativa deve ser reservada antes do acesso a rede e deve executar no
  maximo um POST Discord, sem retry automatico.
- Somente entrega HTTP confirmada deve atualizar `last_notified_at`.
- Rejeicao, incerteza ou interrupcao devem permanecer registradas e suprimir
  repeticao automatica da mesma chave semantica.
- `notify-diagnostic-incident --dry-run` nao deve acessar rede nem gravar a
  tabela de tentativas.
- Webhook ausente deve falhar antes da reserva; o fluxo nao deve chamar
  Telegram, alarme, telefone, input do Codex ou recuperacao.
- Recuperacao diagnostica nao deve ser iniciada por observer, motor de
  diagnostico, notificacao, monitor continuo ou timer.
- A recuperacao one-shot deve aceitar somente `codex_closed` com confianca
  media/alta ou `codex_crashed` com confianca alta.
- A tentativa deve exigir worker ativo, incidente aberto, diagnostico atual nao
  expirado, sessao exata coincidente e entrega Discord confirmada para o mesmo
  evento semantico.
- Cada execucao real deve exigir `--authorize-once`; autorizacao persistente de
  automacao nao deve substituir esse consentimento.
- O dry-run deve avaliar os gates sem procurar executavel, reservar tentativa,
  enviar input ou atualizar presenca.
- A reserva `(incident_id, action)` deve ocorrer antes do transporte e suprimir
  repeticao apos `pending`, `dispatch_started`, `input_emitted`, `uncertain` ou
  interrupcao.
- A recuperacao deve usar somente `codex queue` local, sem GUI, remoto, delay,
  Telegram, alarme, telefone, fallback ou encadeamento.
- Estado de transporte nao deve atualizar `last_activity_at`/`last_signal_at`,
  resolver o incidente ou provar processamento; hook posterior e novo
  diagnostico devem fornecer essa evidencia.

## Ciclo de Vida do Produto

- Upgrade suportado deve usar somente wheels locais e nunca resolver
  dependencias ou acessar indice de pacotes durante a transacao.
- O wheel de rollback deve corresponder exatamente a versao instalada antes da
  mutacao.
- Preflight deve validar plataforma, schema, integridade, versoes e estado dos
  servicos sem criar backup ou instalar pacote no modo dry-run.
- Antes da instalacao devem existir copia dos dois wheels, snapshot SQLite,
  hashes SHA-256 e manifesto privado gravado atomicamente.
- Somente servicos gerenciados ativos antes da transacao devem ser parados e
  reiniciados; falha parcial deve restaurar o estado conhecido.
- Falha depois do inicio da instalacao deve tentar exatamente um rollback
  automatico do pacote e banco, sem retry silencioso.
- Rollback manual deve validar manifesto e hashes, exigir autorizacao unica e
  reconhecimento explicito de que o banco sera restaurado.
- Upgrade transacional e suportado somente no Linux ate existir implementacao
  e E2E nativos equivalentes no Windows.
- Processo da bandeja deve ser reiniciado manualmente depois do upgrade porque
  nao pertence aos servicos systemd gerenciados.

## Portabilidade

- A CLI deve fornecer `--version` deterministico sem depender de metadata do
  diretorio atual.
- O schema SQLite deve possuir versao explicita e rejeitar bancos mais novos
  que o runtime sem tentar downgrade.
- A inspecao de schema deve ser somente leitura e nao criar banco ausente.
- O comando `doctor` deve produzir apenas estados sanitizados, sem tokens,
  webhooks, prompts, sessoes ou valores do `.env`.
- O modo estrito deve retornar codigo diferente de zero para avisos, permitindo
  preflight de automacao.

- O projeto deve gerar wheel instalavel para Python 3.10+.
- A configuracao deve funcionar com `.env` central ou por projeto.
- Caminhos relativos do banco devem ser estaveis fora do `cwd`.
- Hooks nao devem depender da permanencia do checkout.
- Workers devem poder ser isolados por projeto e sessao.
- O servico de monitoramento continuo deve ser gerado sem caminhos fixos da
  maquina de desenvolvimento.
- Linux deve permanecer habilitado e suportado sem configuracao adicional.
- Windows deve preservar seus adaptadores e testes, mas sua execucao
  operacional deve exigir opt-in experimental desabilitado por padrao.
- A selecao deve usar uma factory de plataforma, sem duplicar a logica dos
  protocolos.
- A execucao continua usa systemd de usuario no Linux; o Task Scheduler do
  usuario permanece disponivel somente no runtime Windows experimental.
- A distribuicao Windows deve instalar uma base IANA de timezones para
  `ZoneInfo` e fechar conexoes SQLite antes de liberar arquivos.
- O bloqueio Windows deve ocorrer antes de efeitos operacionais, inclusive em
  `--dry-run`, mas deve preservar diagnostico, encerramento e rollback.

## Respostas Remotas

- Perguntas devem ser correlacionadas com a mensagem Discord publicada.
- Somente resposta direta de usuario em allowlist deve ser aceita.
- O observer nao deve expor servidor HTTP publico.
- Cada pergunta deve congelar `native`, `gui` ou `store` antes da publicacao.
- Entrega nativa deve usar `codex queue` para a sessao exata salva.
- Alvo nativo ausente, antigo ou ambiguo deve falhar antes da publicacao.
- Falha nativa nao deve acionar fallback GUI.
- A entrega GUI deve ficar desativada por padrao.
- O alvo GUI deve ser uma janela exata X11 ou Win32, sem fallback para a
  primeira janela.
- Falha ou resultado incerto nao deve causar reenvio automatico.
- Hook posterior do mesmo worker deve confirmar GUI legada; entrega nativa
  tambem deve exigir a mesma sessao salva.
- O observer continuo deve ter unidade systemd ou tarefa agendada separada e
  opcional.
- Falhas persistentes do observer nao devem provocar reinicios ilimitados em
  intervalo curto nem alterar a politica de recuperacao do monitor principal.
- Enquanto houver pergunta pendente, mensagem nao correlacionada de usuario
  autorizado deve receber orientacao no mesmo canal para usar **Responder**.
- Conteudo vazio deve orientar a verificacao de `Message Content Intent`.
- Orientacao nao deve ser enviada para bot, webhook, usuario nao autorizado ou
  quando nao houver pergunta dentro do prazo.
- Cada mensagem invalida deve causar no maximo uma tentativa de orientacao.

## Continue Integrado

- Monitoramento e continuidade devem pertencer ao mesmo pacote e a mesma CLI.
- A mensagem padrao deve ser `continue`.
- O delay padrao deve ser 60 segundos.
- O transporte nativo deve usar `codex queue` sem shell, mouse ou teclado.
- O envio para a propria sessao deve ser nao bloqueante e retornar
  `dispatch_started` sem atualizar presenca antes de um hook posterior.
- O alvo nativo deve ser uma sessao explicita ou inferida de hook do mesmo worker.
- X11/Win32 deve permanecer fallback explicito, desativado por padrao, com
  janela unica capturada e revalidada.
- `--dry-run` nao deve esperar, controlar GUI ou gravar banco.
- Somente emissao bem-sucedida pode sincronizar atividade.
- Sincronizacao deve exigir worker existente e ativo.
- No Protocolo 2, a sincronizacao deve atualizar `last_activity_at`.
- No Protocolo 1, a sincronizacao deve preservar `last_signal_at`.
- Ausencia de atividade posterior deve voltar a gerar alertas normais.
- O projeto deve usar layout `src/` e produzir wheel independente do checkout.
- Uma autorizacao persistente deve bloquear ou liberar a automacao, sem criar
  um temporizador de presenca artificial.

## Bandeja e Controle de Entrada

- CLI e bandeja devem compartilhar o mesmo estado persistente de autorizacao.
- O estado deve ser atomico, local, ignorado pelo Git e nao conter tokens.
- A bandeja deve oferecer habilitar automacao, responder mensagem e sair.
- Preferencias devem separar entrada nativa, fallback GUI, destino remoto e
  sincronizacao de atividade.
- O compositor deve enviar para este computador ou para um endpoint Codex
  remoto autenticado.
- A dependencia da bandeja deve ser opcional para preservar instalacoes CLI.
