# Planejamento Solo: Respostas Remotas Discord para Codex GUI

## 1. Objetivo

Permitir que um AI-worker publique uma pergunta em um canal dedicado do
Discord, receba uma resposta autorizada e, como fallback para a ausencia de uma
API nativa de entrada, entregue essa resposta na janela exata do Codex GUI.

O recurso e opcional, local e desativado por padrao. Ele nao substitui uma
integracao nativa via MCP ou App Server quando essa integracao estiver
disponivel.

## 2. Escopo

Incluido nesta tarefa:

- envio de pergunta por webhook dedicado do Discord;
- persistencia da pergunta, correlacao e estados no SQLite;
- polling da API REST do Discord por um bot;
- aceitacao somente de resposta direta a pergunta original;
- allowlist de IDs de usuarios do Discord;
- captura e validacao de uma janela X11 exata;
- colagem por `xclip` e acionamento por `xdotool`;
- confirmacao posterior por evento do hook do Codex;
- CLI, `.env.example`, documentacao, testes e auditoria local.

Fora do escopo:

- recepcao de respostas pelo Telegram;
- uso do Discord Gateway/WebSocket;
- exposicao de servidor HTTP publico;
- interpretacao semantica da resposta;
- escolha automatica da primeira janela encontrada;
- reenvio automatico depois de resultado incerto;
- integracao nativa com o prompt interno do Codex.

## 3. Fluxo

1. O AI-worker executa `ask-user` com a pergunta.
2. O programa exige configuracao Discord valida.
3. Se a entrega GUI estiver ativa, uma unica janela deve corresponder ao titulo
   configurado; seu ID e titulo sao guardados.
4. O webhook publica a pergunta e retorna o ID da mensagem Discord.
5. O usuario usa a funcao **Responder** do Discord nessa mensagem.
6. `observe-replies` consulta novas mensagens no canal.
7. O observer valida canal, autor autorizado, referencia e pergunta pendente.
8. A resposta e gravada como `answered`.
9. Com a entrega GUI ativa, o dispatcher revalida o mesmo ID e titulo, ativa a
   janela, clica na posicao configurada, cola a resposta e pressiona Enter.
10. O estado passa a `input_emitted`.
11. O proximo hook do mesmo worker marca `delivery_confirmed`.

## 4. Estados

| Estado | Significado |
|---|---|
| `pending` | Pergunta publicada e aguardando resposta. |
| `publish_failed` | Publicacao no Discord falhou. |
| `answered` | Resposta autorizada persistida, ainda nao entregue. |
| `input_emitted` | Mouse/teclado executados com sucesso local. |
| `delivery_confirmed` | Hook posterior do Codex confirmou nova atividade. |
| `dispatch_failed` | Entrega local falhou antes de confirmacao. |
| `expired` | Prazo da pergunta terminou sem resposta. |

Uma falha `dispatch_failed` nao e reenviada automaticamente. A operacao exige
revisao e comando manual para evitar duplicar texto ou Enter.

## 5. Configuracao

```env
PRESENCE_REMOTE_QUESTIONS_ENABLED=false
DISCORD_QUESTION_WEBHOOK_URL=
DISCORD_BOT_TOKEN=
DISCORD_QUESTION_CHANNEL_ID=
DISCORD_ALLOWED_USER_IDS=
PRESENCE_QUESTION_POLL_INTERVAL_SECONDS=5
PRESENCE_QUESTION_TIMEOUT_SECONDS=1800

PRESENCE_GUI_ANSWER_ENABLED=false
PRESENCE_CODEX_GUI_WINDOW_TITLE=
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
PRESENCE_GUI_CONFIRMATION_TIMEOUT_SECONDS=120
```

O token do bot e a URL do webhook sao segredos. A allowlist usa IDs numericos
do Discord separados por virgula.

## 6. Seguranca e Fail-Safe

- O recurso remoto e recusado quando
  `PRESENCE_REMOTE_QUESTIONS_ENABLED=false`.
- A entrega GUI e independente e recusada quando
  `PRESENCE_GUI_ANSWER_ENABLED=false`.
- O observer ignora bots, mensagens sem referencia e autores fora da allowlist.
- O texto recebido nunca e passado a shell.
- O alvo GUI exige um unico match no momento da pergunta.
- A entrega usa o ID salvo; nunca escolhe a primeira janela disponivel.
- O titulo atual precisa continuar correspondendo ao padrao configurado.
- A area de transferencia e restaurada depois da colagem.
- `--dry-run` nao acessa rede, banco ou GUI para criar uma pergunta.
- Segredos nao aparecem em logs, status ou mensagens Discord.

## 7. Criterios de Aceite

- [x] Pergunta e resposta ficam correlacionadas por IDs Discord.
- [x] Respostas de usuarios nao autorizados sao ignoradas.
- [x] Mensagens que nao usam **Responder** sao ignoradas.
- [x] A mesma mensagem nao e processada duas vezes.
- [x] GUI permanece desativada por padrao.
- [x] Alvo ausente, ambiguo ou alterado nao recebe entrada.
- [x] Texto Unicode e colado sem interpolacao em shell.
- [x] Hook posterior confirma `input_emitted`.
- [x] CLI possui envio, observer, listagem e reenvio manual controlado.
- [x] Testes nao usam Discord nem GUI reais.
- [x] Cobertura total permanece maior ou igual a 80%.
- [x] Python 3.10, 3.11 e 3.12 continuam aprovados.

## 8. Validacao

```bash
python3 -m unittest discover -s tests -v
COVERAGE_CORE=pytrace python3 -m coverage run -m unittest discover -s tests
COVERAGE_CORE=pytrace python3 -m coverage report --fail-under=80
./scripts/test-python-matrix.sh
ruff check ai_presence_monitor hooks tests main.py
mypy ai_presence_monitor
python3 -m build
```

O teste real com Discord e Codex GUI requer autorizacao explicita porque envia
mensagem externa, movimenta o mouse, altera foco e pressiona Enter.

## 10. Resultado

- 62 testes passaram em Python 3.10, 3.11 e 3.12.
- Cobertura total: 86%.
- `ruff`, `mypy`, `bash -n` e `pip check` passaram.
- Wheel 0.3.0 construido, inspecionado e instalado no ambiente dedicado.
- SHA-256 do wheel:
  `220f651cf3c6567f40378c02b6f935f6fdf028db2d36e934420786a387d6ac17`.
- Migração em copia do banco real preservou 1 worker, 17 eventos e 0 alertas,
  com `integrity_check=ok`.
- Servicos permaneceram desabilitados/inativos.
- Teste externo real nao executado por falta das credenciais novas e por exigir
  autorizacao explicita para atuar na GUI.

## 9. Rollback

1. Definir `PRESENCE_REMOTE_QUESTIONS_ENABLED=false`.
2. Definir `PRESENCE_GUI_ANSWER_ENABLED=false`.
3. Encerrar qualquer processo `observe-replies`.
4. Remover `DISCORD_BOT_TOKEN` e o webhook de perguntas do `.env`.
5. Voltar ao wheel 0.2.0, se necessario.

As tabelas novas no SQLite podem permanecer sem afetar workers, eventos ou
alertas antigos.
