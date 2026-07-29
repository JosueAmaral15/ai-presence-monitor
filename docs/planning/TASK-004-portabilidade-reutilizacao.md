# Planejamento Solo: Portabilidade e Reutilizacao

## 1. Objetivo

Transformar o AI Presence Monitor em um pacote Python instalavel e reutilizavel
em outros projetos e computadores, sem depender do caminho atual do codigo-fonte.

## 2. Criterios de Aceite

- [x] `pip wheel` gera um wheel valido.
- [x] O wheel instalado executa os comandos de CLI.
- [x] A configuracao segue uma ordem previsivel: argumento, variavel de ambiente,
      `.env` local existente e configuracao do usuario.
- [x] Caminhos relativos do banco sao resolvidos a partir do diretorio do `.env`.
- [x] O instalador do hook usa o mesmo Python do pacote instalado.
- [x] Hooks antigos baseados em `codex_presence_hook.py` continuam removiveis.
- [x] O worker pode ser isolado por projeto e, opcionalmente, por sessao.
- [x] O modo global atual continua disponivel para compatibilidade.
- [x] A CLI gera um servico systemd de usuario sem caminhos fixos da maquina.
- [x] Documentacao, seguranca e rollback refletem o fluxo portatil.

## 3. Decisoes

- Manter Python 3.10+ e somente biblioteca padrao.
- Nao alterar o esquema SQLite para preservar o banco existente.
- Usar `project` como escopo recomendado, mas manter `global` como padrao de
  compatibilidade no codigo.
- Derivar projeto pelo `cwd` do hook ou pelo diretorio atual da CLI.
- Usar identificadores legiveis e uma parte curta de hash do caminho para evitar
  colisao entre projetos com o mesmo nome.
- Gerar arquivos operacionais por comandos idempotentes, sempre com backup antes
  de substituir um arquivo existente.

## 4. Implementacao

1. Corrigir descoberta de pacote no `pyproject.toml`.
2. Centralizar resolucao de configuracao e identidade.
3. Atualizar CLI e observer do Codex.
4. Tornar instalador de hooks independente do checkout.
5. Criar instalador/desinstalador de servico systemd de usuario.
6. Atualizar exemplos e documentacao.
7. Construir wheel, instalar em diretorio isolado e executar smoke tests.

## 5. Riscos e Mitigacoes

**Worker antigo deixar de receber observacoes**: manter escopo `global` como
fallback e documentar a migracao para `project`.

**Hook parar apos mover o codigo**: gerar comando com o Python absoluto e
`-m ai_presence_monitor.codex_hook`.

**Sobrescrever configuracao do Codex ou systemd**: preservar entradas externas,
criar backup e oferecer `--dry-run` ou desinstalador.

**Banco aparecer no diretorio errado**: resolver caminho relativo a partir do
arquivo `.env` efetivamente selecionado.

## 6. Validacao

- `python3 -m compileall -q ai_presence_monitor hooks tests main.py`
- `python3 -m unittest discover -s tests -v`
- `python3 -m pip wheel --no-deps --no-build-isolation`
- instalar wheel em diretorio temporario e executar `ai-presence protocols`
- testar instalacao idempotente e rollback de hooks/systemd em diretorios temporarios

## 7. Rollback

Os hooks antigos permanecem reconhecidos. Para voltar ao comportamento anterior:

1. definir `PRESENCE_CODEX_WORKER_SCOPE=global`;
2. executar `ai-presence install-codex-hook` para regenerar os hooks;
3. desinstalar o servico com `ai-presence uninstall-systemd-service`, se usado;
4. continuar usando diretamente `python3 -m ai_presence_monitor` no checkout.
