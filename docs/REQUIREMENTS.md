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

## Portabilidade

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
