# Bandeja do Sistema e Entrada Nativa do Codex

## Resultado

A versao 0.6.0 oferece duas formas de enviar texto ao Codex:

1. **entrada nativa**, por `codex queue`, sem mover mouse, usar teclado ou
   alterar clipboard;
2. **fallback GUI**, pelos adaptadores X11 ou Win32 existentes, somente quando
   estiver explicitamente habilitado.

A entrada nativa e a opcao recomendada. O Codex CLI instalado precisa expor o
comando `queue`. Na versao local `0.154.0`, ele recebe um UUID ou nome exato de
sessao e tambem pode se conectar a um app-server remoto.

`app-server`, `remote-control` e seus formatos ainda aparecem como recursos
experimentais no proprio Codex CLI. Atualizacoes do Codex podem mudar esse
contrato; execute os testes secos depois de atualizar o CLI.

## O Que Acontece Sem Mouse e Teclado

O fluxo local e:

```text
usuario, bandeja ou AI-worker
            |
            v
ai-presence -> codex queue --thread SESSAO --message TEXTO
            |
            v
fila da sessao Codex -> proximo hook confirma processamento
```

O texto e passado como um item de uma lista de argumentos a `subprocess`, com
`shell=False` implícito. Ele nao e digitado na janela e nao e interpretado por
Bash, PowerShell ou `cmd.exe`.

Uma saida `input_emitted` significa que o Codex CLI aceitou o comando. O hook
posterior da mesma sessao continua sendo a confirmacao de que o agente iniciou
o processamento. Timeout ou erro nao produz retry automatico nem troca de
transporte.

## Instalar a Bandeja

O toolkit grafico e opcional para que servidores e instalacoes somente CLI nao
recebam uma dependencia grande:

```bash
python -m pip install '/caminho/para/ai-presence-monitor[tray]'
```

Durante desenvolvimento no checkout:

```bash
python -m pip install -e '.[dev,tray]'
```

Verifique a integracao sem manter um icone aberto:

```bash
ai-presence tray --check
```

Inicie a bandeja:

```bash
ai-presence tray
```

O entrypoint dedicado e equivalente:

```bash
ai-presence-tray
```

O processo precisa permanecer em execucao. **Exit** encerra somente o processo
da bandeja; monitor, hooks e observer de respostas continuam independentes.

## Menu da Bandeja

O menu de contexto possui os tres comandos solicitados:

- **Enable task automation**: habilita ou desabilita a autorizacao persistente
  para o procedimento `continue`;
- **Respond to message...**: abre o compositor e permite escolher este
  computador ou o computador cliente;
- **Exit**: remove o icone e encerra a bandeja.

Um clique simples no icone abre as preferencias.

## Preferencias e Checkboxes

As preferencias oferecem:

- **Enable task automation**: permite que `ai-presence continue` seja acionado
  por um AI-worker que cumpra a norma de continuidade;
- **Enable native Codex input**: libera `codex queue`;
- **Allow mouse and keyboard fallback**: libera X11/Win32 somente quando o modo
  selecionado precisar de GUI;
- **Allow input on a client computer**: libera o destino remoto configurado;
- **Synchronize successful continue as activity**: permite atualizar
  `last_activity_at` depois de uma emissao bem-sucedida.

Os campos de destino sao:

- **Codex session**: seletor editavel com tarefa, worker e sessoes vistas pelos
  hooks; tambem aceita UUID ou nome exato digitado;
- **Client endpoint**: endereco `ws://`, `wss://` ou `unix://` do app-server;
- **Token variable**: nome da variavel de ambiente que contem o bearer token.

O valor do token nao e exibido nem salvo pela bandeja.

## Controle Equivalente pela CLI

Consultar o estado:

```bash
ai-presence control
ai-presence control show --json
```

Habilitar e desabilitar recursos:

```bash
ai-presence control enable task-automation
ai-presence control disable task-automation
ai-presence control enable native-input
ai-presence control disable gui-fallback
ai-presence control enable remote-input
ai-presence control enable activity-sync
```

Definir o alvo local:

```bash
ai-presence control target --thread SESSAO_EXATA
```

Definir o computador cliente:

