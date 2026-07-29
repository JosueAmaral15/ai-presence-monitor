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
