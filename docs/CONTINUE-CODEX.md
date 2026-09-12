# Continue Integrado para o Codex

## Objetivo

O AI Presence Monitor pode aguardar um intervalo e enfileirar uma mensagem em
uma sessao exata do Codex. O transporte recomendado usa `codex queue`, sem
mouse, teclado ou clipboard. X11 e Win32 permanecem como fallback explicito.
A mensagem padrao e `continue` e o atraso padrao e 60 segundos.

Esse recurso substitui o uso separado de `prosseguir_tarefas.py` no fluxo
monitorado.

## Requisitos

- pacote AI Presence Monitor instalado;
- Codex CLI com `codex queue` para a entrada nativa;
- UUID/nome exato da sessao, ou hook recente do mesmo worker.

Para o fallback GUI, tambem e necessario um titulo que identifique exatamente
uma janela visivel do Codex.

No Linux, a sessao deve ser X11 e os comandos `xdotool` e `xclip` precisam
estar instalados. Verifique:

```bash
command -v xdotool
command -v xclip
printf 'sessao=%s display=%s\n' "$XDG_SESSION_TYPE" "$DISPLAY"
```

No Windows 10/11, use uma sessao de desktop interativa e desbloqueada. O
adaptador usa a API Win32 nativa e nao requer dependencia GUI externa. Wayland
e macOS ainda nao possuem adaptador.
Na versao 0.6.2, o caminho Windows e experimental e requer
`PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED=true`.

## Norma de Acionamento pela IA

Esta secao incorpora e atualiza as regras operacionais do antigo protocolo de
`prosseguir_tarefas.py`. Ela se aplica tanto ao Linux quanto ao Windows.

### Pre-condicoes obrigatorias

A IA somente deve executar `ai-presence continue` quando **todas** estas
condicoes forem verdadeiras:

1. O usuario habilitou a automacao de tarefas na bandeja/CLI ou autorizou uma
   unica execucao com `--authorize-once`.
2. A etapa limitada da sessao atual foi concluida e existe uma proxima tarefa
   concreta, documentada e executavel pelo mesmo AI-worker.
3. A proxima tarefa nao depende de resposta, aprovacao, credencial, arquivo ou
   decisao ainda pendente do usuario.
4. Nao existe erro bloqueante, teste critico falhando sem diagnostico, estado
   inconsistente ou operacao destrutiva aguardando revisao.
5. A sessao seguinte ainda faz parte do trabalho autorizado e esta dentro do
   periodo em que o usuario permitiu a automacao.
6. O transporte nativo aponta para uma sessao Codex exata; no fallback GUI, o
   titulo ou ID identifica exatamente uma janela visivel.
7. Nao existe outra execucao de `continue` pendente para o mesmo worker e o
   mesmo alvo.
8. Quando a sincronizacao estiver ativa, o worker existe e permanece `active`
   porque o trabalho completo ainda nao terminou.

Uma "proxima tarefa concreta" deve estar registrada no plano, `TASKS.md`, issue
ou instrucao atual. A mera possibilidade de encontrar trabalho adicional nao e
suficiente.

### Situacoes em que e proibido executar

A IA nao deve executar `continue`:

- para simular presenca, evitar alertas ou manter artificialmente o Protocolo 2
  ativo sem trabalho correspondente;
- quando o usuario pediu pausa, cancelamento, revisao ou apenas um relatorio;
- enquanto houver pergunta pendente ou quando a resposta puder alterar a
  proxima tarefa;
- depois de concluir todo o trabalho autorizado ou registrar `finish`;
- para encadear sessoes indefinidamente sem tarefas previamente identificadas;
- quando o alvo nativo estiver indefinido; no fallback GUI, quando a tela
  estiver bloqueada, indisponivel ou a janela for ambigua;
- como retry automatico depois de qualquer envio com resultado incerto;
- para substituir `start`, `heartbeat`, `touch`, hooks ou `finish`.

Se qualquer condicao mudar durante o delay, o alvo deve falhar fechado. A IA
nao deve contornar a falha escolhendo outra sessao, a janela ativa, a primeira
janela da lista ou coordenadas globais.

### Sequencia normativa

Quando as pre-condicoes forem satisfeitas, a IA deve:

1. concluir e validar a etapa atual;
2. registrar o proximo passo concreto no plano ou controle de tarefas;
3. confirmar que nao ha pergunta nem bloqueio pendente;
4. usar `--dry-run` no primeiro uso, depois de alterar titulo/ID ou depois de
   mudar de sistema operacional;
