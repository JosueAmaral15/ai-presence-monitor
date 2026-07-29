from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .codex_hook import run_from_stdin as run_codex_hook_from_stdin
from .codex_hook_installer import (
    install_codex_hook,
    print_result as print_hook_install_result,
    uninstall_codex_hook,
)
from .config import AppConfig, load_config
from .continue_task import ContinueTaskError, execute_continue_task
from .identity import WORKER_SCOPES, scoped_worker_id
from .notify import NotificationError, Notifier
from .protocols import PROTOCOLS, choose_threshold, format_duration, get_protocol, should_escalate
from .remote_questions import (
    RemoteQuestionError,
    ask_remote_question,
    observe_discord_replies_once,
    retry_gui_dispatch,
)
from .store import PresenceStore, WorkerState
from .systemd_service import (
    install_reply_observer_service,
    install_user_service,
    print_result as print_systemd_result,
    uninstall_reply_observer_service,
    uninstall_user_service,
)
from .work_window import get_work_window_status


DEFAULT_EVENT_MESSAGES = {
    "start": "tarefa iniciada",
    "heartbeat": "continuo trabalhando",
    "touch": "atividade interna registrada",
    "finish": "tarefa concluida",
}


def _timestamp(value: float | None) -> str:
    if value is None:
        return "sem registro"
    return datetime.fromtimestamp(value).isoformat(timespec="seconds")


def _clock_value(worker: WorkerState) -> tuple[str, float | None]:
    protocol = get_protocol(worker.protocol)
    if protocol.monitored_clock == "last_signal_at":
        return protocol.monitored_clock, worker.last_signal_at
    return protocol.monitored_clock, worker.last_activity_at or worker.last_signal_at


def _should_send_alert(worker: WorkerState, threshold_level: str, config: AppConfig, now: float) -> bool:
    if should_escalate(worker.last_alert_level, threshold_level):
        return True

    if not config.alert_repeat_enabled:
        return False
    if threshold_level not in config.alert_repeat_levels:
        return False
    if worker.last_alert_level != threshold_level:
        return False
    if worker.last_alert_at is None:
        return False

    return now - worker.last_alert_at >= config.alert_repeat_seconds


def _identity(args: argparse.Namespace, config: AppConfig) -> tuple[str, str, str, str]:
    computer = args.computer or config.computer_name
    ia_name = args.ai or "codex"
    explicit_worker = getattr(args, "worker", None)
    if explicit_worker:
        worker_id = explicit_worker
    else:
        base_worker_id = config.codex_worker_id or f"{computer}:{ia_name}"
        worker_id = scoped_worker_id(
            base_worker_id,
            getattr(args, "scope", None) or config.codex_worker_scope,
            project_path=getattr(args, "project", None) or Path.cwd(),
            session_id=getattr(args, "session", None),
        )
    protocol = args.protocol or config.default_protocol
    get_protocol(protocol)
    return worker_id, computer, ia_name, protocol


def _record_event(args: argparse.Namespace, config: AppConfig, event_type: str) -> int:
    worker_id, computer, ia_name, protocol = _identity(args, config)
    message = args.message or DEFAULT_EVENT_MESSAGES[event_type]
    store = PresenceStore(config.db_path)
    worker = store.record_event(
        worker_id=worker_id,
        computer=computer,
        ia_name=ia_name,
        protocol=protocol,
        event_type=event_type,
        message=message,
        task=args.task,
    )

    should_notify = event_type != "touch" or getattr(args, "notify", False)
    if should_notify:
        try:
            Notifier(config, dry_run=args.dry_run).send_point(event_type, worker, message)
        except NotificationError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    print(
        f"{event_type}: worker={worker.worker_id} protocolo={worker.protocol} "
        f"status={worker.status} db={config.db_path}"
    )
    return 0


