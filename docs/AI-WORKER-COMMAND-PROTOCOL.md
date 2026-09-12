# Protocolo de Comandos para AI-workers

## Objetivo

Este documento define como uma IA de programacao deve operar o AI Presence
Monitor por comandos deterministas de terminal. O monitor acompanha workers,
projetos e atividade registrada. Ele nao monitora uma aba de terminal pelo
texto exibido no cabecalho.

Para um Codex trabalhando no AmaralAgenda, a identidade recomendada e derivada
do caminho absoluto do projeto:

```text
notebook-josue:codex:project=AmaralAgenda-23813ab6
```

O nome pode variar em outra maquina porque o hash inclui o caminho absoluto.
Por isso, a IA deve informar `--project` e nao gravar o ID derivado em scripts.

## Descoberta do Comando

No Linux:

```bash
command -v ai-presence
ai-presence --help
```

Fallback Linux quando o comando nao estiver no `PATH`:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --help
```

No Windows, a instalacao Python cria `ai-presence.exe` dentro de
`%LOCALAPPDATA%\ai-presence-monitor\venv\Scripts`. Um alias de shell nao e o
mecanismo principal porque aliases geralmente nao sao carregados por
subprocessos, hooks, CI ou servicos.

## Variaveis do Turno

Antes dos comandos, a IA deve obter a raiz real do projeto:

```bash
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
TASK="descricao curta da tarefa"
```

O caminho deve identificar o projeto em que a IA esta trabalhando, nao o
checkout do AI Presence Monitor.

## Maquina de Estados

```text
idle --start--> active --hooks/touch--> active --finish--> idle
```

`PRESENCE_CODEX_AUTO_START=false` exige `start` explicito. Isso impede que
qualquer evento incidental do Codex reative um worker encerrado.

### 1. Inicio

Execute uma vez depois de aceitar a tarefa:

```bash
ai-presence start \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "Codex iniciou a tarefa"
```

`start` registra o worker e publica no canal de ponto. Nao repita `start` como
heartbeat.

### 2. Durante o Trabalho

Os hooks `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse` e
`Stop` registram observacoes silenciosas. Com hooks funcionando, a IA nao
precisa executar `touch` em cada comando.

Quando os hooks estiverem indisponiveis, registre somente atividade real:

```bash
ai-presence touch \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "checkpoint de trabalho concluido"
```

Nao execute `touch` apenas porque um temporizador expirou. O objetivo e reduzir
falsos positivos sem criar presenca artificial sem trabalho correspondente.

### 3. Pergunta ao Usuario

Quando a superficie do Codex oferecer entrada nativa do usuario, prefira esse
mecanismo. Como fallback remoto:

```bash
ai-presence ask-user \
  --project "$PROJECT" \
  --question "Pergunta objetiva para o usuario"
```

O observer de respostas e um processo separado. Uma resposta so e aceita se
estiver correlacionada com a pergunta e vier de um usuario permitido.

### 4. Continuidade

`continue` envia entrada a uma sessao Codex. Por padrao, usa `codex queue` sem
controlar mouse ou teclado; X11/Win32 e apenas fallback. Ele nao e necessario
para registrar atividade comum:

```bash
ai-presence control show
ai-presence --dry-run continue --project "$PROJECT" --thread SESSAO_EXATA
ai-presence continue --project "$PROJECT"
```

Use o comando real somente quando `task-automation` estiver habilitado ou o
usuario tiver autorizado `--authorize-once`, e depois de aplicar a
[norma de acionamento](CONTINUE-CODEX.md#norma-de-acionamento-pela-ia). Em
resumo: a etapa atual deve estar concluida, a proxima tarefa precisa ser
concreta e nao pode existir pergunta, bloqueio ou outra execucao pendente.

Uma emissao sincrona bem-sucedida pode atualizar `last_activity_at` de um
worker ativo no Protocolo 2. Ao enviar para a propria sessao, a CLI retorna
`dispatch_started` sem atualizar o monitor; somente o hook posterior registra
atividade. Falha, cancelamento, dry-run e worker inativo tambem nao atualizam o
monitor. Nenhum estado inicial prova que o Codex processou a mensagem.

Na ausencia de `PRESENCE_CODEX_THREAD_ID`, o comando real pode inferir a sessao
do hook mais recente do mesmo worker. Nunca escolha outra sessao para contornar
uma falha. Consulte [SYSTEM-TRAY-NATIVE-INPUT.md](SYSTEM-TRAY-NATIVE-INPUT.md).

No fallback GUI, uma aba do GNOME Terminal nao e uma janela X11 independente. O nome da aba pode
nao aparecer no titulo da janela e, nesse caso, nao serve como alvo seguro para
`xdotool`.

No Windows, o alvo e uma janela superior Win32 e `--window-id` recebe o
`MainWindowHandle`, nao o PID. Em ambas as plataformas, prefira um padrao de
titulo unico e estavel.

### 5. Encerramento

Execute uma vez quando o trabalho solicitado terminar:

```bash
ai-presence finish \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "$TASK" \
  --message "Codex concluiu a tarefa"