5. iniciar uma unica execucao com worker, projeto, transporte e alvo
   especificos;
6. confirmar que o processo foi iniciado e que o log possui destino conhecido;
7. encerrar a sessao atual sem aguardar o fim do delay;
8. na sessao seguinte, verificar o status e os hooks antes de considerar que o
   Codex retomou o trabalho.

`dispatch_started` confirma apenas que o processo destacado foi criado.
`input_emitted` confirma que uma execucao sincrona do transporte terminou com
sucesso. Nenhum dos dois estados prova processamento: a retomada deve ser
confirmada por hook posterior, resultado visivel ou nova evidencia de trabalho.
Resultado incerto exige inspecao, nao reenvio.

Um hook isolado comprova atividade posterior da sessao, nao a autoria de uma
mensagem especifica. Para atribuir um E2E ao transporte, siga o protocolo com
marcador exclusivo em [USO-COMO-FERRAMENTA.md](USO-COMO-FERRAMENTA.md).

### Relacao com os protocolos de presenca

No Protocolo 1, `continue` nunca substitui o heartbeat publico. No Protocolo 2,
somente uma emissao sincrona bem-sucedida pode reiniciar temporariamente
`last_activity_at`. Um despacho destacado nao atualiza o relogio: o hook
posterior registra a atividade real. Se nao houver atividade posterior, os
alertas devem retornar normalmente.

O AI-worker deve permanecer `active` entre sessoes somente quando continua
responsavel por uma cadeia autorizada de tarefas. Quando a cadeia terminar, a
IA deve executar `finish` e nao agendar outro `continue`.

## Configuracao

Os defaults sao:

```env
PRESENCE_CODEX_GUI_WINDOW_TITLE=Codex
PRESENCE_CODEX_GUI_CLICK_X_RATIO=0.50
PRESENCE_CODEX_GUI_CLICK_Y_RATIO=0.90
PRESENCE_CONTINUE_MESSAGE=continue
PRESENCE_CONTINUE_DELAY_SECONDS=60
PRESENCE_CONTINUE_SYNC_ACTIVITY=true
PRESENCE_TASK_AUTOMATION_ENABLED=false
PRESENCE_NATIVE_INPUT_ENABLED=true
PRESENCE_GUI_FALLBACK_ENABLED=false
PRESENCE_CONTINUE_TRANSPORT=auto
PRESENCE_CONTINUE_DESTINATION=local
PRESENCE_CODEX_THREAD_ID=
```

`auto` prefere `codex queue`. Se `PRESENCE_CODEX_THREAD_ID` estiver vazio, o
comando real procura o `session_id` do hook mais recente do mesmo worker. O
fallback GUI so pode ser usado quando estiver habilitado.

O destino `local` e independente do endpoint remoto salvo. Para enviar ao
computador cliente, use `--destination client`; apenas informar um endpoint na
configuracao nao muda silenciosamente o destino.

`PRESENCE_CODEX_GUI_WINDOW_TITLE` e uma expressao regular. Ela precisa
corresponder a uma unica janela. Use um titulo mais especifico quando houver
mais de uma janela do Codex aberta.

O clique usa coordenadas relativas a janela:

- `0.50`: centro horizontal;
- `0.90`: 90% da altura, proximo a parte inferior.

## Primeiro teste

O teste seco valida argumentos e mostra o que seria feito. Ele nao espera, nao
acessa a GUI e nao grava o banco:

```bash
ai-presence --dry-run continue \
  --worker ID_EXATO_DO_WORKER \
  --transport native \
  --thread SESSAO_EXATA
```

Saida esperada:

```text
[dry-run:continue] worker=... atraso=60s mensagem='continue' ...
```

## Uso real

Antes de usar sincronizacao no Protocolo 2, marque a tarefa como ativa:

```bash
ai-presence start \
  --worker ID_EXATO_DO_WORKER \
  --protocol protocol2 \
  --task "nome-da-tarefa"
```

Agende o envio:

```bash
ai-presence control enable task-automation
ai-presence continue \
  --worker ID_EXATO_DO_WORKER
```

Valores temporarios podem sobrescrever o `.env`:

```bash
ai-presence continue \
  --worker ID_EXATO_DO_WORKER \
  --message "continue" \
  --delay 30 \
  --transport native \
  --thread SESSAO_EXATA
```

Para envio imediato:

```bash
ai-presence continue --delay 0 --thread SESSAO_EXATA
```