def _check_once(config: AppConfig, dry_run: bool = False, now: float | None = None) -> int:
    store = PresenceStore(config.db_path)
    notifier = Notifier(config, dry_run=dry_run)
    now = time.time() if now is None else now
    alerts_sent = 0
    window_status = get_work_window_status(config, now)

    if not window_status.alerts_allowed:
        local_hour = window_status.local_now.isoformat(timespec="minutes")
        print(f"monitor: {window_status.reason}; alertas suprimidos. agora={local_hour}")
        return 0

    for worker in store.list_workers(only_active=True):
        protocol = get_protocol(worker.protocol)
        clock_name, clock_time = _clock_value(worker)
        if clock_time is None:
            continue

        age_seconds = now - clock_time
        threshold = choose_threshold(protocol, age_seconds)
        if threshold is None:
            continue

        is_escalation = should_escalate(worker.last_alert_level, threshold.level)
        if not _should_send_alert(worker, threshold.level, config, now):
            continue

        try:
            notifier.send_alert(
                worker=worker,
                protocol=protocol,
                threshold=threshold,
                age_seconds=age_seconds,
                clock_name=clock_name,
                trigger_red_escalation=is_escalation,
            )
        except NotificationError as exc:
            print(str(exc), file=sys.stderr)
            continue

        store.record_alert(
            worker_id=worker.worker_id,
            protocol=worker.protocol,
            level=threshold.level,
            signal_age_seconds=age_seconds,
            triggered_at=now,
        )
        alerts_sent += 1
        print(
            f"alerta={threshold.level} worker={worker.worker_id} "
            f"idade={format_duration(age_seconds)}"
        )

    if alerts_sent == 0:
        print("monitor: nenhum alerta novo.")
    return alerts_sent


def _run_monitor(args: argparse.Namespace, config: AppConfig) -> int:
    interval = args.interval or config.monitor_interval_seconds
    while True:
        _check_once(config, dry_run=args.dry_run)
        if args.once:
            return 0
        time.sleep(interval)


def _run_codex_hook(args: argparse.Namespace, config: AppConfig) -> int:
    return run_codex_hook_from_stdin(
        config=config,
        stdin_text=sys.stdin.read(),
        dry_run=args.dry_run,
        quiet=not args.verbose,
        fail_closed=args.fail_closed or None,
        auto_start=True if args.auto_start else False if args.no_auto_start else None,
    )


