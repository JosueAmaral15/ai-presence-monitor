# Auditoria de Base - Task 007

**Data**: 2026-07-29
**Branch**: `COM-e776b5f7-30fd-43cb-9d44-cd2f6c1cf7d0`
**Baseline**: `4f0b71b`

## Escopo confirmado

- Nenhum outro AI-worker atua nesta tarefa.
- O usuario autorizou criar a linha de base Git local e a branch de trabalho.
- O resultado deve ser um unico projeto executavel: `ai-presence-monitor`.
- O comportamento aproveitado de `mouse-control-clicker` e somente o envio
  programado de texto ao prompt do Codex GUI.
- O `.env` real nao sera alterado durante a reorganizacao.

## Protocolo aplicado

O arquivo `PROTOCOLO_SIMPLICIDADE_3.md` foi lido integralmente, com 12.124
linhas. SHA-256:

```text
a1277d18ccacbbc1c911069d3e83485f4713a688814e16412196c298f51c22a4
```

Esta fase se limitou a inventario, leitura, medicao e registro. Nenhum arquivo
de codigo, banco, hook ou configuracao operacional foi alterado.

## Inventario do monitor

O projeto possui um pacote Python plano em `ai_presence_monitor/`, 16 modulos,
10 arquivos de testes, CLI, menu interativo, wrappers, exemplos e documentacao.
O `pyproject.toml` empacota explicitamente `ai_presence_monitor` e declara
Python 3.10 ou superior, sem dependencias Python de runtime.

Arquivos acima de 500 linhas:

| Arquivo | Linhas | Observacao |
|---|---:|---|
| `interactive.py` | 815 | configuracao, prompts, adaptadores e menu |
| `store.py` | 719 | estado de presenca e perguntas remotas |
| `cli.py` | 670 | comandos, regras operacionais e parser |

O grafo de importacoes internas nao possui ciclos. `config` recebe sete
importacoes internas e `store` recebe cinco; sao os principais modulos
compartilhados. A migracao deve preservar essa direcao e impedir que a camada
de dominio passe a depender da CLI ou do menu.

## Inventario do projeto de continuidade

`mouse-control-clicker/prosseguir_tarefas.py` implementa:

- mensagem padrao `continue`;
- atraso padrao de 60 segundos;
- busca de janela por titulo com `xdotool`;
- clique em 50% da largura e 92% da altura;
- fallback global por `pyautogui`.

O projeto tambem contem uma macro Gmail em `main.py`, fora do escopo da
unificacao. Seu ambiente Poetry traz `pyautogui`, `keyboard`, Pillow e uma
arvore extensa de dependencias de GUI. Essa arvore nao e necessaria no monitor.

Problemas que nao devem ser importados:

- escolha silenciosa da primeira janela quando ha mais de uma correspondencia;
- titulo padrao ligado a um projeto especifico;
- fallback global que pode clicar em outra aplicacao;
- duas automacoes sem relacao no mesmo projeto;
- ausencia de testes automatizados.

## Componente reutilizavel

`X11GuiAnswerDispatcher` ja exige uma unica janela visivel, valida ID e titulo,
calcula clique relativo, preserva o clipboard e envia texto sem shell. O novo
comando deve reutilizar essa infraestrutura por uma API de entrada textual
generica, mantendo a resposta remota e o comando `continue` como casos de uso
separados.

Uma emissao local de clique, colagem e Enter prova apenas `input_emitted`.
Confirmacao de entrega continua dependendo de evento posterior do hook ou
inspecao visual.

## Estado operacional medido

- 62 testes passaram em Python 3.12.
- Cobertura total: 86%, acima do gate de 80%.
- `ruff check`: aprovado.
- `mypy`: aprovado em 16 modulos.
- Compilacao bytecode: aprovada.
- `pip check` no ambiente dedicado: aprovado.
- SQLite: `integrity_check=ok`, com 1 worker, 17 eventos e 0 alertas.
- Servico do monitor: desabilitado e inativo.
- Servico do observer de respostas: ausente e inativo.
- Cinco hooks do Codex apontam para o ambiente dedicado e para a configuracao
  central.
- `xdotool` e `xclip` estao instalados.

## Organizacao encontrada

Artefatos gerados ocupam a raiz local: `.mypy_cache/`, `.ruff_cache/`,
`__pycache__/`, `build/`, `dist/`, `*.egg-info`, `.coverage` e `presence.db`.
Eles ja estao fora do commit, salvo caches ainda nao cobertos pelo
`.gitignore`.

Tambem foram encontrados:

- `assets/alarm-four2.mp3`, sem referencia no codigo e ausente do wheel;
- diretorios vazios `docs/security/` e `docs/rollback/`;
- documentos de seguranca e rollback diretamente em `docs/`;
- nenhum `LICENSE`;
- nenhum remote Git configurado.

Nenhum artefato sera apagado nesta tarefa sem aprovacao explicita. A
organizacao pode corrigir ignore, caminhos de fonte e documentos sem remover
dados locais.

## Riscos da proxima fase

1. Mover o pacote para `src/` pode quebrar importacoes feitas diretamente do
   checkout, wrappers, cobertura, hooks e a instalacao editavel.
2. Separar arquivos grandes pode ampliar o escopo e introduzir regressao sem
   ganho direto para a unificacao.
3. Reutilizar o dispatcher sem generaliza-lo pode forcar uma dependencia
   artificial de `RemoteQuestion`.
4. Um envio em segundo plano pode sobreviver ao terminal e agir quando o alvo
   ja mudou; o alvo deve ser capturado e revalidado.
5. Alterar o `.env` enquanto ele esta sendo preenchido pode perder dados.

## Direcao recomendada para planejamento

- Migrar o pacote para `src/ai_presence_monitor/` em uma operacao mecanica.
- Corrigir `pyproject.toml`, testes, cobertura, wrappers e hook de
  compatibilidade.
- Extrair uma operacao generica de envio X11 a partir do dispatcher atual.
- Criar comando `continue-task` com mensagem `continue`, atraso de 60 segundos,
  titulo configurado ou informado, clique 50%/90% e `--dry-run`.
- Adicionar a mesma operacao ao menu interativo.
- Manter o fallback global por coordenadas fora do escopo inicial.
- Preservar banco, configuracao central, identidade de worker e esquema SQLite.
- Adiar a divisao ampla de `cli.py`, `interactive.py` e `store.py`; registrar
  essa divida e dividir apenas quando uma fronteira funcional concreta exigir.
- Validar no checkout, no wheel e em instalacao isolada antes de regenerar hooks.

## Rollback da reorganizacao

O rollback de codigo e retornar ao commit `4f0b71b` em uma nova branch ou
reinstalar o wheel 0.3.0 ja existente. O `.env`, o SQLite e os hooks nao fazem
parte da migracao inicial. A retirada do projeto `mouse-control-clicker` fica
fora desta fase e depende de aprovacao posterior.