```

Nao use `finish` para pausas curtas se a tarefa continua sob responsabilidade
do mesmo worker.

## Integracao Git por Sessao

Ao terminar cada sessao de implementacao:

1. execute os gates aplicaveis e revise o diff;
2. crie um commit na branch da tarefa;
3. integre trabalho funcional e validado em `develop`;
4. promova `develop` para `main` somente quando todos os requisitos de
   publicacao, testes de integracao e dependencias externas obrigatorias
   estiverem concluidos;
5. registre bloqueios no plano ou em `docs/TASKS.md`, sem declarar a versao
   pronta para publicacao.

Uma suite local aprovada nao substitui um E2E real exigido pelo plano nem uma
CI de plataforma que ainda nao executou. Commit e promocao de branch devem
preservar o historico; nunca descarte alteracoes do usuario para obter um
worktree limpo.

## Comandos de Diagnostico

Estes comandos nao controlam a GUI:

```bash
ai-presence status
ai-presence stop-alarm
systemctl --user status ai-presence-monitor.service
journalctl --user -u ai-presence-monitor.service -n 100 --no-pager
```

Se houver um alarme audivel, a IA pode executar `ai-presence stop-alarm`
imediatamente. Essa operacao nao exige autorizacao adicional porque apenas
interrompe um processo de alarme previamente iniciado pelo monitor.

O monitor e o observer de respostas sao componentes diferentes:

| Componente | Funcao |
|---|---|
| hooks do Codex | registram evidencia local de atividade |
| monitor | avalia atrasos e envia alertas |
| observer de respostas | consulta o Discord e processa respostas |
| transporte nativo | enfileira texto em uma sessao exata com `codex queue` |
| dispatcher GUI | fallback opcional de mouse e teclado |

`observer nao instalado` significa que a unidade systemd do Linux ou a tarefa
`AI Presence Reply Observer` do Windows ainda nao foi instalada. Isso nao
impede o monitor de alertas nem os hooks de funcionar.

## Codigos de Saida

- `0`: comando concluido;
- valor diferente de zero: falha de configuracao, transporte ou operacao.

A IA deve verificar o codigo de saida e relatar o erro. Nao deve repetir
automaticamente nenhum envio com resultado incerto.

`dispatch_started` com codigo zero significa apenas que o processo destacado
foi criado. A IA deve encerrar o turno e aguardar evidencia posterior, sem
executar novo envio nem `touch` para fabricar confirmacao. Hook isolado prova
atividade, nao autoria; testes E2E exigem o marcador exclusivo definido em
[USO-COMO-FERRAMENTA.md](USO-COMO-FERRAMENTA.md).

## Linux e Windows

O nucleo, SQLite e a CLI Python sao portateis. `pip` gera um launcher apropriado
para cada sistema:

- Linux: `venv/bin/ai-presence`;
- Windows: `venv\Scripts\ai-presence.exe`.

Na versao 0.6.2, somente Linux e um runtime suportado. A implementacao Windows
foi preservada, mas fica desabilitada por padrao. Um AI-worker nao deve ativar
`PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true` sem autorizacao explicita para uma
validacao controlada.

Uma Abstract Factory seleciona os adaptadores operacionais sem alterar os casos
de uso:

| Capacidade | Linux atual | Windows |
|---|---|---|
| processo continuo | systemd de usuario | Task Scheduler do usuario |
| entrada nativa Codex | `codex queue` | `codex queue.exe` |
| controle GUI | X11, `xdotool`, `xclip` | API Win32 e `SendInput` |
| alarme limitado | GNU `timeout` e `/proc` | runner e `taskkill /T /F` |
| CLI e banco | suportado | experimental com opt-in |

Use os comandos portateis `install-background-service` e
`uninstall-background-service`; a factory escolhe systemd ou Task Scheduler. A
logica dos Protocolos 1 e 2 permanece compartilhada. No Windows, instalacao e
operacao exigem o opt-in; ajuda e recuperacao permanecem acessiveis sem ele.

## Instrucao para Outro Codex

Use esta orientacao no prompt inicial:

```text
Leia AGENTS.md, docs/USO-COMO-FERRAMENTA.md e
docs/AI-WORKER-COMMAND-PROTOCOL.md do projeto ai-presence-monitor. Use
ai-presence com --project apontando para a raiz deste projeto. Registre start
ao iniciar, confie nos hooks durante o trabalho e registre finish somente ao
concluir. Prefira entrada nativa e nao execute automacao de continuidade ou
fallback GUI sem autorizacao. Em E2E, use marcador exclusivo e nunca atribua
uma mensagem ao transporte apenas porque ocorreu um hook posterior.
```
