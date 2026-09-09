# Security Checklist

## Task 001 - Codex Hook Observer

### 1. Injection

- [x] Nao usa SQL dinamico com interpolacao; operacoes SQLite usam parametros.
- [x] Nao usa `eval()` ou `exec()`.
- [x] O hook nao executa comandos vindos do JSON do Codex.

### 2. Dados Sensiveis

- [x] Webhooks e tokens continuam no `.env`, que esta no `.gitignore`.
- [x] Hook nao imprime payload por padrao.
- [x] Metadata gravada deve ser curta e nao incluir transcript completo.

### 3. Controle de Acesso

- [x] O hook grava apenas no banco configurado.
- [x] Hook gerado usa Python e `.env` absolutos para evitar ambiguidade.

### 4. Configuracoes Inseguras

- [x] Sem dependencia externa nova.
- [x] Sem rede dentro do hook.
- [x] Erros recuperaveis nao interrompem Codex por padrao.

### 5. Logs/Monitoring

- [x] Eventos de observer ficam no SQLite para auditoria local.
- [x] Notificacoes continuam centralizadas no monitor.

## Limites

- A instalacao do hook em `~/.codex/hooks.json` exige confianca/revisao no Codex via `/hooks`.
- O observer prova atividade de lifecycle do Codex, nao qualidade do trabalho produzido.

## Task 003 - Janela de expediente e repeticao

- [x] Repeticao de alerta usa intervalo minimo configurado por `PRESENCE_ALERT_REPEAT_SECONDS`.
- [x] Fora do expediente, `suppress_alerts` evita novos alertas quando a janela esta ativa.
- [x] Vermelho nao repete mensagem nem escalada externa no mesmo episodio de inatividade.
- [x] Somente nova atividade valida rearma um futuro alerta vermelho.
- [x] Comandos locais continuam restritos ao valor explicito de `RED_ALERT_COMMAND` no `.env`.
- [x] Estado do alarme nao armazena o comando em texto e usa permissao `600`.
- [x] `stop-alarm` valida PID, fingerprint e inicio antes de sinalizar.
- [x] GNU `timeout` limita todo alarme local, inclusive comandos em loop.
- [x] Windows limita o alarme em runner dedicado e encerra somente sua arvore.
- [x] Windows revalida PID, horario nativo de criacao e executavel antes da parada.

## Task 004 - Portabilidade

- [x] Wheel inclui somente o pacote `ai_presence_monitor`.
- [x] Hook recebe apenas caminho de Python e `.env` definidos localmente.
- [x] Instaladores de hook e systemd criam backup antes de substituir.
- [x] Desinstalacao do systemd cria backup recuperavel antes de remover.
- [x] `.env`, banco, build e metadata de pacote ficam ignorados pelo Git.
- [x] Escopo usa hash de caminho, sem gravar conteudo dos arquivos do projeto.

## Task 006 - Respostas remotas

- [x] Recurso remoto e entrega GUI desativados por padrao.
- [x] Token do bot e webhook permanecem somente no `.env`.
- [x] Bot usa allowlist de IDs numericos.
- [x] Somente resposta com `message_reference.message_id` e aceita.
- [x] Mensagens de bot, respostas vazias e canal diferente sao ignorados.
- [x] `allowed_mentions` impede mencoes disparadas pela pergunta.
- [x] Texto da resposta nao e executado por shell.
- [x] X11 e Win32 exigem ID e titulo capturados, revalidados antes da entrega.
- [x] No Linux, o clipboard anterior e restaurado; no Windows, ele nao e usado.
- [x] Falha GUI nao causa retry automatico.
- [x] Estados e erro ficam auditaveis no SQLite.
- [x] `--dry-run` nao acessa rede, banco nem GUI nos comandos de resposta.

### Risco residual