Ao enviar para a propria sessao Codex, identificada por `CODEX_SESSION_ID` ou
`CODEX_THREAD_ID`, o modo nativo usa automaticamente um processo destacado e
retorna `dispatch_started`. Isso evita que o turno atual espere pela mensagem
que somente podera ser processada depois que ele terminar.

O modo tambem pode ser escolhido explicitamente:

```bash
ai-presence continue --detach --thread SESSAO_EXATA
ai-presence send-input --detach --thread SESSAO_EXATA --message 'continue'
```

`--no-detach` e uma opcao de diagnostico para processos que nao sejam o proprio
turno de destino. Nao a use para forcar espera sincrona na sessao atual.

O alias `continue-task` executa o mesmo comando.

## Execucao em segundo plano

`--detach` destaca somente o processo `codex queue`, depois do delay. Para
encerrar o terminal atual sem cancelar a propria espera, destaque o comando
`ai-presence` inteiro:

```bash
mkdir -p "$HOME/.local/state"
setsid nohup ai-presence continue \
  --worker ID_EXATO_DO_WORKER \
  --thread SESSAO_EXATA \
  > "$HOME/.local/state/ai-presence-continue.log" 2>&1 < /dev/null &
```

No Windows PowerShell, inicie um processo separado:

```powershell
Start-Process ai-presence.exe -ArgumentList @(
  "continue", "--worker", "ID_EXATO_DO_WORKER",
  "--thread", "SESSAO_EXATA"
)
```

No modo nativo, o processo fixa a sessao antes da espera. No modo GUI, captura
a janela antes da espera e revalida o mesmo ID e titulo no momento do envio.
Fechar a janela ou mudar seu titulo causa falha fechada.

Terminais que alteram o titulo enquanto o Codex trabalha podem usar o modo
opt-in abaixo. Ele exige o ID da janela explicito e continua revalidando tanto
esse ID quanto o padrao de titulo; somente a igualdade do titulo completo e
relaxada:

```bash
ai-presence continue \
  --transport gui \
  --window-id ID_EXATO_DA_JANELA \
  --window-title 'trecho estavel do projeto' \
  --allow-title-change
```

Nao use essa opcao sem um padrao estavel e especifico para o projeto.

No Linux, o mantenedor da selecao iniciado por `xclip` tem sua saida isolada dos
pipes do comando. Isso permite que a automacao prossiga sem ficar bloqueada
enquanto o conteudo permanece disponivel na area de transferencia. No Windows,
o texto Unicode e emitido por `SendInput`; a area de transferencia nao e usada.

## Sincronizacao com o Protocolo 2

Com `PRESENCE_CONTINUE_SYNC_ACTIVITY=true`, o fluxo sincrono e:

1. a sessao exata e resolvida, ou a janela e capturada no fallback;
2. o programa aguarda o delay;
3. a mensagem e enfileirada nativamente ou o alvo GUI e revalidado;
4. o transporte informa sucesso;
5. um worker existente e `active` recebe
   `observation:automation:continue`;
6. `last_activity_at` e atualizado;
7. um hook posterior registra a atividade seguinte do Codex.

A observacao de automacao reinicia a contagem 5/10/15 minutos do Protocolo 2.
Isso evita um alerta de inatividade imediatamente depois do envio. Se o Codex
nao produzir hook, `touch` ou outra atividade depois, os alertas retornam
normalmente a partir do novo horario.

O sistema nao trata a automacao como prova de qualidade ou conclusao do
trabalho. O evento informa que a entrada foi emitida; o hook posterior informa
que houve atividade subsequente.

No despacho destacado, o fluxo termina inicialmente em `dispatch_started` e
nao executa os passos 5 e 6. O processo pode ainda falhar depois da criacao, e
por isso o monitor nao antecipa atividade. Se a mensagem for processada, o hook
posterior atualiza `last_activity_at` pela origem normal `codex:*`.

## Comportamento no Protocolo 1

O evento de automacao preserva `last_signal_at`. Assim, executar `continue` nao
substitui o heartbeat publico esperado pelo Protocolo 1.

## Situacoes que nao atualizam atividade

- iniciar ou agendar o comando;
- executar `--dry-run`;
- obter apenas `dispatch_started` de um processo destacado;
- cancelar durante a espera;
- nao encontrar a sessao nativa;
- falhar o Codex CLI ou o endpoint remoto;
- no fallback, nao encontrar uma janela unica ou detectar mudanca do alvo;
- no fallback, falhar clipboard, mouse ou teclado;
- indicar worker inexistente;
- indicar worker `idle`;
- passar `--no-sync-activity`.

