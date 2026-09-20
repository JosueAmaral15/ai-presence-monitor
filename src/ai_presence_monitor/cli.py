from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from . import __version__
from .alarm import AlarmControlError, AlarmController
from .background_service import (
    BACKGROUND_COMPONENTS,
    BackgroundServiceError,
    print_background_service_result,
)
from .codex_app_server import CodexAppServerError, probe_codex_app_server
from .codex_evidence import (
    collect_codex_limit_observation,
    record_codex_limit_observation,
)
from .codex_hook import run_from_stdin as run_codex_hook_from_stdin
from .codex_hook_installer import (
    install_codex_hook,
    uninstall_codex_hook,
)
from .codex_hook_installer import (
    print_result as print_hook_install_result,
)
from .codex_input import (
    CodexInputError,
    resolve_native_destination,
    send_native_message,
)
from .config import AppConfig, load_config
from .continue_task import ContinueTaskError, execute_continue_task
from .control import CONTROL_NAMES, ControlError, ControlStore
from .diagnosis_engine import diagnose_worker
from .diagnostic_notifications import notify_diagnostic_incident
from .identity import WORKER_SCOPES, scoped_worker_id
from .linux_evidence import (
    LinuxPowerObserver,
    LinuxProcessObserver,
    observe_linux_network,
    observe_user_service,
    record_linux_observations,
)
from .notify import NotificationError, Notifier
from .platform_integration import (
    UnsupportedPlatformError,
    ensure_runtime_enabled,
    get_platform_factory,
)
from .product_health import collect_doctor_report
from .protocols import (
    PROTOCOLS,
    choose_threshold,
    format_duration,
    get_protocol,
    should_escalate,
)
from .recovery_coordinator import recover_diagnostic_incident
from .remote_questions import (
    RemoteQuestionError,
    ask_remote_question,
    observe_discord_replies_once,
    retry_answer_dispatch,
)
from .store import SCHEMA_VERSION, PresenceStore, WorkerState, inspect_schema
from .systemd_service import (
    install_reply_observer_service,
    install_user_service,
    uninstall_reply_observer_service,
    uninstall_user_service,
)
from .systemd_service import (
    print_result as print_systemd_result,
)
from .updater import UpgradeError, rollback_upgrade, upgrade_from_wheel
from .work_window import get_work_window_status

DEFAULT_EVENT_MESSAGES = {
    "start": "tarefa iniciada",
    "heartbeat": "continuo trabalhando",
    "touch": "atividade interna registrada",
    "finish": "tarefa concluida",
}

DISABLED_RUNTIME_SAFE_COMMANDS = frozenset(
    {
        "finish",
        "doctor",
        "protocols",
        "questions",
        "schema-status",
        "status",
        "stop-alarm",
        "uninstall-background-service",
        "uninstall-codex-hook",
        "uninstall-reply-observer-service",
        "uninstall-systemd-service",
    }
)


def _command_allowed_while_runtime_disabled(args: argparse.Namespace) -> bool:
    if args.command in DISABLED_RUNTIME_SAFE_COMMANDS:
        return True
    return args.command == "control" and args.action in {"show", "disable"}


def _enforce_runtime_policy(args: argparse.Namespace, config: AppConfig) -> None:
    if _command_allowed_while_runtime_disabled(args):
        return
    ensure_runtime_enabled(
        experimental_windows_enabled=config.experimental_windows_enabled,
    )


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

    if threshold_level == "red" and worker.last_alert_level == "red":
        return False

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
        answer_transport = (
            getattr(args, "answer_transport", None)
            or config.question_answer_transport
        )
        answer_destination = (
            getattr(args, "answer_destination", None)
            or config.question_answer_destination
        )
        print(
            f"[dry-run:pergunta] worker={worker_id} prazo={timeout}s "
            f"transporte={answer_transport} destino={answer_destination} "
            f"sessao={getattr(args, 'thread', None) or '-'} "
            f"texto={args.question!r}"
        )
        return 0

    store = PresenceStore(config.db_path)
    controls = ControlStore.from_config(config).load()
    try:
        question = ask_remote_question(
            config=config,
            store=store,
            worker_id=worker_id,
            prompt=args.question,
            timeout_seconds=timeout,
            answer_transport=getattr(args, "answer_transport", None),
            thread_id=getattr(args, "thread", None),
            destination=getattr(args, "answer_destination", None),
            window_id=args.window_id,
            title_pattern=args.window_title,
            controls=controls,
        )
    except RemoteQuestionError as exc:
        print(f"Falha ao publicar pergunta: {exc}", file=sys.stderr)
        return 2

    print(
        f"pergunta={question.question_id} status={question.status} "
        f"discord_message={question.external_message_id} worker={question.worker_id} "
        f"transporte={question.answer_transport} "
        f"sessao={question.target_session_id or '-'}"
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
            controls=ControlStore.from_config(config).load(),
        )
    except RemoteQuestionError as exc:
        print(f"Falha no observer de respostas: {exc}", file=sys.stderr)
        return 2
    print(
        f"respostas: lidas={result.fetched} aceitas={result.accepted} "
        f"entregues={result.dispatched} falhas_entrega={result.dispatch_failed} "
        f"orientadas={result.guided} falhas_orientacao={result.guidance_failed}"
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
            f"transporte={question.answer_transport or 'legacy'} | "
            f"sessao={question.target_session_id or '-'} | "
            f"destino={question.target_destination or '-'} | "
            f"autor={question.answered_by or '-'} | resposta={answer!r} | erro={error!r}"
        )
    return 0