```bash
ai-presence control target \
  --thread SESSAO_EXATA \
  --remote 'wss://cliente.exemplo/app-server' \
  --remote-auth-token-env CODEX_REMOTE_AUTH_TOKEN
```

Remover alvos persistidos:

```bash
ai-presence control target --clear-thread --clear-remote
```

## Enviar uma Mensagem

Teste seco local:

```bash
ai-presence --dry-run send-input \
  --thread SESSAO_EXATA \
  --message 'continue'
```

Envio local real:

```bash
ai-presence send-input --message 'Resposta para o agente'
```

Envio ao computador cliente:

```bash
ai-presence send-input \
  --destination client \
  --message 'Resposta para o agente'
```

`send-input` exige entrada nativa habilitada. O destino cliente tambem exige
`remote-input`, endpoint, nome da variavel e valor do token no ambiente.

## Automacao de `continue`

Habilitar a automacao nao inicia um timer. Isso registra uma autorizacao para
que um AI-worker execute o procedimento quando houver uma proxima tarefa
concreta, sem pergunta ou bloqueio pendente:

```bash
ai-presence control enable task-automation
ai-presence --dry-run continue \
  --project /caminho/absoluto/do/projeto
ai-presence continue \
  --project /caminho/absoluto/do/projeto
```

Quando a autorizacao persistente estiver desligada, uma acao humana isolada
pode usar:

```bash
ai-presence continue --authorize-once --project /caminho/absoluto/do/projeto
```

`auto` prefere entrada nativa. Se a sessao nao estiver configurada, `continue`
tenta obter o ultimo `session_id` observado por hook **do mesmo worker**. A GUI
so sera selecionada se o fallback estiver habilitado. Para forcar uma escolha:

```bash
ai-presence continue --transport native --thread SESSAO_EXATA
ai-presence continue --transport gui --window-title '^Codex$'
```

Consulte a [norma completa de acionamento](CONTINUE-CODEX.md).

## Computador Cliente

O AI Presence Monitor e cliente do app-server; ele nao publica nem administra
automaticamente o servidor Codex remoto. No computador de destino:

1. confirme `codex app-server --help` e `codex queue --help`;
2. configure o app-server com autenticacao para listener nao local;
3. prefira `wss://` por TLS ou um tunel seguro;
4. mantenha o token em arquivo/secret store no servidor e em uma variavel de
   ambiente no cliente;
5. restrinja firewall e rede ao usuario/computador autorizado;
6. valide primeiro com uma sessao descartavel e uma mensagem inofensiva.

Nunca exponha `ws://0.0.0.0:PORTA` sem autenticacao. O modo remoto do Codex e
experimental e precisa ser revalidado apos cada atualizacao.

## Arquivo de Controle

Por padrao, o estado fica fora do checkout, na area de estado do usuario. No
Linux, normalmente sera:

```text
~/.local/state/ai-presence-monitor/control.json
```

No Windows, normalmente fica sob:

```text
%LOCALAPPDATA%\ai-presence-monitor\control.json
```

O arquivo e gravado por substituicao atomica e recebe modo `600` em sistemas
POSIX. Ele contem flags, sessao, endpoint e **nome** da variavel de token, mas
nunca o token. Depois que ele existe, seus valores substituem os defaults do
`.env`. Para voltar aos defaults, encerre a bandeja e remova somente
`control.json`.

Defina `PRESENCE_CONTROL_PATH` apenas para substituir esse local. Um caminho
relativo explicito e resolvido a partir do diretorio do `.env`.

## Limites

- A bandeja precisa de sessao grafica com system tray disponivel.
- Ela nao e iniciada automaticamente no login nesta versao.
- O envio nativo depende do comando experimental `codex queue` instalado no
  mesmo computador que executa `ai-presence`.
- O texto segue em `--message` para o processo Codex e pode aparecer
  temporariamente em ferramentas locais de inspecao; nao envie segredos.
- O compositor manual nao correlaciona a mensagem com uma pergunta Discord;
  o observer Discord continua sendo o fluxo correlacionado.
- Ferramentas genericas de LLM podem chegar ao mesmo resultado por function
  calling ou MCP, invocando a CLI como ferramenta autorizada; nao precisam
  simular um cursor.
