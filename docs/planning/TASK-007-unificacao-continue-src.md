# Planejamento: Unificacao do Continue e Layout `src/`

**Task**: 007
**Data**: 2026-07-29
**Prioridade**: Alta
**Branch**: `COM-e776b5f7-30fd-43cb-9d44-cd2f6c1cf7d0`

## 1. Objetivo

Transformar o AI Presence Monitor no unico projeto necessario para:

- monitorar workers pelos Protocolos 1 e 2;
- observar atividade do Codex;
- enviar perguntas e respostas remotas;
- agendar e emitir a mensagem `continue` no Codex GUI;
- sincronizar a emissao bem-sucedida com a atividade monitorada.

O projeto `mouse-control-clicker` permanece intacto ate a validacao final e uma
decisao explicita sobre arquivamento ou retirada.

## 2. Contrato do comando

A CLI oferecera:

```text
ai-presence continue-task
ai-presence continue
```

Padroes:

| Campo | Padrao |
|---|---|
| mensagem | `continue` |
| atraso | 60 segundos |
| posicao horizontal | 0.50 |
| posicao vertical | 0.90 |
| sincronizar atividade | ativo |

O titulo da janela deve vir de `--window-title` ou
`PRESENCE_CODEX_GUI_WINDOW_TITLE`. Nao havera titulo especifico de projeto nem
fallback para coordenada global da tela.

Fluxo:

1. Derivar ou receber o ID exato do worker.
2. Validar mensagem, atraso, proporcoes e titulo.
3. Em `--dry-run`, apenas exibir o plano e encerrar.
4. Capturar exatamente uma janela X11.
5. Aguardar o atraso configurado.
6. Revalidar o mesmo ID e titulo.
7. Ativar a janela, clicar, colar a mensagem e pressionar Enter.
8. Restaurar o clipboard.
9. Sincronizar atividade somente depois do passo 7 bem-sucedido.
10. Informar separadamente emissao e sincronizacao.

## 3. Regra contra falsos positivos

O envio de `continue` produz duas evidencias diferentes:

- `input_emitted`: o computador emitiu clique, texto e Enter;
- hook posterior: o Codex produziu um novo evento observado.

Para evitar que o Protocolo 2 alerte imediatamente enquanto o Codex recebe e
processa a entrada, a emissao bem-sucedida registra uma observacao local com
origem `automation:continue`. Essa observacao:

- exige worker existente e `active`;
- atualiza `last_activity_at`;
- limpa o nivel de alerta anterior como as demais observacoes;
- preserva `last_signal_at`;
- aparece na tabela `events`;
- inicia uma nova janela normal de 5/10/15 minutos no Protocolo 2.

Se nenhum hook ou outra atividade ocorrer depois, o monitor volta a alertar
normalmente quando a nova janela expirar. Assim, a automacao concede somente o
tempo correspondente a uma atividade real observada; ela nao mantem a IA ativa
indefinidamente.

No Protocolo 1, a observacao preserva `last_signal_at`. Portanto, o comando nao
substitui o heartbeat publico esperado a cada cinco minutos.

Nao sincronizam atividade:

- iniciar o comando;
- iniciar a contagem regressiva;
- `--dry-run`;
- cancelar com `Ctrl+C`;
- alvo ausente ou ambiguo;
- falha no clipboard, clique, colagem ou Enter;
- worker inexistente ou `idle`;
- uso explicito de `--no-sync-activity`.

## 4. Estrutura de destino

```text
ai-presence-monitor/
|-- src/
|   `-- ai_presence_monitor/
|       |-- continue_task.py
|       |-- gui_answer.py
|       `-- ...
|-- tests/
|-- docs/
|   |-- audits/
|   |-- planning/
|   |-- rollback/
|   `-- security/
|-- hooks/
|-- scripts/
|-- examples/
|-- assets/
|-- pyproject.toml
|-- README.md
|-- history-chat.md
|-- main.py
|-- run_interactive.sh
`-- run_interactive.bat
```

O pacote sera descoberto por `setuptools` dentro de `src/`. O wrapper
`main.py`, o hook de compatibilidade e a matriz de testes receberao caminhos
explicitos para preservar a execucao local e impedir importacao acidental de
artefatos antigos.

## 5. Alteracoes de codigo

### `gui_answer.py`

Extrair uma operacao generica `dispatch_text(target, text)`. O metodo atual de
resposta remota continuara adaptando `RemoteQuestion` para essa operacao.

### `continue_task.py`

Criar o caso de uso de continuidade:

- validacao;
- captura do alvo;
- contagem regressiva;
- emissao;
- sincronizacao com `PresenceStore`;
- resultado estruturado para CLI e testes.

### `config.py`

Adicionar, com defaults compativeis:

```env
PRESENCE_CONTINUE_MESSAGE=continue
PRESENCE_CONTINUE_DELAY_SECONDS=60
PRESENCE_CONTINUE_SYNC_ACTIVITY=true
```

O `.env` real nao sera modificado.

### `cli.py` e `interactive.py`

Adicionar o subcomando e uma opcao no menu. A CLI aceitara:

```text
--message
--delay
--window-id
--window-title
--sync-activity / --no-sync-activity
```

Os argumentos existentes de identidade permitirao sincronizar o worker correto.

### `store.py`

Reutilizar `record_observation` com worker ativo e `auto_start=false`. Nenhuma
tabela ou migracao nova e necessaria.

## 6. Escopo de organizacao

Incluido:

- migracao mecanica do pacote para `src/`;
- correcao de imports e entrypoints;
- melhoria do `.gitignore`;
- indice de documentacao;
- posicionamento dos documentos de seguranca e rollback;
- atualizacao dos comandos de teste e build;
- gate local reproduzivel.

Adiado com justificativa:

- divisao ampla de `cli.py`, `interactive.py` e `store.py`;
- suporte Wayland, Windows e macOS para entrada GUI;
- remocao de artefatos locais;
- remocao do projeto antigo;
- troca do polling Discord por Gateway;
- integracao nativa com memoria interna do Codex.

Os tres arquivos grandes possuem fronteiras imperfeitas, mas uma divisao ampla
durante a migracao de layout aumentaria simultaneamente o risco funcional e o
risco de importacao. O novo caso de uso sera isolado em modulo proprio, e a
divida restante sera registrada.

## 7. Testes obrigatorios

Testes unitarios:

- defaults de mensagem, atraso e sincronizacao;
- mensagem vazia e atraso negativo;
- `dry-run` sem GUI, banco ou espera;
- alvo ausente e alvo ambiguo;
- revalidacao do mesmo ID e titulo depois do atraso;
- clipboard restaurado;
- emissao falha sem atualizar atividade;
- worker ativo no Protocolo 2 atualiza `last_activity_at`;
- worker ausente ou `idle` nao e reativado;
- Protocolo 1 preserva `last_signal_at`;
- `--no-sync-activity` preserva os dois relogios;
- menu e parser encaminham os argumentos.

Validacao:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src coverage run -m unittest discover -s tests
coverage report --fail-under=80
ruff check src hooks tests main.py
mypy src/ai_presence_monitor
./scripts/test-python-matrix.sh
python3 -m build
```

O wheel sera instalado em ambiente temporario. Os entrypoints, `continue
--dry-run`, hooks e uma copia do SQLite serao exercitados.

## 8. Seguranca

- Entrada GUI continua restrita a X11, `xdotool` e `xclip`.
- Nenhum texto passa por shell.
- Nenhuma janela e escolhida por ordem ou foco.
- O alvo capturado e revalidado apos o atraso.
- `--dry-run` nao espera, nao acessa GUI e nao grava SQLite.
- A sincronizacao nao cria nem reativa workers.
- O evento diferencia automacao de atividade posterior do Codex.
- Segredos permanecem fora do Git e da documentacao.

## 9. Rollback

Antes da validacao instalada:

```text
git switch main
```

Para uso operacional, reinstalar o wheel 0.3.0 preservado e regenerar os hooks:

```text
pip install --force-reinstall dist/ai_presence_monitor-0.3.0-py3-none-any.whl
ai-presence install-codex-hook
```

O esquema SQLite nao muda. O `.env` atual continua valido porque os novos
campos possuem defaults internos.

## 10. Criterio de conclusao

A Task 007 so sera concluida quando:

- a CLI e o menu usarem o recurso integrado;
- o pacote instalado funcionar fora do checkout;
- o comportamento de sincronizacao estiver coberto por testes;
- o gate total permanecer acima de 80%;
- Python 3.10, 3.11 e 3.12 passarem;
- hooks e copia do banco forem revalidados;
- a documentacao explicar limites e falsos positivos;
- o projeto antigo nao for mais necessario para o fluxo validado.

## 11. Resultado

- 74 testes passaram em Python 3.10, 3.11 e 3.12.
- Cobertura total: 86%, acima do gate de 80%.
- `ruff`, `mypy`, compilacao, sintaxe Bash e links locais passaram.
- Wheel e sdist 0.4.0 foram construidos e inspecionados.
- SHA-256 do wheel:
  `543477a9218aaff6578aaaade0dd0c5f7b50332633f97a8649719763f4ea9968`.
- O wheel foi instalado em ambiente limpo fora do checkout.
- Todos os entrypoints e `continue --dry-run` passaram.
- Uma copia do banco preservou 1 worker, 17 eventos, 0 alertas, 0 perguntas e
  0 estados de observer, com `integrity_check=ok`.
- O ambiente dedicado foi atualizado de 0.3.0 para 0.4.0.
- Os cinco tipos de evento do hook passaram em dry-run.
- O hash do banco real permaneceu
  `54abee65b1af8a076f1929a8b60479ab50c494fff74bc26eb764ddf6eb8e1f94`.
- Monitor e observer de respostas permaneceram inativos.
- O `.env` e o arquivo de hooks nao foram modificados.

O teste real de clique, colagem e Enter nao foi repetido nesta fase, pois atua
na GUI. O caminho foi coberto por testes de subprocesso simulados e o primeiro
uso real deve permanecer visualmente supervisionado.
