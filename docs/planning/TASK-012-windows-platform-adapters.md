# Planejamento: Task 012 - Adaptadores operacionais para Windows

## TL;DR

O nucleo do monitor ja funciona em qualquer Python suportado, mas o alarme
controlado, a automacao GUI e a execucao continua ainda dependem de Linux. Esta
tarefa adiciona uma familia Windows concreta e usa Abstract Factory somente na
fronteira de plataforma. Protocolos, SQLite, hooks e notificacoes nao mudam.

## 1. Problema

O launcher `ai-presence.exe` existe no Windows, mas isso nao representa
equivalencia operacional:

- `continue` e respostas remotas instanciam diretamente o dispatcher X11;
- o alarme recusa plataformas sem `/proc` e depende de GNU `timeout`;
- o processo continuo possui somente gerador systemd;
- a CI roda apenas em Ubuntu.

## 2. Escopo aprovado

### Incluido

1. Abstract Factory para criar produtos coerentes da plataforma atual.
2. Dispatcher Win32 com API nativa via `ctypes`, sem dependencia de shell.
3. Backend de processo Windows para alarme limitado e interrompivel.
4. Task Scheduler para monitor e observer de respostas no logon do usuario.
5. Comandos CLI portateis, mantendo os comandos systemd existentes.
6. Testes unitarios simulados e job real em `windows-latest`.
7. Documentacao de instalacao, uso, seguranca e rollback.

### Nao incluido

- suporte a macOS;
- suporte Wayland;
- servico do Windows executado como `LocalSystem`;
- instalador MSI ou privilegios administrativos;
- automacao de janelas em outra sessao de usuario ou tela bloqueada.

## 3. Arquitetura

```text
casos de uso / CLI
        |
        v
PlatformIntegrationFactory
        |
        +-- LinuxPlatformFactory
        |      +-- X11GuiAnswerDispatcher
        |      +-- LinuxAlarmProcessBackend
        |      `-- SystemdBackgroundService
        |
        `-- WindowsPlatformFactory
               +-- Win32GuiAnswerDispatcher
               +-- WindowsAlarmProcessBackend
               `-- WindowsTaskSchedulerService
```

Os casos de uso dependem de protocolos estreitos. Imports nativos Windows ficam
isolados e so sao inicializados nessa plataforma.

## 4. Comportamento Windows

### GUI

- enumera apenas janelas superiores visiveis;
- aplica o padrao de titulo como expressao regular;
- exige exatamente uma correspondencia, ou um identificador explicito valido;
- revalida identificador e titulo imediatamente antes do envio;
- restaura uma janela minimizada e tenta traze-la ao primeiro plano;
- calcula o clique dentro do retangulo da janela;
- digita Unicode com `SendInput` e pressiona Enter, sem executar o texto como
  comando e sem substituir o clipboard do usuario.

### Alarme

- interpreta a linha de comando com `CommandLineToArgvW`;
- inicia um runner Python dedicado em novo grupo de processo;
- o runner encerra toda a arvore no limite configurado;
- o controlador registra PID, horario nativo de criacao e fingerprint do
  executavel, reduzindo risco de encerrar um PID reutilizado;
- `ai-presence stop-alarm` solicita parada da arvore e usa fallback forcado.

### Execucao continua

- registra tarefas por usuario, sem elevacao, com `schtasks.exe`;
- cria tarefas separadas para `monitor` e `observe-replies`;
- executa no logon e reinicia em falhas limitadas;
- guarda apenas caminhos para Python e `.env`, nunca o conteudo secreto;
- a desinstalacao remove somente a tarefa administrada pelo projeto.

## 5. Compatibilidade

- `install-systemd-service` e comandos relacionados permanecem disponiveis;
- novos comandos portateis escolhem a plataforma automaticamente;
- configuracao e schema SQLite nao mudam;
- formatos de pergunta, worker e alertas permanecem compativeis;
- a raiz continua com `README.md` em ingles e `README.pt-BR.md` em portugues.

## 6. Testes

1. Factory seleciona Linux/Windows e rejeita plataforma desconhecida.
2. Dispatcher Win32 trata janela unica, ambiguidade, titulo alterado, Unicode e
   falha de foreground usando API simulada.
3. Backend Windows valida identidade e monta runner sem shell.
4. Runner encerra processo no prazo e reage a parada.
5. Task Scheduler monta comandos sem segredos, instala/remove idempotentemente
   e falha com mensagem util quando `schtasks` nao existe.
6. Casos de uso usam a factory por padrao e continuam aceitando doubles.
7. Suite completa, cobertura >= 80%, Ruff, mypy, build e `git diff --check`.
8. GitHub Actions em Ubuntu e Windows.

## 7. Riscos

### Restricao de foreground do Windows

O Windows pode negar `SetForegroundWindow` quando outra aplicacao possui o foco
ou a sessao esta bloqueada. O dispatcher falha fechado e nao digita em outra
janela. O usuario deve manter a sessao desbloqueada.

### Task Scheduler e sessao grafica

O monitor nao precisa de desktop. O observer com entrega GUI precisa rodar na
sessao interativa do usuario. A tarefa usa logon interativo e privilegio
limitado; nao usa `SYSTEM`.

### Arvore de processos do alarme

No Windows, a parada usa `taskkill /T` sobre o runner dedicado. A identidade do
runner e revalidada antes da chamada. Nenhum processo e localizado apenas pelo
nome do player.

## 8. Rollback

1. Interromper alarme: `ai-presence stop-alarm`.
2. Remover tarefas Windows pelos novos comandos de desinstalacao.
3. Reinstalar o wheel anterior ou voltar ao commit anterior.
4. O `.env` e o banco nao precisam ser restaurados, pois nao ha migracao.
5. No Linux, as unidades systemd existentes permanecem intactas.

## 9. Checkpoints

- [x] Auditoria do acoplamento Linux concluida.
- [x] Escopo e rollback documentados.
- [x] Contratos e factories implementados.
- [x] Adaptadores Windows implementados.
- [x] CLI e menu integrados.
- [ ] Testes e CI multiplataforma aprovados.
- [x] Documentacao final atualizada.
