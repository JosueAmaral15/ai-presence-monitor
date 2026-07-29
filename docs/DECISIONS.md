# Decisions

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
- Abstract Factory imediata: adiada ate existir um adaptador Windows concreto.

**Consequencia**:

`AGENTS.md` e `docs/AI-WORKER-COMMAND-PROTOCOL.md` definem os comandos. Linux
usa systemd/X11; Windows pode reutilizar a CLI e o SQLite, mas ainda precisa de
Task Scheduler e dispatcher GUI nativo para equivalencia operacional.
