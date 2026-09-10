# Plano de Acao: Orientacao para Respostas Discord Invalidas

## TL;DR

Enquanto existir pergunta Discord pendente dentro do prazo, cada mensagem
humana de usuario autorizado que nao puder ser correlacionada deve receber uma
orientacao no mesmo canal. O aviso deve ensinar o uso de **Responder**, mencionar
o usuario de forma controlada e explicar `Message Content Intent` quando o
Discord ocultar o texto.

## Origem

No E2E da Task 013, o observer leu uma mensagem normal de usuario autorizado,
mas recebeu `type=0`, sem `message_reference` e com `content` vazio. A rejeicao
foi segura, porem o usuario nao recebeu feedback no Discord sobre como corrigir
a resposta.

## Escopo

- classificar mensagens humanas autorizadas que nao correspondam a uma
  pergunta pendente;
- publicar uma orientacao no mesmo canal para cada mensagem invalida;
- mencionar somente o autor autorizado, com `allowed_mentions` restritivo;
- diferenciar ausencia de referencia, referencia incorreta e conteudo vazio;
- manter silencio para bots, webhooks, usuarios fora da allowlist e quando nao
  houver pergunta pendente;
- registrar contadores de lembretes enviados e falhos na saida operacional;
- nao repetir automaticamente tentativa de aviso com resultado incerto;
- atualizar documentacao, versao, testes e pacote instalado.

## Decisao Tecnica

O cursor existente fornece semantica de uma tentativa por mensagem recebida.
O observer tentara o lembrete antes de avancar o cursor e, mesmo se a chamada
falhar, contabilizara a falha e avancara. Isso evita que um timeout apos aceite
do webhook produza lembretes duplicados no ciclo seguinte.

O lembrete sera enviado pelo webhook ja configurado. A mencao usara somente o
ID numerico que ja passou pela allowlist:

```json
{
  "parse": [],
  "users": ["ID_AUTORIZADO"]
}
```

Nenhuma resposta invalida sera enviada ao Codex GUI. A regra de aceitacao
continua exigindo canal correto, usuario autorizado, resposta direta, pergunta
pendente e conteudo textual nao vazio.

## Fases

| Fase | Entrega | Status |
|---|---|---|
| 1 | Diagnostico E2E e plano | concluida |
| 2 | Transporte e classificacao | concluida |
| 3 | Testes unitarios e regressao | concluida |
| 4 | Documentacao e versao | concluida |
| 5 | Gate, build e instalacao | concluida |
| 6 | Retomada do E2E real | bloqueada: intent continua desativado |

## Criterios de Aceite

- [x] Usuario autorizado sem `message_reference` recebe orientacao.
- [x] Referencia sem pergunta pendente correspondente recebe orientacao quando
      ainda existe outra pergunta dentro do prazo.
- [x] Conteudo vazio inclui instrucao sobre `Message Content Intent`.
- [x] Lembrete usa mencao limitada ao autor permitido.
- [x] Bot, webhook e usuario nao autorizado nao geram lembrete.
- [x] Ausencia de pergunta pendente nao gera lembrete.
- [x] Cada mensagem invalida causa no maximo uma tentativa de aviso.
- [x] Falha de aviso nao causa entrega GUI nem retry automatico.
- [x] Resposta valida preserva `answered -> input_emitted ->
      delivery_confirmed`.
- [x] Testes, cobertura, lint, tipos, build e verificacao de diff passam.
- [ ] E2E real confirma a orientacao no canal e depois uma resposta valida.

## Rollback

Reinstalar o wheel `0.5.1` e reiniciar somente o reply observer. Perguntas e
respostas existentes permanecem no SQLite; nao ha migracao de esquema.

## Dependencias Externas

- O usuario precisa habilitar e salvar **Message Content Intent** no aplicativo
  do bot para que respostas textuais em canal de servidor cheguem preenchidas.
- A segunda tentativa usou uma nova pergunta dentro do prazo e uma resposta
  direta do usuario autorizado. A API retornou o texto vazio e as flags da
  aplicacao confirmaram que os recursos `gateway_message_content` e
  `gateway_message_content_limited` continuam desativados.
- Uma nova tentativa depende de habilitar e salvar o intent e de autorizacao
  explicita para publicar outra pergunta e entregar a futura resposta ao Codex
  GUI.

## Registro de Evidencias

- 2026-09-09: 14 testes focados de Discord e fluxo remoto aprovados.
- 2026-09-09: gate completo aprovado com 121 testes, cobertura total de 87%,
  Ruff, mypy, sdist, wheel e `git diff --check`.
- 2026-09-09: wheel `0.5.2` instalado no venv dedicado.
- 2026-09-09: monitor e observer reativados, habilitados e com
  `NRestarts=0`.
- 2026-09-09: processo atual do observer registra os contadores
  `orientadas` e `falhas_orientacao`; E2E externo permanece pendente.
- 2026-09-10: pergunta `7a22a705-8a91-41cc-81c9-93c3b041c837` publicada com
  nova correlacao e prazo de 30 minutos.
- 2026-09-10: resposta direta do usuario autorizado referenciou a mensagem
  correta, mas chegou com `content_length=0`; permaneceu `pending`, nao foi
  enviada a GUI e gerou uma orientacao no canal.
- 2026-09-10: consulta autenticada da aplicacao `AI Presence Monitor` retornou
  `flags=0`, confirmando que o Message Content Intent nao esta ativo.