Se a entrada for emitida, mas o worker nao puder ser sincronizado, a CLI informa
`input_emitted`, escreve o motivo no erro padrao e retorna codigo diferente de
zero. O texto nao e reenviado automaticamente.

## Descobrir o worker

Liste os workers:

```bash
ai-presence status
```

Use o ID completo mostrado na primeira coluna. Isso e especialmente importante
com escopo `project`, `session` ou `project-session`.

Tambem e possivel omitir `--worker` e deixar a CLI derivar a identidade. Nesse
caso, execute `start` e `continue` no mesmo diretorio de projeto e com os mesmos
argumentos de escopo.

## Desativar sincronizacao

Para uma execucao:

```bash
ai-presence continue --no-sync-activity --window-title 'Codex'
```

Como default:

```env
PRESENCE_CONTINUE_SYNC_ACTIVITY=false
```

Nesse modo, o envio ocorre, mas nenhum relogio do monitor e atualizado.

## Menu interativo

Execute:

```bash
ai-presence-interactive
```

Escolha `18. Agendar e enviar continue ao Codex`. O menu solicita worker,
mensagem, atraso, titulo, ID opcional e sincronizacao.

## Seguranca

- O programa nunca escolhe a primeira janela de uma lista ambigua.
- A entrada nativa exige uma sessao exata e usa `subprocess` sem shell.
- A propria sessao e despachada sem bloquear o turno nem antecipar atividade.
- O texto nao passa por shell.
- No Linux, o clipboard anterior e restaurado.
- No Windows, a digitacao Unicode nao altera o clipboard.
- O alvo e revalidado depois do delay.
- Nao existe retry automatico depois de resultado incerto.
- Revise visualmente o primeiro teste real.

## Evidencia E2E historica do fallback GUI

Em 2026-09-11, uma execucao autorizada validou o fluxo instalado no Linux X11:

1. o dry-run confirmou mensagem `continue`, delay de 60 segundos, worker e
   sincronizacao;
2. o padrao `^ChatGPT$` correspondeu a uma unica janela visivel;
3. a execucao real terminou com `input_emitted` e atividade sincronizada;
4. `continue` apareceu como nova entrada na tarefa do Codex;
5. o banco registrou `observation:automation:continue` as `00:25:44` e o hook
   `observation:codex:UserPromptSubmit` as `00:25:45` no mesmo worker.

Essa verificacao confirma o fallback GUI anterior e o processamento inicial
daquela execucao, sem ampliar a autorizacao para execucoes futuras.

## Tentativa E2E inconclusiva do transporte nativo

Em 2026-09-11, outra autorizacao explicita permitiu uma tentativa de mensagem
`continue`, com delay zero, para a sessao local
`019f5691-c118-7370-a205-94cfde0a93d7`:

1. o dry-run confirmou destino, sessao, mensagem e transporte nativo;
2. a chamada sincrona expirou depois de 15 segundos e nao foi repetida;
3. uma mensagem `continue` apareceu e o SQLite registrou hooks posteriores;
4. o usuario esclareceu que ele proprio havia digitado essa mensagem.

A mensagem e os hooks provam somente atividade manual, nao entrega pela fila.
Logo, o E2E nativo permanece pendente. O timeout sustenta o diagnostico de
bloqueio sincrono da propria sessao, e a versao 0.6.1 continua evitando essa
espera ao retornar `dispatch_started`, mas um novo teste precisa de autorizacao
e marcador exclusivo.

No proximo E2E, use texto como `[AI-PRESENCE-E2E:<id>] continue`. Durante a
janela do teste, o usuario usa `prossiga` para mensagens manuais e nao digita o
marcador. Somente a aparicao do texto exato, combinada com hook posterior da
mesma sessao, pode confirmar processamento. Hook isolado nao identifica a
origem da mensagem.

## Rollback

Desative apenas a sincronizacao:

```env
PRESENCE_CONTINUE_SYNC_ACTIVITY=false
```

Desative a autorizacao persistente e os transportes:

```bash
ai-presence control disable task-automation
ai-presence control disable native-input
ai-presence control disable gui-fallback
```

Ou deixe de executar `continue`. O monitor, os hooks, o banco e os protocolos
continuam funcionando sem esse comando. Para rollback completo de pacote,
consulte [rollback/ROLLBACK.md](rollback/ROLLBACK.md).
