# Continue Integrado para o Codex

## Objetivo

O AI Presence Monitor pode aguardar um intervalo, localizar uma unica janela
visivel do Codex, clicar no prompt, escrever uma mensagem e pressionar Enter. A
mensagem padrao e `continue` e o atraso padrao e 60 segundos.

Esse recurso substitui o uso separado de `prosseguir_tarefas.py` no fluxo
monitorado.

## Requisitos

- pacote AI Presence Monitor instalado;
- titulo que identifique exatamente uma janela visivel do Codex.

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

## Norma de Acionamento pela IA

Esta secao incorpora e atualiza as regras operacionais do antigo protocolo de
`prosseguir_tarefas.py`. Ela se aplica tanto ao Linux quanto ao Windows.

### Pre-condicoes obrigatorias

A IA somente deve executar `ai-presence continue` quando **todas** estas
condicoes forem verdadeiras:

1. O usuario autorizou explicitamente a automacao GUI para essa execucao.
2. A etapa limitada da sessao atual foi concluida e existe uma proxima tarefa
   concreta, documentada e executavel pelo mesmo AI-worker.
3. A proxima tarefa nao depende de resposta, aprovacao, credencial, arquivo ou
   decisao ainda pendente do usuario.
4. Nao existe erro bloqueante, teste critico falhando sem diagnostico, estado
   inconsistente ou operacao destrutiva aguardando revisao.
5. A sessao seguinte ainda faz parte do trabalho autorizado e esta dentro do
   periodo em que o usuario permitiu a automacao.
6. O titulo ou ID configurado identifica exatamente uma janela visivel do
   Codex na sessao grafica atual.
7. Nao existe outra execucao de `continue` pendente para o mesmo worker e a
   mesma janela.
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
- quando a tela estiver bloqueada, a sessao grafica estiver indisponivel ou o
  alvo da janela for ambiguo;
- como retry automatico depois de clique, digitacao ou Enter com resultado
  incerto;
- para substituir `start`, `heartbeat`, `touch`, hooks ou `finish`.

Se qualquer condicao mudar durante o delay, o alvo deve falhar fechado. A IA
nao deve contornar a falha escolhendo a janela ativa, a primeira janela da
lista ou coordenadas globais.

### Sequencia normativa

Quando as pre-condicoes forem satisfeitas, a IA deve:

1. concluir e validar a etapa atual;
2. registrar o proximo passo concreto no plano ou controle de tarefas;
3. confirmar que nao ha pergunta nem bloqueio pendente;
4. usar `--dry-run` no primeiro uso, depois de alterar titulo/ID ou depois de
   mudar de sistema operacional;
5. iniciar uma unica execucao em segundo plano com worker, projeto e alvo
   especificos;
6. confirmar que o processo foi iniciado e que o log possui destino conhecido;
7. encerrar a sessao atual sem aguardar o fim do delay;
8. na sessao seguinte, verificar o status e os hooks antes de considerar que o
   Codex retomou o trabalho.

`input_emitted` confirma apenas que o sistema operacional aceitou os eventos de
entrada. A retomada deve ser confirmada por hook posterior, resultado visivel
ou nova evidencia de trabalho. Resultado incerto exige inspecao, nao reenvio.

### Relacao com os protocolos de presenca

No Protocolo 1, `continue` nunca substitui o heartbeat publico. No Protocolo 2,
a emissao bem-sucedida reinicia temporariamente `last_activity_at`, mas nao
prova execucao da tarefa. Se nao houver atividade posterior, os alertas devem
retornar normalmente.

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
```

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
  --window-title 'Codex'
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
ai-presence continue \
  --worker ID_EXATO_DO_WORKER \
  --window-title 'Codex'
```

Valores temporarios podem sobrescrever o `.env`:

```bash
ai-presence continue \
  --worker ID_EXATO_DO_WORKER \
  --message "continue" \
  --delay 30 \
  --window-title 'Codex - projeto'
```

Para envio imediato:

```bash
ai-presence continue --delay 0 --window-title 'Codex'
```

O alias `continue-task` executa o mesmo comando.

## Execucao em segundo plano

Para encerrar o terminal atual sem cancelar a espera:

```bash
mkdir -p "$HOME/.local/state"
setsid nohup ai-presence continue \
  --worker ID_EXATO_DO_WORKER \
  --window-title 'Codex' \
  > "$HOME/.local/state/ai-presence-continue.log" 2>&1 < /dev/null &
```

No Windows PowerShell, inicie um processo separado:

```powershell
Start-Process ai-presence.exe -ArgumentList @(
  "continue", "--worker", "ID_EXATO_DO_WORKER",
  "--window-title", "Codex"
)
```

O processo captura a janela antes da espera e revalida o mesmo ID e titulo no
momento do envio. Fechar a janela ou mudar seu titulo causa falha fechada.

Terminais que alteram o titulo enquanto o Codex trabalha podem usar o modo
opt-in abaixo. Ele exige o ID da janela explicito e continua revalidando tanto
esse ID quanto o padrao de titulo; somente a igualdade do titulo completo e
relaxada:

```bash
ai-presence continue \
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

Com `PRESENCE_CONTINUE_SYNC_ACTIVITY=true`, o fluxo e:

1. a janela exata e capturada;
2. o programa aguarda o delay;
3. o mesmo alvo e revalidado;
4. texto e Enter sao emitidos;
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

## Comportamento no Protocolo 1

O evento de automacao preserva `last_signal_at`. Assim, executar `continue` nao
substitui o heartbeat publico esperado pelo Protocolo 1.

## Situacoes que nao atualizam atividade

- iniciar ou agendar o comando;
- executar `--dry-run`;
- cancelar durante a espera;
- nao encontrar a janela;
- encontrar mais de uma janela;
- detectar mudanca do ID ou titulo;
- falhar ao acessar clipboard, mouse ou teclado;
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
- O texto nao passa por shell.
- No Linux, o clipboard anterior e restaurado.
- No Windows, a digitacao Unicode nao altera o clipboard.
- O alvo e revalidado depois do delay.
- Nao existe retry automatico depois de resultado incerto.
- Revise visualmente o primeiro teste real.

## Rollback

Desative apenas a sincronizacao:

```env
PRESENCE_CONTINUE_SYNC_ACTIVITY=false
```

Ou deixe de executar `continue`. O monitor, os hooks, o banco e os protocolos
continuam funcionando sem esse comando. Para rollback completo de pacote,
consulte [rollback/ROLLBACK.md](rollback/ROLLBACK.md).
