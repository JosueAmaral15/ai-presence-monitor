# Rollback

## Task 001 - Codex Hook Observer

## Criterios para rollback

Execute rollback se:

- Codex mostrar erro recorrente ao iniciar ou usar ferramentas.
- O banco SQLite receber eventos errados ou excessivos.
- O monitor gerar alertas inesperados depois da instalacao do hook.

## Como reverter

### 1. Desabilitar hook do Codex

Remova ou comente as entradas adicionadas em `~/.codex/hooks.json` ou no `.codex/hooks.json` do projeto monitorado.

Depois, no Codex, abra `/hooks` e confirme que o hook nao esta ativo.

Tambem e possivel remover automaticamente apenas os hooks deste projeto:

```bash
python3 -m ai_presence_monitor uninstall-codex-hook
```

Se precisar restaurar o arquivo anterior, use o backup `hooks.json.backup-*` criado no mesmo diretorio do alvo.

### 2. Voltar ao modo manual

Use novamente:

```bash
python3 -m ai_presence_monitor start --protocol protocol2 --task "tarefa"
python3 -m ai_presence_monitor touch --protocol protocol2 --task "tarefa"
python3 -m ai_presence_monitor finish --protocol protocol2 --task "tarefa"
```

### 3. Remover estado de teste, se necessario

Se o problema ocorreu em banco de teste:

```bash
rm /tmp/ai-presence-monitor-*.db
```

Nao remova `presence.db` real sem backup.

## Tempo estimado

5-10 minutos.

## Task 003 - Janela de expediente e repeticao

Para desativar a nova politica sem remover codigo, ajuste o `.env`:

```env
PRESENCE_WORK_WINDOW_ENABLED=false
PRESENCE_ALERT_REPEAT_ENABLED=false
```

Se quiser manter expediente, mas parar repeticao:

```env
PRESENCE_ALERT_REPEAT_ENABLED=false
```

Se quiser manter repeticao, mas cobrar em qualquer horario:

```env
PRESENCE_WORK_WINDOW_ENABLED=false
```

Desde a versao 0.4.2, vermelho e unico por episodio, independentemente do valor
de `PRESENCE_ALERT_REPEAT_LEVELS`. Para restaurar o comportamento repetitivo
antigo, e necessario voltar o pacote para 0.4.1; alterar apenas o `.env` nao
reativa repeticoes vermelhas.

## Task 004 - Portabilidade e isolamento

Voltar temporariamente ao worker unico:

```env
PRESENCE_CODEX_WORKER_SCOPE=global
```

Regere os hooks depois de instalar a versao desejada:

```bash
ai-presence install-codex-hook
```

Remover o servico continuo:

```bash
systemctl --user disable --now ai-presence-monitor.service
ai-presence uninstall-systemd-service
systemctl --user daemon-reload
```

Depois de corrigir uma falha persistente e antes de reativar a unidade:

```bash
ai-presence observe-replies --once
systemctl --user reset-failed ai-presence-reply-observer.service
systemctl --user start ai-presence-reply-observer.service
```

O limite padrao do observer e tres falhas em cinco minutos, com 30 segundos
entre tentativas. O rollback do wheel restaura a definicao anterior quando a
unidade for reinstalada.

O desinstalador informa o caminho do backup `.service.backup-*`.

Para restaurar hooks, use `hooks.json.backup-*` ou execute:

```bash
ai-presence uninstall-codex-hook
```

O banco 0.1 permanece compativel; mudar escopo cria novos IDs de worker, sem
apagar os anteriores.

## Task 006 - Respostas remotas

Desative os dois niveis:

```env
PRESENCE_REMOTE_QUESTIONS_ENABLED=false
PRESENCE_GUI_ANSWER_ENABLED=false
```

Pare e remova o observer:

```bash
systemctl --user disable --now ai-presence-reply-observer.service
ai-presence uninstall-reply-observer-service
systemctl --user daemon-reload
```

Remova `DISCORD_BOT_TOKEN` e `DISCORD_QUESTION_WEBHOOK_URL` do `.env` quando nao
forem mais necessarios. As tabelas `remote_questions` e `observer_state` podem
permanecer sem afetar os dados de presenca.

Para rollback de pacote, reinstale o wheel 0.2.0. O esquema novo e aditivo e a
versao anterior ignora as tabelas desconhecidas.

## Task 007 - Continue integrado e layout `src/`

Desativar somente a sincronizacao:

```env
PRESENCE_CONTINUE_SYNC_ACTIVITY=false
```

Tambem e possivel usar `--no-sync-activity` em uma unica execucao. Deixar de
executar `continue` nao afeta monitor, hooks, respostas remotas ou banco.

Antes de voltar a uma versao sem controle de alarme, interrompa qualquer som:

```bash
ai-presence stop-alarm
```

Na versao 0.4.3, `RED_ALERT_MAX_DURATION_SECONDS=15` limita automaticamente o
som. Ao voltar para 0.4.2, esse limite deixa de existir; remova `-loop 0` de
`RED_ALERT_COMMAND` ou use `stop-alarm` antes do rollback.

Para voltar ao pacote anterior:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install \
  --force-reinstall /caminho/para/ai_presence_monitor-0.3.0-py3-none-any.whl
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" \
  install-codex-hook
```

O esquema SQLite nao mudou na Task 007. O `.env` anterior continua valido
porque os novos campos possuem defaults internos.

Para reverter o checkout local, use a baseline ou o commit anterior em uma nova
branch. Nao apague o `.env` nem o banco durante o rollback.

## Task 012 - Adaptadores do Windows

Antes de voltar para a versao 0.4.3, interrompa um alarme ativo:

```powershell
ai-presence.exe stop-alarm
```

Remova somente as tarefas administradas pelo pacote:

```powershell
ai-presence.exe uninstall-background-service --component monitor
ai-presence.exe uninstall-background-service --component reply-observer
```

Se o launcher nao estiver disponivel, o fallback explicito e:

```powershell
schtasks.exe /Delete /TN "AI Presence Monitor" /F
schtasks.exe /Delete /TN "AI Presence Reply Observer" /F
```

Depois, reinstale um wheel 0.4.3 conhecido. Nao remova o `.env` nem o SQLite:
nao houve migracao de esquema e as chaves novas preservam defaults compativeis.
