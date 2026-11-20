# Primeiros Passos no Linux

Este guia leva uma pessoa que nunca utilizou o projeto desde o download ate um
worker local saudavel. Comece pelo monitoramento local. Adicione Discord,
continuacao automatica e outras integracoes somente depois que a instalacao
basica passar nos diagnosticos.

## O que o Produto Faz

O AI Presence Monitor registra quando um agente inicia, realiza atividade
significativa e termina. Ele pode avaliar protocolos de inatividade, mostrar
alertas no desktop ou Discord, receber respostas correlacionadas e, quando o
usuario habilita explicitamente, enviar um prompt a uma sessao Codex exata.

Ele nao avalia a qualidade do trabalho e nao presume que um processo aberto
esta produzindo. Entrada automatica permanece desabilitada ate o operador
habilitar os controles correspondentes.

## Escolha um Metodo de Instalacao

Use o bundle por wheel para instalacao sem `sudo`, bandeja opcional e rollback
mais simples. Esta e a recomendacao padrao.

Use o `.deb` quando quiser a CLI em `/usr/bin` e gerenciamento pelo APT. O
`.deb` nao configura sua conta, nao inicia servicos e nao instala PySide6.

Se os dois metodos existirem, descubra qual comando sera executado:

```bash
command -v ai-presence
readlink -f "$(command -v ai-presence)"
```

## Verifique o Download

No diretorio extraido da release canonica:

```bash
sha256sum -c SHA256SUMS
python3 verify_release.py .
```

Para o pacote Debian isolado, mantenha o sidecar ao lado:

```bash
sha256sum -c ai-presence-monitor_0.15.1-1_all.deb.sha256
python3 verify_deb.py \
  ai-presence-monitor_0.15.1-1_all.deb \
  --expected-version 0.15.1
```

Nao prossiga se checksum, commit de origem ou verificador offline falhar.

## Instale

### Instalacao recomendada por usuario

```bash
./install-linux.sh \
  --wheel ./ai_presence_monitor-0.15.1-py3-none-any.whl
```

### Pacote Debian, Ubuntu ou Linux Mint

```bash
sudo apt install ./ai-presence-monitor_0.15.1-1_all.deb
/usr/bin/ai-presence --version
```

Os guias do `.deb` ficam em:

```text
/usr/share/doc/ai-presence-monitor/
```

## Primeiro Diagnostico

Antes de adicionar integracoes:

```bash
ai-presence --version
ai-presence schema-status --json
ai-presence doctor --json --strict
```

Uma instalacao nova pode avisar que hooks, servicos, Codex CLI ou autostart da
bandeja nao existem, pois sao opcionais. Banco, ambiente, runtime e plataforma
nao podem apresentar erro.

## Crie ou Revise a Configuracao

O instalador por usuario cria um template privado se ainda nao existir. No
pacote Debian:

```bash
mkdir -p "$HOME/.config/ai-presence-monitor"
install -m 600 \
  /usr/share/ai-presence-monitor/.env.example \
  "$HOME/.config/ai-presence-monitor/.env"
```

Edite localmente. Nunca envie o arquivo completo em chats, nao o coloque no Git
e nao passe tokens ou webhooks como argumentos. Para uso somente local, Discord
e Telegram podem permanecer vazios.

Antes de inicializar, confirme que `PRESENCE_DB_PATH` aponta para o local
pretendido:

```bash
ai-presence init
ai-presence schema-status --json
```

## Inicie um Worker do Projeto

Dentro do projeto em que a IA trabalha:

```bash
PROJECT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"

ai-presence start \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "Descreva a tarefa atual" \
  --message "Trabalho iniciado"
```

O Protocolo 2 e o padrao recomendado para agentes de programacao. Inicio e fim
sao publicos; hooks do Codex registram atividade interna significativa.

Ao terminar:

```bash
ai-presence finish \
  --project "$PROJECT" \
  --protocol protocol2 \
  --task "Descreva a tarefa atual" \
  --message "Trabalho concluido"
```

Use sempre o caminho absoluto. Cada projeto recebe identidade e configuracoes
de automacao independentes.

## Adicione Componentes Opcionais um por Vez

Revise cada dry-run:

```bash
ai-presence --dry-run install-codex-hook
ai-presence install-codex-hook

ai-presence --dry-run install-background-service --component monitor
ai-presence install-background-service --component monitor

ai-presence --dry-run install-background-service --component reply-observer
ai-presence install-background-service --component reply-observer

ai-presence --dry-run install-background-service --component prompt-rule-observer
ai-presence install-background-service --component prompt-rule-observer
```

Depois de cada componente:

```bash
systemctl --user --no-pager status NOME_DA_UNIDADE
ai-presence doctor --json --strict
```

## Bandeja Opcional

No runtime dedicado do wheel:

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/pip" install PySide6
ai-presence tray --check
./start-tray.sh
```

Na bandeja, o ser humano habilita automacao, seleciona sessoes Codex exatas,
cria Prompt Rules e Availability Recovery e abre o chat dos agentes. Uma IA
pode desabilitar somente a automacao do proprio projeto; nao pode habilitar ou
redirecionar o perfil de outro agente.

## Discord Opcional

Use canais e webhooks separados para ponto e alertas. Perguntas remotas exigem
tambem bot de aplicacao Discord, ID do canal e lista de usuarios permitidos.
Configure uma integracao por vez, reinicie apenas o servico afetado e leia o
journal antes de habilitar entrada automatica.

## Seguranca da Entrada Automatica

Prompt Rules e Availability Recovery exigem **Enable task automation** e
**Enable native Codex input** no perfil escolhido. Selecione uma sessao exata.
O inicio do transporte e preliminar; atividade canonica posterior confirma o
processamento na sessao.

Consulte o historico sanitizado sem texto do prompt nem ID bruto da sessao:

```bash
ai-presence dispatch-audit --profile WORKER_ID --limit 20 --json
```

## Problemas Comuns

### O comando nao foi encontrado

```bash
"$HOME/.local/share/ai-presence-monitor/venv/bin/ai-presence" --version
```

Se funcionar, inclua `~/.local/bin` no `PATH` ou use o caminho absoluto.

### A instalacao errada esta sendo executada

Compare `command -v`, `readlink -f` e `/usr/bin/ai-presence --version`. Nao
remova nenhuma instalacao sem um plano de rollback.

### Um servico esta failed

```bash
systemctl --user status NOME_DA_UNIDADE --no-pager -l
journalctl --user-unit NOME_DA_UNIDADE -n 80 --no-pager
```

Nao reinicie repetidamente antes de ler a primeira falha.

### O schema e mais novo que o runtime

Nao diminua `PRAGMA user_version` e nao apague tabelas. Instale o runtime mais
novo pelo upgrade transacional ou restaure um snapshot revisado com autorizacao
explicita.

### O icone da bandeja nao aparece

Execute `ai-presence tray --check` na sessao grafica. Confirme PySide6 e leia
`journalctl --user-unit ai-presence-tray-session.service`.

### O disco esta cheio

Interrompa a release antes que SQLite ou empacotamento falhem. Identifique os
maiores caminhos e obtenha autorizacao antes de apagar caches ou arquivos
pessoais.

## Proximas Leituras

- [Instalacao Linux](INSTALL-LINUX.md)
- [Pacote Debian](INSTALL-DEB.md)
- [Configuracao do ambiente](CONFIGURANDO-ENV.md)
- [Uso por humanos e AI-workers](USO-COMO-FERRAMENTA.md)
- [Bandeja do sistema](SYSTEM-TRAY-NATIVE-INPUT.md)
- [Upgrade transacional](TRANSACTIONAL-UPGRADE.md)
- [Suporte e compatibilidade](SUPPORT.md)