def _ask_user(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    timeout = (
        config.question_timeout_seconds
        if args.timeout is None
        else args.timeout
    )
    if timeout <= 0:
        raise ValueError("O prazo da pergunta precisa ser maior que zero.")
    if args.dry_run:
        print(
            f"[dry-run:pergunta] worker={worker_id} prazo={timeout}s "
            f"gui={'ativa' if config.gui_answer_enabled else 'inativa'} "
            f"texto={args.question!r}"
        )
        return 0

    store = PresenceStore(config.db_path)
    try:
        question = ask_remote_question(
            config=config,
            store=store,
            worker_id=worker_id,
            prompt=args.question,
            timeout_seconds=timeout,
            window_id=args.window_id,
            title_pattern=args.window_title,
        )
    except RemoteQuestionError as exc:
        print(f"Falha ao publicar pergunta: {exc}", file=sys.stderr)
        return 2

    print(
        f"pergunta={question.question_id} status={question.status} "
        f"discord_message={question.external_message_id} worker={question.worker_id}"
    )
    return 0


def _observe_replies_once(config: AppConfig, dry_run: bool = False) -> int:
    if dry_run:
        print("[dry-run:respostas] rede, banco e GUI nao foram acessados.")
        return 0
    try:
        result = observe_discord_replies_once(
            config=config,
            store=PresenceStore(config.db_path),
        )
    except RemoteQuestionError as exc:
        print(f"Falha no observer de respostas: {exc}", file=sys.stderr)
        return 2
    print(
        f"respostas: lidas={result.fetched} aceitas={result.accepted} "
        f"entregues={result.dispatched} falhas_gui={result.dispatch_failed}"
    )
    return 0


def _run_reply_observer(args: argparse.Namespace, config: AppConfig) -> int:
    interval = args.interval or config.question_poll_interval_seconds
    if interval <= 0:
        raise ValueError("O intervalo do observer precisa ser maior que zero.")
    while True:
        result = _observe_replies_once(config, dry_run=args.dry_run)
        if result != 0 or args.once or args.dry_run:
            return result
        time.sleep(interval)


def _show_questions(args: argparse.Namespace, config: AppConfig) -> int:
    store = PresenceStore(config.db_path)
    store.expire_questions()
    questions = store.list_questions(status=args.status, limit=args.limit)
    if not questions:
        print(f"Nenhuma pergunta registrada em {config.db_path}.")
        return 0

    for question in questions:
        answer = "-"
        if question.answer:
            answer = question.answer.replace("\n", " ")[:120]
        error = "-"
        if question.last_error:
            error = question.last_error.replace("\n", " ")[:120]
        print(
            f"{question.question_id} | {question.status} | worker={question.worker_id} | "
            f"criada={_timestamp(question.created_at)} | "
            f"expira={_timestamp(question.expires_at)} | "
            f"discord={question.external_message_id or '-'} | "
            f"autor={question.answered_by or '-'} | resposta={answer!r} | erro={error!r}"
        )
    return 0


def _dispatch_answer(args: argparse.Namespace, config: AppConfig) -> int:
    if args.dry_run:
        print(
            f"[dry-run:entrega-gui] pergunta={args.question_id}; "
            "mouse, teclado e banco nao foram alterados."
        )
        return 0
    try:
        question = retry_gui_dispatch(
            config=config,
            store=PresenceStore(config.db_path),
            question_id=args.question_id,
        )
    except (RemoteQuestionError, ValueError) as exc:
        print(f"Falha na entrega GUI: {exc}", file=sys.stderr)
        return 2
    print(f"pergunta={question.question_id} status={question.status}")
    return 0


def _continue_task(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    try:
        result = execute_continue_task(
            config=config,
            worker_id=worker_id,
            message=args.message,
            delay_seconds=args.delay,
            window_id=args.window_id,
            title_pattern=args.window_title,
            sync_activity=args.sync_activity,
            dry_run=args.dry_run,
        )
    except ContinueTaskError as exc:
        print(f"Falha ao executar continue: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        sync = (
            config.continue_sync_activity
            if args.sync_activity is None
            else args.sync_activity
        )
        print(
            f"[dry-run:continue] worker={worker_id} "
            f"atraso={result.delay_seconds}s mensagem={result.message!r} "
            f"sincronizar_atividade={str(sync).lower()}; "
            "espera, GUI e banco nao foram acessados."
        )
        return 0

    assert result.target is not None
    print(
        f"continue: input_emitted janela={result.target.window_id} "
        f"worker={worker_id}"
    )
    if result.activity_synced:
        print(
            "continue: atividade sincronizada "
            f"worker={worker_id} origem=automation:continue"
        )
        return 0
    if result.sync_reason == "disabled":
        print("continue: sincronizacao de atividade desativada.")
        return 0

    print(
        "continue: entrada emitida, mas a atividade nao foi sincronizada; "
        f"motivo={result.sync_reason}.",
        file=sys.stderr,
    )
    return 2


def _install_codex_hook(args: argparse.Namespace, config: AppConfig) -> int:
    result = install_codex_hook(
        target_path=args.target,
        env_file=config.env_path,
        hook_script=args.hook_script,
        python_executable=args.python,
        timeout=args.timeout,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print_hook_install_result(result, dry_run=args.dry_run)
    return 0


def _uninstall_codex_hook(args: argparse.Namespace, config: AppConfig) -> int:
    result = uninstall_codex_hook(
        target_path=args.target,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print_hook_install_result(result, dry_run=args.dry_run)
    return 0


def _install_systemd_service(args: argparse.Namespace, config: AppConfig) -> int:
    result = install_user_service(
        env_file=config.env_path,
        target_path=args.target,
        python_executable=args.python,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print_systemd_result(result, dry_run=args.dry_run)
    if not args.dry_run and result.changed:
        print("Execute: systemctl --user daemon-reload")
        print("Execute: systemctl --user enable --now ai-presence-monitor.service")
    return 0


def _uninstall_systemd_service(args: argparse.Namespace, config: AppConfig) -> int:
    result = uninstall_user_service(
        target_path=args.target,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print_systemd_result(result, dry_run=args.dry_run)
    if not args.dry_run and result.changed:
        print("Execute: systemctl --user daemon-reload")
    return 0


def _install_reply_observer_service(
    args: argparse.Namespace,
    config: AppConfig,
) -> int:
    result = install_reply_observer_service(
        env_file=config.env_path,
        target_path=args.target,
        python_executable=args.python,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print_systemd_result(result, dry_run=args.dry_run)
    if not args.dry_run and result.changed:
        print("Execute: systemctl --user daemon-reload")
        print(
            "Execute: systemctl --user enable --now "
            "ai-presence-reply-observer.service"
        )
    return 0


def _uninstall_reply_observer_service(
    args: argparse.Namespace,
    config: AppConfig,
) -> int:
    result = uninstall_reply_observer_service(
        target_path=args.target,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
    print_systemd_result(result, dry_run=args.dry_run)
    if not args.dry_run and result.changed:
        print("Execute: systemctl --user daemon-reload")
    return 0


def _show_status(config: AppConfig) -> int:
    store = PresenceStore(config.db_path)
    now = time.time()
    workers = store.list_workers()
    if not workers:
        print(f"Nenhum worker registrado em {config.db_path}.")
        return 0

    for worker in workers:
        clock_name, clock_time = _clock_value(worker)
        age = None if clock_time is None else now - clock_time
        print(
            f"{worker.worker_id} | {worker.status} | {worker.protocol} | "
            f"computador={worker.computer} | ia={worker.ia_name} | "
            f"tarefa={worker.current_task or '-'} | "
            f"{clock_name}={_timestamp(clock_time)} | idade={format_duration(age)} | "
            f"ultimo_alerta={worker.last_alert_level or '-'} | "
            f"ultimo_alerta_em={_timestamp(worker.last_alert_at)}"
        )
    return 0


def _show_protocols() -> int:
    for protocol in PROTOCOLS.values():
        print(f"{protocol.protocol_id}: {protocol.title}")
        print(f"  {protocol.description}")
        for threshold in protocol.thresholds:
            print(f"  - {threshold.color_name}: depois de {format_duration(threshold.after_seconds)}")
    return 0


def _add_identity_args(
    parser: argparse.ArgumentParser,
    *,
    include_task_message: bool = True,
) -> None:
    parser.add_argument(
        "--worker",
        help="ID exato do worker; quando informado, ignora a derivacao por escopo.",
    )
    parser.add_argument("--computer", help="Nome do computador. Padrao: hostname ou .env.")
    parser.add_argument("--ai", help="Nome da IA/agente. Padrao: codex.")
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), help="Protocolo de monitoramento.")
    parser.add_argument(
        "--scope",
        choices=WORKER_SCOPES,
        help="Escopo do worker. Padrao: PRESENCE_CODEX_WORKER_SCOPE.",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Diretorio do projeto usado na identidade. Padrao: diretorio atual.",
    )
    parser.add_argument("--session", help="ID de sessao para escopos que usam sessao.")
    if include_task_message:
        parser.add_argument("--task", help="Nome ou ID da tarefa/algoritmo atual.")
        parser.add_argument("--message", help="Mensagem descritiva para o registro.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor de presenca artificial com alertas Discord/Telegram."
    )
    parser.add_argument(
        "--env-file",
        help="Arquivo .env. Padrao: arquivo dedicado do projeto ou configuracao do usuario.",
    )
    parser.add_argument("--db", help="Caminho do banco SQLite. Sobrescreve PRESENCE_DB_PATH.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra notificacoes sem enviar.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Cria/valida o banco local.")
    init_parser.set_defaults(func=lambda args, config: _init_db(config))

    protocols_parser = subparsers.add_parser("protocols", help="Lista os protocolos disponiveis.")
    protocols_parser.set_defaults(func=lambda args, config: _show_protocols())

    start_parser = subparsers.add_parser("start", help="Registra inicio de tarefa.")
    _add_identity_args(start_parser)
    start_parser.set_defaults(func=lambda args, config: _record_event(args, config, "start"))

    heartbeat_parser = subparsers.add_parser("heartbeat", help="Registra ponto de atividade.")
    _add_identity_args(heartbeat_parser)
    heartbeat_parser.set_defaults(func=lambda args, config: _record_event(args, config, "heartbeat"))

    touch_parser = subparsers.add_parser(
        "touch",
        help="Registra atividade silenciosa, util no protocolo 2.",
    )
    _add_identity_args(touch_parser)
    touch_parser.add_argument("--notify", action="store_true", help="Tambem posta no canal de ponto.")
    touch_parser.set_defaults(func=lambda args, config: _record_event(args, config, "touch"))

    finish_parser = subparsers.add_parser("finish", help="Registra fim de tarefa.")
    _add_identity_args(finish_parser)
    finish_parser.set_defaults(func=lambda args, config: _record_event(args, config, "finish"))

    monitor_parser = subparsers.add_parser("monitor", help="Monitora atrasos e envia alertas.")
    monitor_parser.add_argument("--once", action="store_true", help="Executa uma verificacao e sai.")
    monitor_parser.add_argument("--interval", type=int, help="Intervalo do loop em segundos.")
    monitor_parser.set_defaults(func=lambda args, config: _run_monitor(args, config))

    ask_parser = subparsers.add_parser(
        "ask-user",
        help="Publica uma pergunta no Discord e aguarda resposta correlacionada.",
    )
    _add_identity_args(ask_parser)
    ask_parser.add_argument("--question", required=True, help="Pergunta enviada ao usuario.")
    ask_parser.add_argument("--timeout", type=int, help="Prazo da pergunta em segundos.")
    ask_parser.add_argument(
        "--window-id",
        help="ID X11 exato. Se omitido, exige um unico titulo correspondente.",
    )
    ask_parser.add_argument(
        "--window-title",
        help="Padrao de titulo da janela; sobrescreve PRESENCE_CODEX_GUI_WINDOW_TITLE.",
    )
    ask_parser.set_defaults(func=lambda args, config: _ask_user(args, config))

    replies_parser = subparsers.add_parser(
        "observe-replies",
        help="Observa respostas autorizadas no canal de perguntas do Discord.",
    )
    replies_parser.add_argument("--once", action="store_true", help="Consulta uma vez e sai.")
    replies_parser.add_argument("--interval", type=int, help="Intervalo do polling em segundos.")
    replies_parser.set_defaults(func=lambda args, config: _run_reply_observer(args, config))

    questions_parser = subparsers.add_parser(
        "questions",
        help="Lista perguntas e estados de entrega.",
    )
    questions_parser.add_argument("--status", help="Filtra por estado exato.")
    questions_parser.add_argument("--limit", type=int, default=50, help="Quantidade maxima.")
    questions_parser.set_defaults(func=lambda args, config: _show_questions(args, config))

    dispatch_parser = subparsers.add_parser(
        "dispatch-answer",
        help="Reenvia manualmente uma resposta apos revisar uma falha GUI.",
    )
    dispatch_parser.add_argument("question_id", help="ID local da pergunta.")
    dispatch_parser.set_defaults(func=lambda args, config: _dispatch_answer(args, config))

    continue_parser = subparsers.add_parser(
        "continue-task",
        aliases=["continue"],
        help="Agenda e envia uma mensagem de continuidade ao Codex GUI.",
    )
    _add_identity_args(continue_parser, include_task_message=False)
    continue_parser.add_argument(
        "--message",
        help="Texto enviado. Padrao: PRESENCE_CONTINUE_MESSAGE ou 'continue'.",
    )
    continue_parser.add_argument(
        "--delay",
        type=int,
        help="Atraso em segundos. Padrao: PRESENCE_CONTINUE_DELAY_SECONDS ou 60.",
    )
    continue_parser.add_argument(
        "--window-id",
        help="ID X11 exato. Se omitido, exige um unico titulo correspondente.",
    )
    continue_parser.add_argument(
        "--window-title",
        help="Padrao de titulo; sobrescreve PRESENCE_CODEX_GUI_WINDOW_TITLE.",
    )
    continue_parser.add_argument(
        "--sync-activity",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Sincroniza a emissao bem-sucedida com um worker ativo. "
            "Padrao: PRESENCE_CONTINUE_SYNC_ACTIVITY."
        ),
    )
    continue_parser.set_defaults(
        func=lambda args, config: _continue_task(args, config)
    )

    hook_parser = subparsers.add_parser(
        "codex-hook",
        help="Recebe JSON de hook do Codex e registra atividade observada.",
    )
    hook_parser.add_argument("--verbose", action="store_true", help="Mostra resultado do hook.")
    hook_parser.add_argument(
        "--fail-closed",
        action="store_true",
        help="Retorna erro se nao conseguir registrar atividade.",
    )
    hook_parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Cria ou reativa worker automaticamente a partir do hook.",
    )
    hook_parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Nao cria nem reativa worker automaticamente a partir do hook.",
    )
    hook_parser.set_defaults(func=lambda args, config: _run_codex_hook(args, config))

    install_hook_parser = subparsers.add_parser(
        "install-codex-hook",
        help="Instala hooks do AI Presence Monitor em hooks.json do Codex.",
    )
    install_hook_parser.add_argument("--target", type=Path, help="Caminho do hooks.json.")
    install_hook_parser.add_argument("--hook-script", type=Path, help="Script de hook.")
    install_hook_parser.add_argument(
        "--python",
        help="Executavel Python. Padrao: o mesmo Python desta instalacao.",
    )
    install_hook_parser.add_argument("--timeout", type=int, default=5, help="Timeout do hook.")
    install_hook_parser.add_argument("--no-backup", action="store_true", help="Nao cria backup.")
    install_hook_parser.set_defaults(func=lambda args, config: _install_codex_hook(args, config))

    uninstall_hook_parser = subparsers.add_parser(
        "uninstall-codex-hook",
        help="Remove hooks do AI Presence Monitor de hooks.json do Codex.",
    )
    uninstall_hook_parser.add_argument("--target", type=Path, help="Caminho do hooks.json.")
    uninstall_hook_parser.add_argument("--no-backup", action="store_true", help="Nao cria backup.")
    uninstall_hook_parser.set_defaults(func=lambda args, config: _uninstall_codex_hook(args, config))

    install_service_parser = subparsers.add_parser(
        "install-systemd-service",
        help="Gera o servico systemd de usuario para o monitor continuo.",
    )
    install_service_parser.add_argument("--target", type=Path, help="Caminho do arquivo .service.")
    install_service_parser.add_argument(
        "--python",
        help="Executavel Python. Padrao: o mesmo Python desta instalacao.",
    )
    install_service_parser.add_argument("--no-backup", action="store_true", help="Nao cria backup.")
    install_service_parser.set_defaults(
        func=lambda args, config: _install_systemd_service(args, config)
    )

    uninstall_service_parser = subparsers.add_parser(
        "uninstall-systemd-service",
        help="Remove o arquivo de servico systemd de usuario.",
    )
    uninstall_service_parser.add_argument("--target", type=Path, help="Caminho do arquivo .service.")
    uninstall_service_parser.add_argument("--no-backup", action="store_true", help="Nao cria backup.")
    uninstall_service_parser.set_defaults(
        func=lambda args, config: _uninstall_systemd_service(args, config)
    )

    install_reply_service_parser = subparsers.add_parser(
        "install-reply-observer-service",
        help="Gera o servico systemd do observer continuo de respostas.",
    )
    install_reply_service_parser.add_argument(
        "--target",
        type=Path,
        help="Caminho do arquivo .service.",
    )
    install_reply_service_parser.add_argument(
        "--python",
        help="Executavel Python. Padrao: o mesmo Python desta instalacao.",
    )
    install_reply_service_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Nao cria backup.",
    )
    install_reply_service_parser.set_defaults(
        func=lambda args, config: _install_reply_observer_service(args, config)
    )

    uninstall_reply_service_parser = subparsers.add_parser(
        "uninstall-reply-observer-service",
        help="Remove o servico systemd do observer de respostas.",
    )
    uninstall_reply_service_parser.add_argument(
        "--target",
        type=Path,
        help="Caminho do arquivo .service.",
    )
    uninstall_reply_service_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Nao cria backup.",
    )
    uninstall_reply_service_parser.set_defaults(
        func=lambda args, config: _uninstall_reply_observer_service(args, config)
    )

    status_parser = subparsers.add_parser("status", help="Mostra estado dos workers.")
    status_parser.set_defaults(func=lambda args, config: _show_status(config))

    return parser


def _init_db(config: AppConfig) -> int:
    PresenceStore(config.db_path)
    print(f"Banco pronto: {config.db_path}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.env_file)
        if args.db:
            config = replace(config, db_path=Path(args.db).expanduser())
        raise_code = args.func(args, config)
    except (ValueError, KeyboardInterrupt) as exc:
        print(str(exc), file=sys.stderr)
        raise_code = 1
    raise SystemExit(raise_code)
