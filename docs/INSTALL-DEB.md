# Pacote Debian, Ubuntu e Linux Mint

## Escopo

O pacote `ai-presence-monitor_<versao>-1_all.deb` fornece a CLI e o codigo Python
puro para Debian 12, Ubuntu 22.04, Ubuntu 24.04 e distribuicoes compativeis,
incluindo Linux Mint 21/22. O instalador por wheel continua sendo a opcao
oficial sem privilegios administrativos.

O pacote `.deb` nao cria configuracao no diretorio pessoal, nao inicializa banco,
nao instala hooks, nao ativa servicos, nao habilita automacao e nao inicia a
bandeja. Essas operacoes permanecem explicitas por usuario.

## Verificacao

Mantenha o `.deb`, seu sidecar `.sha256` e `verify_deb.py` no mesmo diretorio:

```bash
sha256sum -c ai-presence-monitor_0.13.0-1_all.deb.sha256
python3 verify_deb.py \
  ai-presence-monitor_0.13.0-1_all.deb \
  --expected-version 0.13.0
```

O verificador inspeciona metadados, caminhos, permissoes, commit de origem,
dependencias e executa um smoke test isolado da CLI e do schema SQLite.

## Instalacao

Use o gerenciador APT para resolver a versao suportada do Python:

```bash
sudo apt install ./ai-presence-monitor_0.13.0-1_all.deb
/usr/bin/ai-presence --version
```

Se uma instalacao anterior por wheel existir em `~/.local/bin`, ela pode ter
precedencia no `PATH`. Verifique antes de operar:

```bash
command -v ai-presence
readlink -f "$(command -v ai-presence)"
```

Nao remova nem substitua a instalacao anterior ate concluir a migracao e o
rollback planejados. Para testar inequivocamente o pacote Debian, use
`/usr/bin/ai-presence`.

## Configuracao por usuario

Depois da instalacao, copie o exemplo sem sobrescrever configuracao existente:

```bash
mkdir -p "$HOME/.config/ai-presence-monitor"
install -m 600 \
  /usr/share/ai-presence-monitor/.env.example \
  "$HOME/.config/ai-presence-monitor/.env"
```

Edite o arquivo e execute:

```bash
/usr/bin/ai-presence init
/usr/bin/ai-presence doctor --strict
```

Hooks, observers e automacao continuam seguindo `INSTALL-LINUX.md` e
`USO-COMO-FERRAMENTA.md`.

## Bandeja

O pacote base e independente de toolkit grafico. A bandeja exige PySide6 para
o Python do sistema, mas os nomes e versoes dos pacotes Qt variam entre as
distribuicoes suportadas. Por isso, o `.deb` nao baixa nem incorpora PySide6 e
nao declara uma dependencia APT que seria invalida em parte da matriz.

Valide primeiro:

```bash
/usr/bin/ai-presence tray --check
```

Se a distribuicao nao fornecer PySide6 compativel, use o bundle por wheel com o
extra `tray` em ambiente virtual dedicado. Nao misture `pip` com os arquivos
controlados pelo `dpkg` em `/usr/lib/python3/dist-packages`.

## Atualizacao e remocao

Uma futura atualizacao por `.deb` usa:

```bash
sudo apt install ./ai-presence-monitor_NOVA_VERSAO_all.deb
```

O banco e a configuracao ficam no diretorio do usuario e nao pertencem ao
pacote. A remocao do programa nao os apaga:

```bash
sudo apt remove ai-presence-monitor
```

O script de remocao limpa somente diretorios `__pycache__` gerados dentro de
`/usr/lib/python3/dist-packages/ai_presence_monitor`. Ele nao consulta nem
remove `$HOME`, `.env`, banco, controles, hooks, servicos ou autostart.

Antes de remover, desative explicitamente hooks, autostart e servicos de usuario
conforme `docs/rollback/ROLLBACK.md`.

## Limites dos testes

Containers comprovam instalacao, dependencias, CLI, schema, layout e remocao.
Eles nao comprovam bandeja, desktop, systemd de usuario, Codex GUI, X11/Wayland
ou retomada apos suspensao. Esses fluxos exigem uma VM completa ou host fisico.