Um usuario autorizado controla texto que sera enviado ao Codex. Conta Discord
comprometida ou allowlist incorreta pode alterar o trabalho da IA. O mecanismo
nao substitui revisao de permissoes, isolamento do canal e validacao humana para
acoes destrutivas.

## Task 007 - Continue integrado

- [x] Texto e enviado por clipboard no Linux ou `SendInput` no Windows, sem shell.
- [x] Uma unica janela deve corresponder ao titulo.
- [x] ID e titulo sao revalidados depois do delay.
- [x] No Linux, o clipboard anterior e restaurado; no Windows, ele nao e usado.
- [x] `--dry-run` nao espera, nao acessa GUI e nao grava banco.
- [x] Falha GUI nao atualiza atividade.
- [x] Sincronizacao exige worker existente e ativo.
- [x] Sincronizacao preserva `last_signal_at` do Protocolo 1.
- [x] Evento diferencia automacao de hook posterior.
- [x] Nao existe retry automatico.
- [x] Configuracao real e segredos nao foram modificados.

### Risco residual

Uma emissao bem-sucedida prova que o sistema operacional aceitou os eventos de
entrada, nao que o Codex interpretou ou executou a mensagem. Por isso a
observacao reinicia apenas a janela normal do Protocolo 2; ausencia posterior de
hooks volta a produzir alerta.

## Task 012 - Windows

- [x] Win32 e acessado por argumentos tipados de `ctypes`, sem shell.
- [x] Texto remoto e enviado como Unicode por `SendInput`, nao como comando.
- [x] Falha de foreground impede clique e digitacao.
- [x] Tarefas usam `InteractiveToken` e `LeastPrivilege`, nao `SYSTEM`.
- [x] XML do Task Scheduler guarda caminhos, nao valores secretos do `.env`.
- [x] Desinstalacao remove somente os dois nomes de tarefa administrados.
- [x] `--dry-run` nao registra tarefa, nao escreve definicao e nao usa GUI.

### Risco residual Windows

Qualquer automacao de teclado pode influenciar a aplicacao alvo. A revalidacao
reduz selecao incorreta, mas nao substitui sessao desbloqueada, titulo especifico
e revisao humana antes de comandos destrutivos. O Windows tambem pode negar
foreground; o sistema falha fechado nessa situacao.

## Task 013 - Hardening operacional do observer

- [x] Limite de reinicio e aplicado somente ao observer de respostas.
- [x] Tres falhas em cinco minutos bloqueiam uma tempestade de reinicios.
- [x] O intervalo entre tentativas sobe de cinco para 30 segundos.
- [x] O monitor principal preserva sua politica independente.
- [x] Recuperacao exige corrigir a causa e executar `reset-failed`.
- [x] Nenhum token, webhook ou conteudo do `.env` entra na unidade.

### Risco residual

O limite interrompe recuperacao automatica depois de falhas persistentes. Essa
escolha evita carga e ruido indefinidos; depois de corrigir rede, canal ou
credenciais, o operador precisa liberar e iniciar a unidade explicitamente.

## Task 014 - Orientacao para respostas Discord invalidas

- [x] Orientacao exige pergunta pendente no mesmo canal.
- [x] Somente autor humano presente na allowlist pode receber o aviso.
- [x] Mensagens de bot e webhook nao geram resposta, evitando ciclo.
- [x] Mencao usa `parse=[]` e lista explicita com somente o autor validado.
- [x] Mensagem invalida nunca e persistida como resposta nem enviada a GUI.
- [x] Cursor avanca depois de uma tentativa de aviso, inclusive em timeout
      incerto, para impedir duplicacao automatica.
- [x] Nenhum token, webhook ou conteudo invalido e incluido no log.

### Risco residual

Um usuario permitido que converse normalmente no canal dedicado enquanto
existir pergunta pendente recebera orientacao. O canal deve permanecer dedicado
ao fluxo de perguntas. Falha do webhook pode impedir um aviso; por seguranca,
o sistema nao repete uma entrega cujo resultado externo seja incerto.
