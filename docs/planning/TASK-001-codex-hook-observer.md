# Planejamento Solo: Codex Hook Observer

**Data**: 2026-07-16  
**Tempo estimado**: 1-2 horas  
**Prioridade**: Alta

## 1. O Que Precisa Ser Feito?

Criar um observer passivo para hooks do Codex. O observer recebe eventos de lifecycle do Codex, registra atividade local no SQLite e permite que o monitor existente aplique os protocolos de alerta.

Isso evita falso alerta vermelho no Protocolo 2 quando o Codex esta trabalhando por mais de 15 minutos, desde que haja eventos de ferramenta, prompt, sessao ou finalizacao de turno.

**Criterios de pronto**:

- [x] Existe comando `codex-hook`.
- [x] Existe script `hooks/codex_presence_hook.py` com caminho importavel mesmo sem instalar pacote.
- [x] Evento de hook atualiza `last_activity_at` sem alterar `last_signal_at`.
- [x] O hook e silencioso por padrao e nao posta em Discord/Telegram.
- [x] Falhas nao quebram a sessao do Codex por padrao.
- [x] Testes automatizados validam o comportamento.

## 2. Analise Rapida do Codigo Existente

**Arquivos que vou mexer**:

- `ai_presence_monitor/store.py` - adicionar metodo de observacao passiva.
- `ai_presence_monitor/cli.py` - adicionar subcomando `codex-hook`.
- `ai_presence_monitor/config.py` - adicionar opcoes de observer via env.
- `README.md` e `docs/` - documentar uso, arquitetura, seguranca e rollback.

**Arquivos novos**:

- `ai_presence_monitor/codex_hook.py` - parsing do JSON de hook e gravacao de atividade.
- `hooks/codex_presence_hook.py` - wrapper executavel por hook.
- `examples/codex/hooks.json` - exemplo de configuracao do Codex.
- `tests/test_codex_hook.py` - testes unitarios.

## 3. Como Vou Implementar?

Abordagem:

1. Receber JSON por `stdin`.
2. Extrair `hook_event_name` ou `hookEventName`.
3. Derivar worker por env/config: `PRESENCE_CODEX_WORKER_ID` ou `<computador>:codex`.
4. Derivar protocolo por `PRESENCE_CODEX_PROTOCOL` ou protocolo padrao.
5. Gravar observacao passiva no SQLite.
6. Sair com codigo `0` e sem output por padrao.

Escolha tecnica: usar apenas biblioteca padrao Python. Nao adiciona dependencia nova e reduz manutencao.

## 4. Passo a Passo

1. Criar docs e plano.
2. Implementar `record_observation` no store.
3. Implementar parser/runner do hook.
4. Expor subcomando no CLI.
5. Criar script wrapper e exemplo de `hooks.json`.
6. Atualizar README/docs.
7. Criar e rodar testes.

## 5. Como Vou Testar?

- `python3 -m compileall -q ai_presence_monitor hooks tests`
- `python3 -m unittest discover -s tests -v`
- Simular hook com JSON em `stdin`.
- Confirmar que o worker fica `active`, `last_activity_at` e atualizado e `last_signal_at` nao e usado como ponto publico.
- Confirmar que JSON invalido nao quebra o Codex no modo padrao.

## 6. Documentacao a Atualizar

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/security/SECURITY.md`
- `docs/rollback/ROLLBACK.md`
- `docs/CHANGELOG.md`
- `history-chat.md`

## 7. Duvidas Bloqueantes

Nao ha duvida bloqueante para esta etapa porque a recomendacao ja foi aprovada pelo usuario. Assumirei:

- Observer do Codex sera passivo.
- Ele nao fara postagem direta em Discord/Telegram.
- O monitor existente continuara responsavel por alertas.
- A instalacao automatica em `~/.codex/hooks.json` ficara para passo futuro, para evitar mexer em configuracao global sem confirmacao explicita.

## 8. Riscos e Plano B

**Risco**: hook mal configurado gerar ruido ou falhar.  
**Mitigacao**: modo silencioso, sem dependencia externa, sem rede, erro recuperavel por padrao.

**Risco**: o evento de hook nao ter todos os campos esperados.  
**Mitigacao**: aceitar `hook_event_name` e `hookEventName`, manter metadata generica e gravar o que existir.

**Plano B**: remover/desabilitar a entrada do hook no `hooks.json`; o monitor volta ao comportamento manual por `start/touch/finish`.

## 9. Checklist Pre-Implementacao

- [x] Protocolo Simplicidade 3 lido operacionalmente.
- [x] Documentacao atual do Codex Hooks consultada no manual oficial local.
- [x] Codigo existente estudado.
- [x] Planejamento criado.
- [x] Rollback definido.