def _dispatch_answer(args: argparse.Namespace, config: AppConfig) -> int:
    if args.dry_run:
        print(
            f"[dry-run:entrega-resposta] pergunta={args.question_id}; "
            "transporte e banco nao foram alterados."
        )
        return 0
    try:
        question = retry_answer_dispatch(
            config=config,
            store=PresenceStore(config.db_path),
            question_id=args.question_id,
            controls=ControlStore.from_config(config).load(),
        )
    except (RemoteQuestionError, ValueError) as exc:
        print(f"Falha na entrega da resposta: {exc}", file=sys.stderr)
        return 2
    print(f"pergunta={question.question_id} status={question.status}")
    return 0


def _continue_task(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    controls = ControlStore.from_config(config).load()
    if (
        not args.dry_run
        and not controls.task_automation_enabled
        and not getattr(args, "authorize_once", False)
    ):
        print(
            "Falha ao executar continue: automacao de tarefas desativada. "
            "Habilite com 'ai-presence control enable task-automation' ou use "
            "--authorize-once para esta execucao.",
            file=sys.stderr,
        )
        return 2
    try:
        result = execute_continue_task(
            config=config,
            worker_id=worker_id,
            message=args.message,
            delay_seconds=args.delay,
            window_id=args.window_id,
            title_pattern=args.window_title,
            allow_title_change=args.allow_title_change,
            sync_activity=args.sync_activity,
            input_transport=getattr(args, "transport", None),
            input_destination=getattr(args, "destination", None),
            thread_id=getattr(args, "thread", None),
            remote=getattr(args, "remote", None),
            remote_auth_token_env=getattr(args, "remote_auth_token_env", None),
            native_detached=getattr(args, "detach", None),
            dry_run=args.dry_run,
            controls=controls,
        )
    except ContinueTaskError as exc:
        print(f"Falha ao executar continue: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        sync = (
            controls.sync_activity_enabled
            if args.sync_activity is None
            else args.sync_activity
        )
        print(
            f"[dry-run:continue] worker={worker_id} "
            f"atraso={result.delay_seconds}s mensagem={result.message!r} "
            f"transporte={result.transport} "
            f"destino={result.destination} "
            f"sessao={result.thread_id or '-'} "
            f"destacado={str(result.detached).lower()} "
            f"permitir_mudanca_titulo={str(args.allow_title_change).lower()} "
            f"sincronizar_atividade={str(sync).lower()}; "
            "espera, entrada e banco nao foram acessados."
        )
        return 0

    if result.dispatch_state == "dispatch_started":
        print(
            "continue: dispatch_started transporte=native "
            f"destino={result.destination} sessao={result.thread_id} "
            f"worker={worker_id}; aguarde evidencia posterior da sessao"
        )
        return 0

    if result.transport == "native":
        print(
            f"continue: input_emitted transporte=native "
            f"destino={result.destination} sessao={result.thread_id} "
            f"worker={worker_id}"
        )
    else:
        assert result.target is not None
        print(
            f"continue: input_emitted transporte=gui "
            f"janela={result.target.window_id} worker={worker_id}"
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


def _control(args: argparse.Namespace, config: AppConfig) -> int:
    store = ControlStore.from_config(config)
    settings = store.load()
    if args.action in {"enable", "disable"}:
        if args.control_name is None:
            raise ControlError("Informe qual controle deve ser alterado.")
        settings = settings.with_control(
            args.control_name,
            args.action == "enable",
        )
        if not getattr(args, "dry_run", False):
            store.save(settings)
    elif args.action == "target":
        thread_id = (
            None
            if args.clear_thread
            else args.thread
            if args.thread is not None
            else settings.codex_thread_id
        )
        if args.clear_remote:
            remote = None
            auth_env = None
        else:
            remote = args.remote if args.remote is not None else settings.codex_remote
            auth_env = (
                args.remote_auth_token_env
                if args.remote_auth_token_env is not None
                else settings.remote_auth_token_env
            )
        settings = settings.with_target(
            thread_id=thread_id,
            remote=remote,
            remote_auth_token_env=auth_env,
        )
        if not getattr(args, "dry_run", False):
            store.save(settings)

    payload = {
        "control_path": str(store.path),
        **settings.__dict__,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if getattr(args, "dry_run", False) and args.action != "show":
            print("[dry-run:control] alteracao nao persistida")
        print(f"controle={store.path}")
        for key, value in payload.items():
            if key == "control_path":
                continue
            print(f"{key}={value if value is not None else '-'}")
    return 0


def _tray(args: argparse.Namespace, config: AppConfig) -> int:
    from .tray import TrayUnavailableError, run_tray

    try:
        return run_tray(config, check_only=args.check)
    except TrayUnavailableError as exc:
        print(f"Bandeja indisponivel: {exc}", file=sys.stderr)
        return 2


def _send_input(args: argparse.Namespace, config: AppConfig) -> int:
    settings = ControlStore.from_config(config).load()
    destination = "remote" if args.destination == "client" else "local"
    try:
        if not args.message.strip():
            raise CodexInputError("A mensagem para o Codex nao pode ficar vazia.")
        thread_id, remote, _ = resolve_native_destination(
            settings=settings,
            destination=destination,
            thread_id=args.thread,
        )
        if args.dry_run:
            print(
                f"[dry-run:input] sessao={thread_id} "
                f"destino={'cliente' if remote else 'local'}; nenhuma entrada foi emitida."
            )
            return 0
        result = send_native_message(
            settings=settings,
            message=args.message,
            destination=destination,
            thread_id=thread_id,
            detached=getattr(args, "detach", None),
        )
    except CodexInputError as exc:
        print(f"Falha ao enviar entrada: {exc}", file=sys.stderr)
        return 2
    print(
        f"{result.state} transporte=native sessao={result.thread_id} "
        f"destino={'cliente' if result.remote else 'local'}"
    )
    return 0


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


def _install_background_service(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        manager = get_platform_factory(
            experimental_windows_enabled=config.experimental_windows_enabled,
        ).create_background_service_manager()
        result = manager.install(
            component=args.component,
            env_file=config.env_path,
            target_path=args.target,
            python_executable=args.python,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
    except (BackgroundServiceError, UnsupportedPlatformError) as exc:
        print(f"Falha ao instalar execucao continua: {exc}", file=sys.stderr)
        return 2
    print_background_service_result(result, dry_run=args.dry_run)
    return 0


def _uninstall_background_service(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        manager = get_platform_factory(
            experimental_windows_enabled=True,
        ).create_background_service_manager()
        result = manager.uninstall(
            component=args.component,
            target_path=args.target,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
    except (BackgroundServiceError, UnsupportedPlatformError) as exc:
        print(f"Falha ao remover execucao continua: {exc}", file=sys.stderr)
        return 2
    print_background_service_result(result, dry_run=args.dry_run)
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


def _show_schema_status(args: argparse.Namespace, config: AppConfig) -> int:
    schema = inspect_schema(config.db_path)
    payload = {
        "database_exists": schema.database_exists,
        "current_version": schema.current_version,
        "expected_version": schema.expected_version,
        "migration_status": schema.migration_status,
        "integrity": schema.integrity,
        "missing_table_count": len(schema.missing_tables),
        "healthy": schema.healthy,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "schema: "
            f"status={schema.migration_status} "
            f"current={schema.current_version if schema.current_version is not None else '-'} "
            f"expected={schema.expected_version} integrity={schema.integrity} "
            f"missing_tables={len(schema.missing_tables)}"
        )
    return 0 if schema.healthy else 1


def _doctor(args: argparse.Namespace, config: AppConfig) -> int:
    report = collect_doctor_report(config)
    if args.json:
        print(report.render_json())
    else:
        for check in report.checks:
            print(f"[{check.status}] {check.name}: {check.summary}")
        print(f"doctor: {report.status}")
    return report.exit_code(strict=args.strict)


def _upgrade(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        result = upgrade_from_wheel(
            config=config,
            target_wheel=args.package,
            rollback_wheel=args.rollback_package,
            authorized=args.authorize_once,
            dry_run=args.dry_run,
        )
    except UpgradeError as exc:
        print(f"Upgrade failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"upgrade: status={result.status} from={result.from_version} "
            f"to={result.to_version} manifest={result.manifest_path or '-'}"
        )
    return 0


def _rollback_upgrade(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        result = rollback_upgrade(
            config=config,
            manifest_path=args.manifest,
            authorized=args.authorize_once,
            restore_database=args.restore_database,
            dry_run=args.dry_run,
        )
    except UpgradeError as exc:
        print(f"Rollback failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"rollback: status={result.status} from={result.from_version} "
            f"to={result.to_version} manifest={result.manifest_path or '-'}"
        )
    return 0


def _show_protocols() -> int:
    for protocol in PROTOCOLS.values():
        print(f"{protocol.protocol_id}: {protocol.title}")
        print(f"  {protocol.description}")
        for threshold in protocol.thresholds:
            print(f"  - {threshold.color_name}: depois de {format_duration(threshold.after_seconds)}")
    return 0


def _stop_alarm(args: argparse.Namespace) -> int:
    try:
        result = AlarmController(experimental_windows_enabled=True).stop(
            timeout_seconds=args.timeout,
            force=not args.no_force,
            dry_run=args.dry_run,
        )
    except AlarmControlError as exc:
        print(f"Falha ao interromper alarme: {exc}", file=sys.stderr)
        return 2

    if result.status == "would_stop":
        print(f"[dry-run:alarme] interromperia PID {result.pid}.")
    elif result.status == "stopped":
        mode = "forcado" if result.forced else "normal"
        print(f"alarme interrompido: pid={result.pid} modo={mode}")
    elif result.status == "stale_state":
        print(f"alarme ja estava inativo; estado obsoleto removido: pid={result.pid}")
    else:
        print("nenhum alarme controlado esta ativo.")
    return 0


def _probe_codex_app_server(args: argparse.Namespace) -> int:
    result = probe_codex_app_server(
        args.thread,
        subscription_seconds=args.subscribe_seconds,
        codex_executable=args.codex_executable,
        request_timeout=args.request_timeout,
    )
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    print(
        "Codex app-server probe: "
        f"thread={result.thread.thread_id} status={result.thread.status or 'unknown'}"
    )
    print(
        "Rate limits: "
        f"ordinary_usage_allowed={result.rate_limits.ordinary_usage_allowed} "
        f"reached_type={result.rate_limits.reached_type or 'none'}"
    )
    print(
        "Separate stdio subscription: "
        f"seconds={result.subscription_seconds:g} events={len(result.events)}"
    )
    return 0


def _observe_codex_limits(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    interval = (
        args.interval
        if args.interval is not None
        else config.codex_limit_poll_interval_seconds
    )
    evidence_ttl = (
        args.evidence_ttl
        if args.evidence_ttl is not None
        else config.codex_limit_evidence_ttl_seconds
    )
    if interval <= 0:
        raise ValueError("Codex limit poll interval must be greater than zero.")
    if evidence_ttl <= 0:
        raise ValueError("Codex limit evidence TTL must be greater than zero.")

    while True:
        if not args.dry_run:
            worker = PresenceStore(config.db_path).get_worker(worker_id)
            if worker is None:
                raise ValueError(
                    f"Worker not found: {worker_id}. Run start before recording evidence."
                )
            if worker.status != "active":
                if args.watch:
                    print(f"codex-limit: worker={worker_id} inativo; observer encerrado.")
                    return 0
                raise ValueError(
                    f"Worker is not active: {worker_id}. Run start before recording evidence."
                )
        observation = collect_codex_limit_observation(
            codex_executable=args.codex_executable,
            request_timeout=args.request_timeout,
            ttl_seconds=evidence_ttl,
        )
        if args.dry_run:
            print(
                "[dry-run:codex-limit] "
                f"worker={worker_id} state={observation.state}"
            )
            return 0
        else:
            worker = PresenceStore(config.db_path).get_worker(worker_id)
            if worker is None or worker.status != "active":
                if args.watch:
                    print(f"codex-limit: worker={worker_id} inativo; observer encerrado.")
                    return 0
                raise ValueError(
                    f"Worker became inactive before evidence was recorded: {worker_id}."
                )
            evidence = record_codex_limit_observation(
                db_path=config.db_path,
                worker_id=worker_id,
                session_id=args.session,
                observation=observation,
            )
            print(
                "codex-limit: "
                f"worker={worker_id} state={evidence.state} "
                f"evidence={evidence.evidence_id}"
            )
        if not args.watch:
            return 0
        time.sleep(interval)


def _observe_linux_state(args: argparse.Namespace, config: AppConfig) -> int:
    if not sys.platform.startswith("linux"):
        raise UnsupportedPlatformError(
            "The Linux evidence observer is available only on Linux."
        )
    worker_id, _, _, _ = _identity(args, config)
    interval = (
        args.interval
        if args.interval is not None
        else config.linux_observer_interval_seconds
    )
    evidence_ttl = (
        args.evidence_ttl
        if args.evidence_ttl is not None
        else config.linux_evidence_ttl_seconds
    )
    suspend_gap = (
        args.suspend_gap
        if args.suspend_gap is not None
        else config.linux_suspend_gap_seconds
    )
    service_timeout = (
        args.service_timeout
        if args.service_timeout is not None
        else config.linux_service_timeout_seconds
    )
    if interval <= 0:
        raise ValueError("Linux observer interval must be greater than zero.")
    if evidence_ttl <= 0:
        raise ValueError("Linux evidence TTL must be greater than zero.")
    if suspend_gap <= 0:
        raise ValueError("Linux suspend gap must be greater than zero.")
    if service_timeout <= 0:
        raise ValueError("Linux service timeout must be greater than zero.")
    if args.expected_process_name is not None and args.process_pid is None:
        raise ValueError("--expected-process-name requires --process-pid.")

    process_observer = (
        LinuxProcessObserver(
            args.process_pid,
            expected_name=args.expected_process_name,
        )
        if args.process_pid is not None
        else None
    )
    power_observer = (
        None
        if args.skip_power
        else LinuxPowerObserver(suspend_gap_seconds=suspend_gap)
    )
    if args.no_services:
        services: tuple[str, ...] = ()
    elif args.services is not None:
        services = tuple(dict.fromkeys(args.services))
    else:
        services = tuple(dict.fromkeys(config.linux_user_services))
    if (
        process_observer is None
        and args.skip_network
        and power_observer is None
        and not services
    ):
        raise ValueError("At least one Linux evidence collector must be enabled.")

    while True:
        if not args.dry_run:
            worker = PresenceStore(config.db_path).get_worker(worker_id)
            if worker is None:
                raise ValueError(
                    f"Worker not found: {worker_id}. Run start before recording evidence."
                )
            if worker.status != "active":
                if args.watch:
                    print(f"linux-evidence: worker={worker_id} inativo; observer encerrado.")
                    return 0
                raise ValueError(
                    f"Worker is not active: {worker_id}. Run start before recording evidence."
                )

        observations = []
        if process_observer is not None:
            observations.append(process_observer.sample())
        if not args.skip_network:
            observations.append(observe_linux_network())
        if power_observer is not None:
            observations.append(power_observer.sample())
        observations.extend(
            observe_user_service(service, timeout_seconds=service_timeout)
            for service in services
        )
        states = ",".join(
            f"{observation.source.value}:{observation.state}"
            for observation in observations
        )

        if args.dry_run:
            print(f"[dry-run:linux-evidence] worker={worker_id} states={states}")
            return 0

        worker = PresenceStore(config.db_path).get_worker(worker_id)
        if worker is None or worker.status != "active":
            if args.watch:
                print(f"linux-evidence: worker={worker_id} inativo; observer encerrado.")
                return 0
            raise ValueError(
                f"Worker became inactive before evidence was recorded: {worker_id}."
            )
        evidence = record_linux_observations(
            db_path=config.db_path,
            worker_id=worker_id,
            session_id=args.session,
            observations=tuple(observations),
            observed_at=time.time(),
            ttl_seconds=evidence_ttl,
        )
        print(
            f"linux-evidence: worker={worker_id} records={len(evidence)} states={states}"
        )
        if not args.watch:
            return 0
        time.sleep(interval)


def _diagnose(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    result = diagnose_worker(
        db_path=config.db_path,
        worker_id=worker_id,
        session_id=args.session,
        dry_run=args.dry_run,
        presence_ttl_seconds=args.presence_ttl,
    )
    payload = {
        "worker_id": result.worker_id,
        "session_id": result.session_id,
        "age_seconds": None if math.isinf(result.age_seconds) else result.age_seconds,
        "severity": result.severity.value,
        "kind": result.assessment.kind.value,
        "confidence": result.assessment.confidence.value,
        "summary": result.assessment.summary,
        "transition": result.transition,
        "diagnosis_id": result.diagnosis.diagnosis_id if result.diagnosis else None,
        "incident_id": result.incident.incident_id if result.incident else None,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        prefix = "[dry-run:diagnosis]" if args.dry_run else "diagnosis:"
        age = "unknown" if math.isinf(result.age_seconds) else f"{result.age_seconds:.0f}s"
        print(
            f"{prefix} worker={result.worker_id} kind={result.assessment.kind.value} "
            f"confidence={result.assessment.confidence.value} "
            f"severity={result.severity.value} age={age} "
            f"transition={result.transition}"
        )
    return 0


def _notify_diagnostic_incident(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    result = notify_diagnostic_incident(
        db_path=config.db_path,
        worker_id=worker_id,
        discord_alert_webhook_url=config.discord_alert_webhook_url,
        discord_red_webhook_url=config.discord_red_webhook_url,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
    )
    payload = {
        "worker_id": result.worker_id,
        "status": result.status,
        "event_key": result.event_key,
        "incident_id": result.incident_id,
        "diagnosis_id": result.diagnosis_id,
        "notification_id": result.notification_id,
        "diagnosis_kind": result.diagnosis_kind,
        "confidence": result.confidence,
        "severity": result.severity,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        prefix = "[dry-run:diagnostic-notification]" if args.dry_run else "diagnostic-notification:"
        print(
            f"{prefix} worker={result.worker_id} status={result.status} "
            f"cause={result.diagnosis_kind or '-'} "
            f"confidence={result.confidence or '-'} "
            f"severity={result.severity or '-'}"
        )
    return 2 if result.status in {"rejected", "uncertain"} else 0


def _recover_diagnostic_incident(args: argparse.Namespace, config: AppConfig) -> int:
    worker_id, _, _, _ = _identity(args, config)
    result = recover_diagnostic_incident(
        db_path=config.db_path,
        worker_id=worker_id,
        controls=ControlStore.from_config(config).load(),
        message=config.continue_message,
        authorized=args.authorize_once,
        dry_run=args.dry_run,
    )
    payload = {
        "worker_id": result.worker_id,
        "status": result.status,
        "incident_id": result.incident_id,
        "diagnosis_id": result.diagnosis_id,
        "recovery_id": result.recovery_id,
        "diagnosis_kind": result.diagnosis_kind,
        "confidence": result.confidence,
        "severity": result.severity,
        "session_id": result.session_id,
        "stored_status": result.stored_status,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        prefix = "[dry-run:diagnostic-recovery]" if args.dry_run else "diagnostic-recovery:"
        print(
            f"{prefix} worker={result.worker_id} status={result.status} "
            f"cause={result.diagnosis_kind or '-'} "
            f"confidence={result.confidence or '-'} "
            f"severity={result.severity or '-'} "
            f"session={result.session_id or '-'}"
        )
    return 2 if result.status == "uncertain" else 0


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
        "--version",
        action="version",
        version=f"ai-presence {__version__}",
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

    stop_alarm_parser = subparsers.add_parser(
        "stop-alarm",
        help="Interrompe o processo de alarme local iniciado pelo monitor.",
    )
    stop_alarm_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Segundos para aguardar parada normal antes do fallback forcado. Padrao: 3.",
    )
    stop_alarm_parser.add_argument(
        "--no-force",
        action="store_true",
        help="Nao forca a arvore se o processo ignorar a parada normal.",
    )
    stop_alarm_parser.set_defaults(func=lambda args, config: _stop_alarm(args))

    app_server_parser = subparsers.add_parser(
        "probe-codex-app-server",
        help="Inspeciona metadados Codex por um app-server filho sem enviar entrada.",
    )
    app_server_parser.add_argument(
        "--thread",
        required=True,
        help="ID exato da sessao Codex persistida.",
    )
    app_server_parser.add_argument(
        "--subscribe-seconds",
        type=float,
        default=0.0,
        help="Janela observacional via thread/resume. Padrao: 0 (sem assinatura).",
    )
    app_server_parser.add_argument(
        "--request-timeout",
        type=float,
        default=10.0,
        help="Timeout de cada requisicao JSON-RPC. Padrao: 10 segundos.",
    )
    app_server_parser.add_argument(
        "--codex-executable",
        default="codex",
        help="Executavel Codex. Padrao: codex no PATH.",
    )
    app_server_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite somente campos sanitizados em JSON.",
    )
    app_server_parser.set_defaults(
        func=lambda args, config: _probe_codex_app_server(args)
    )

    codex_limits_parser = subparsers.add_parser(
        "observe-codex-limits",
        help="Registra evidencia sanitizada dos limites da conta Codex.",
    )
    _add_identity_args(codex_limits_parser, include_task_message=False)
    codex_limits_parser.add_argument(
        "--watch",
        action="store_true",
        help="Repete a leitura no intervalo configurado. Padrao: uma leitura.",
    )
    codex_limits_parser.add_argument(
        "--interval",
        type=int,
        help="Intervalo do modo watch em segundos.",
    )
    codex_limits_parser.add_argument(
        "--evidence-ttl",
        type=int,
        help="Validade da evidencia em segundos.",
    )
    codex_limits_parser.add_argument(
        "--request-timeout",
        type=float,
        default=10.0,
        help="Timeout da leitura JSON-RPC. Padrao: 10 segundos.",
    )
    codex_limits_parser.add_argument(
        "--codex-executable",
        default="codex",
        help="Executavel Codex. Padrao: codex no PATH.",
    )
    codex_limits_parser.set_defaults(
        func=lambda args, config: _observe_codex_limits(args, config)
    )

    linux_state_parser = subparsers.add_parser(
        "observe-linux-state",
        help="Registra evidencias locais de processo, rede, energia e servicos.",
    )
    _add_identity_args(linux_state_parser, include_task_message=False)
    linux_state_parser.add_argument(
        "--process-pid",
        type=int,
        help="PID Linux exato a observar.",
    )
    linux_state_parser.add_argument(
        "--expected-process-name",
        help="Nome exato esperado em /proc/PID/comm.",
    )
    linux_state_parser.add_argument(
        "--service",
        dest="services",
        action="append",
        help="Unidade systemd --user .service; pode ser repetida.",
    )
    linux_state_parser.add_argument(
        "--no-services",
        action="store_true",
        help="Ignora unidades configuradas no ambiente.",
    )
    linux_state_parser.add_argument(
        "--skip-network",
        action="store_true",
        help="Nao le rota e estado dos links locais.",
    )
    linux_state_parser.add_argument(
        "--skip-power",
        action="store_true",
        help="Nao observa intervalos de suspensao/retomada.",
    )
    linux_state_parser.add_argument(
        "--watch",
        action="store_true",
        help="Repete a coleta no intervalo configurado. Padrao: uma coleta.",
    )
    linux_state_parser.add_argument(
        "--interval",
        type=int,
        help="Intervalo do modo watch em segundos.",
    )
    linux_state_parser.add_argument(
        "--evidence-ttl",
        type=int,
        help="Validade comum das evidencias em segundos.",
    )
    linux_state_parser.add_argument(
        "--suspend-gap",
        type=float,
        help="Diferenca minima de relogios para detectar retomada.",
    )
    linux_state_parser.add_argument(
        "--service-timeout",
        type=float,
        help="Timeout de cada consulta systemctl --user.",
    )
    linux_state_parser.set_defaults(
        func=lambda args, config: _observe_linux_state(args, config)
    )

    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Correlaciona evidencia atual e aplica uma transicao de incidente.",
    )
    _add_identity_args(diagnose_parser, include_task_message=False)
    diagnose_parser.add_argument(
        "--presence-ttl",
        type=int,
        default=60,
        help="Validade do fato derivado do relogio de presenca. Padrao: 60 segundos.",
    )
    diagnose_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite somente o resultado sanitizado em JSON.",
    )
    diagnose_parser.set_defaults(func=lambda args, config: _diagnose(args, config))

    diagnostic_notification_parser = subparsers.add_parser(
        "notify-diagnostic-incident",
        help="Envia uma notificacao Discord deduplicada para o incidente atual.",
    )
    _add_identity_args(
        diagnostic_notification_parser,
        include_task_message=False,
    )
    diagnostic_notification_parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout do unico POST Discord. Padrao: 15 segundos.",
    )
    diagnostic_notification_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite somente o resultado sanitizado em JSON.",
    )
    diagnostic_notification_parser.set_defaults(
        func=lambda args, config: _notify_diagnostic_incident(args, config)
    )

    recovery_parser = subparsers.add_parser(
        "recover-diagnostic-incident",
        help="Executa uma recuperacao nativa one-shot para um incidente elegivel.",
    )
    _add_identity_args(recovery_parser, include_task_message=False)
    recovery_parser.add_argument(
        "--authorize-once",
        action="store_true",
        help="Autoriza somente esta tentativa real de recuperacao.",
    )
    recovery_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite somente o resultado sanitizado em JSON.",
    )
    recovery_parser.set_defaults(
        func=lambda args, config: _recover_diagnostic_incident(args, config)
    )

    ask_parser = subparsers.add_parser(
        "ask-user",
        help="Publica uma pergunta no Discord e aguarda resposta correlacionada.",
    )
    _add_identity_args(ask_parser)
    ask_parser.add_argument("--question", required=True, help="Pergunta enviada ao usuario.")
    ask_parser.add_argument("--timeout", type=int, help="Prazo da pergunta em segundos.")
    ask_parser.add_argument(
        "--answer-transport",
        choices=("native", "gui", "store"),
        help=(
            "Entrega da resposta. Padrao: "
            "PRESENCE_QUESTION_ANSWER_TRANSPORT ou native."
        ),
    )
    ask_parser.add_argument(
        "--thread",
        help="UUID ou nome exato da sessao Codex para entrega nativa.",
    )
    ask_parser.add_argument(
        "--answer-destination",
        choices=("local", "client"),
        help="Computador da sessao Codex. Padrao: local.",
    )
    ask_parser.add_argument(
        "--window-id",
        help="ID exato da janela. Se omitido, exige um unico titulo correspondente.",
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
        help="Reenvia manualmente uma resposta apos revisar uma falha de entrega.",
    )
    dispatch_parser.add_argument("question_id", help="ID local da pergunta.")
    dispatch_parser.set_defaults(func=lambda args, config: _dispatch_answer(args, config))

    continue_parser = subparsers.add_parser(
        "continue-task",
        aliases=["continue"],
        help="Agenda e envia uma mensagem de continuidade a uma sessao Codex.",
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
        help="ID exato da janela. Se omitido, exige um unico titulo correspondente.",
    )
    continue_parser.add_argument(
        "--window-title",
        help="Padrao de titulo; sobrescreve PRESENCE_CODEX_GUI_WINDOW_TITLE.",
    )
    continue_parser.add_argument(
        "--allow-title-change",
        action="store_true",
        help=(
            "Aceita mudanca do titulo completo durante a espera, mantendo "
            "a revalidacao do ID explicito e do padrao de titulo."
        ),
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
    continue_parser.add_argument(
        "--transport",
        choices=("auto", "native", "gui"),
        help="Transporte de entrada. Padrao: PRESENCE_CONTINUE_TRANSPORT ou auto.",
    )
    continue_parser.add_argument(
        "--thread",
        help="UUID ou nome exato da sessao Codex para transporte nativo.",
    )
    continue_parser.add_argument(
        "--destination",
        choices=("local", "client"),
        help="Computador de destino. Padrao: local.",
    )
    continue_parser.add_argument(
        "--remote",
        help="Endpoint app-server ws://, wss:// ou unix:// no computador cliente.",
    )
    continue_parser.add_argument(
        "--remote-auth-token-env",
        help="Nome da variavel de ambiente com o token do endpoint remoto.",
    )
    continue_parser.add_argument(
        "--authorize-once",
        action="store_true",
        help="Autoriza somente esta execucao quando a automacao persistente esta desligada.",
    )
    continue_parser.add_argument(
        "--detach",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Executa codex queue em segundo plano. Padrao: automatico ao enviar "
            "para a propria sessao Codex."
        ),
    )
    continue_parser.set_defaults(
        func=lambda args, config: _continue_task(args, config)
    )

    control_parser = subparsers.add_parser(
        "control",
        help="Consulta ou altera autorizacoes compartilhadas pela CLI e bandeja.",
    )
    control_parser.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=("show", "enable", "disable", "target"),
    )
    control_parser.add_argument("control_name", nargs="?", choices=CONTROL_NAMES)
    control_parser.add_argument("--thread", help="UUID ou nome exato da sessao Codex.")
    control_parser.add_argument("--clear-thread", action="store_true")
    control_parser.add_argument("--remote", help="Endpoint app-server remoto.")
    control_parser.add_argument(
        "--remote-auth-token-env",
        help="Nome da variavel de ambiente com o token remoto.",
    )
    control_parser.add_argument("--clear-remote", action="store_true")
    control_parser.add_argument("--json", action="store_true")
    control_parser.set_defaults(func=lambda args, config: _control(args, config))

    tray_parser = subparsers.add_parser(
        "tray",
        help="Inicia o controlador na bandeja do sistema.",
    )
    tray_parser.add_argument(
        "--check",
        action="store_true",
        help="Verifica suporte a bandeja sem manter o processo aberto.",
    )
    tray_parser.set_defaults(func=lambda args, config: _tray(args, config))

    input_parser = subparsers.add_parser(
        "send-input",
        help="Envia texto diretamente para uma sessao Codex, sem mouse ou teclado.",
    )
    input_parser.add_argument("--message", required=True, help="Texto a enfileirar.")
    input_parser.add_argument(
        "--destination",
        choices=("local", "client"),
        default="local",
        help="Instancia Codex local ou endpoint do computador cliente.",
    )
    input_parser.add_argument(
        "--thread",
        help="UUID ou nome exato; sobrescreve o alvo persistente.",
    )
    input_parser.add_argument(
        "--detach",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Despacha em segundo plano; automatico para a propria sessao.",
    )
    input_parser.set_defaults(func=lambda args, config: _send_input(args, config))

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

    install_background_parser = subparsers.add_parser(
        "install-background-service",
        help="Instala execucao continua via systemd ou Task Scheduler.",
    )
    install_background_parser.add_argument(
        "--component",
        choices=BACKGROUND_COMPONENTS,
        default="monitor",
        help="Componente continuo. Padrao: monitor.",
    )
    install_background_parser.add_argument(
        "--target",
        type=Path,
        help="Caminho opcional da definicao gerada.",
    )
    install_background_parser.add_argument(
        "--python",
        help="Executavel Python. Padrao: o mesmo Python desta instalacao.",
    )
    install_background_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Nao cria backup da definicao anterior.",
    )
    install_background_parser.set_defaults(
        func=lambda args, config: _install_background_service(args, config)
    )

    uninstall_background_parser = subparsers.add_parser(
        "uninstall-background-service",
        help="Remove execucao continua via systemd ou Task Scheduler.",
    )
    uninstall_background_parser.add_argument(
        "--component",
        choices=BACKGROUND_COMPONENTS,
        default="monitor",
        help="Componente continuo. Padrao: monitor.",
    )
    uninstall_background_parser.add_argument(
        "--target",
        type=Path,
        help="Caminho opcional da definicao administrada.",
    )
    uninstall_background_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Nao cria backup da definicao removida.",
    )
    uninstall_background_parser.set_defaults(
        func=lambda args, config: _uninstall_background_service(args, config)
    )

    status_parser = subparsers.add_parser("status", help="Mostra estado dos workers.")
    status_parser.set_defaults(func=lambda args, config: _show_status(config))

    schema_parser = subparsers.add_parser(
        "schema-status",
        help="Inspeciona versao, migracao e integridade do banco sem altera-lo.",
    )
    schema_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite somente o resultado sanitizado em JSON.",
    )
    schema_parser.set_defaults(func=lambda args, config: _show_schema_status(args, config))

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Verifica saude local sem imprimir segredos ou alterar estado.",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Emite somente o relatorio sanitizado em JSON.",
    )
    doctor_parser.add_argument(
        "--strict",
        action="store_true",
        help="Retorna codigo 1 quando houver avisos.",
    )
    doctor_parser.set_defaults(func=lambda args, config: _doctor(args, config))

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Atualiza por wheel local com backup e rollback automatico.",
    )
    upgrade_parser.add_argument("--package", type=Path, required=True)
    upgrade_parser.add_argument("--rollback-package", type=Path, required=True)
    upgrade_parser.add_argument("--authorize-once", action="store_true")
    upgrade_parser.add_argument("--json", action="store_true")
    upgrade_parser.set_defaults(func=lambda args, config: _upgrade(args, config))

    rollback_upgrade_parser = subparsers.add_parser(
        "rollback-upgrade",
        help="Restaura wheel e banco de um manifesto de upgrade concluido.",
    )
    rollback_upgrade_parser.add_argument("--manifest", type=Path, required=True)
    rollback_upgrade_parser.add_argument("--authorize-once", action="store_true")
    rollback_upgrade_parser.add_argument(
        "--restore-database",
        action="store_true",
        help="Confirma a restauracao destrutiva do snapshot anterior.",
    )
    rollback_upgrade_parser.add_argument("--json", action="store_true")
    rollback_upgrade_parser.set_defaults(
        func=lambda args, config: _rollback_upgrade(args, config)
    )

    return parser


def _init_db(config: AppConfig) -> int:
    PresenceStore(config.db_path)
    print(f"Banco pronto: {config.db_path} schema={SCHEMA_VERSION}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.env_file)
        if args.db:
            config = replace(config, db_path=Path(args.db).expanduser())
        _enforce_runtime_policy(args, config)
        raise_code = args.func(args, config)
    except (
        CodexAppServerError,
        ControlError,
        UnsupportedPlatformError,
        ValueError,
        KeyboardInterrupt,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise_code = 1
    raise SystemExit(raise_code)
