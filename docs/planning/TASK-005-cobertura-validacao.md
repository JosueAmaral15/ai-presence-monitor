# Planejamento Solo: Cobertura e Revalidacao

## 1. Objetivo

Elevar a cobertura automatizada total do AI Presence Monitor de 61% para pelo
menos 80%, cobrindo fluxos operacionais e casos de erro ainda pouco exercitados.

## 2. Prioridades

1. CLI: registro, status, monitor, instaladores e tratamento de erro.
2. Menu interativo: leitura/escrita do `.env`, prompts e roteamento do menu.
3. Notificadores: Discord/Telegram, escalonamento vermelho e erros de rede.
4. Casos de borda de configuracao, identidade, protocolos e systemd.

## 3. Criterios de Aceite

- [x] Cobertura total, sem omissoes, maior ou igual a 80%.
- [x] Testes nao fazem chamadas externas reais.
- [x] Matriz Python 3.10, 3.11 e 3.12 passa.
- [x] `ruff check` e `mypy` passam.
- [x] Wheel reconstruido e instalado no ambiente dedicado.
- [x] Hooks, banco e unidade systemd continuam validos.

## 4. Riscos

**Testes acoplados a detalhes internos**: priorizar saidas, estado SQLite,
arquivos gerados e chamadas de integracao observaveis.

**Efeitos externos**: usar `TemporaryDirectory`, `--dry-run` e mocks de rede e
processo. Nao enviar Discord/Telegram nem disparar alarmes.

**Cobertura artificial**: nao excluir CLI ou menu da medicao final.

## 5. Validacao

```bash
python3.12 -m coverage run --source=ai_presence_monitor -m unittest discover -s tests
python3.12 -m coverage report --fail-under=80
./scripts/test-python-matrix.sh
ruff check ai_presence_monitor hooks tests main.py
mypy ai_presence_monitor
```

## 6. Rollback

Os novos arquivos sao testes e documentacao. Se um teste for instavel, remover
somente o caso instavel e manter as correcoes de produto que ele tiver revelado.
