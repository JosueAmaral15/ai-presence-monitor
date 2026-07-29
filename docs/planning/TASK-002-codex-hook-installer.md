# Planejamento Solo: Instalador Seguro de Hooks do Codex

**Data**: 2026-07-16  
**Tempo estimado**: 1 hora  
**Prioridade**: Alta

## 1. O Que Precisa Ser Feito?

Criar uma forma segura de instalar e remover o hook do AI Presence Monitor em `hooks.json` do Codex.

O usuario pediu para prosseguir apos a implementacao do observer. A proxima etapa natural e facilitar a ativacao do hook, mas sem editar configuracao global de forma opaca.

**Criterios de pronto**:

- [x] CLI instala em `~/.codex/hooks.json` por padrao.
- [x] CLI aceita alvo alternativo para testes/projetos locais.
- [x] Arquivo existente recebe backup antes de modificacao.
- [x] Instalacao repetida nao duplica hooks.
- [x] Desinstalacao remove apenas hooks deste projeto.
- [x] README documenta que o Codex ainda precisa revisar/confiar via `/hooks`.

## 2. Analise Rapida do Codigo Existente

**Arquivos a mexer**:

- `ai_presence_monitor/cli.py` - novos subcomandos.
- `ai_presence_monitor/interactive.py` - opcao no menu.
- `README.md` e `docs/ROLLBACK.md` - uso e reversao.

**Arquivos novos**:

- `ai_presence_monitor/codex_hook_installer.py`
- `tests/test_codex_hook_installer.py`

## 3. Como Vou Implementar?

Usar JSON estruturado, sem manipulacao textual.

Fluxo de instalacao:

1. Ler `hooks.json` se existir.
2. Validar que e objeto JSON.
3. Remover entradas antigas cujo comando aponta para `codex_presence_hook.py`.
4. Adicionar entradas oficiais do AI Presence Monitor.
5. Fazer backup se arquivo existia.
6. Escrever JSON formatado.

Fluxo de desinstalacao:

1. Ler `hooks.json`.
2. Remover apenas comandos do AI Presence Monitor.
3. Fazer backup.
4. Escrever arquivo atualizado.

## 4. Como Vou Testar?

- Teste de instalacao em arquivo temporario.
- Teste de reinstalacao idempotente.
- Teste de preservacao de hook externo.
- Teste de desinstalacao.
- Smoke test com `--dry-run` e alvo temporario.

## 5. Riscos e Plano B

**Risco**: corromper `hooks.json` existente.  
**Mitigacao**: backup antes de escrever, parsing JSON antes da escrita, `--dry-run`.

**Risco**: remover hook de outro projeto por engano.  
**Mitigacao**: remover somente comandos que contenham `codex_presence_hook.py`.

**Rollback**: restaurar `hooks.json.backup-*` ou usar `uninstall-codex-hook`.
