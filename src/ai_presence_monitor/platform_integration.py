from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .alarm_process import AlarmProcessBackend
    from .background_service import BackgroundServiceManager
    from .gui_answer import GuiAnswerDispatcher


class UnsupportedPlatformError(RuntimeError):
    pass


WINDOWS_PLATFORM_NAMES = frozenset({"win32", "windows", "cygwin"})
WINDOWS_OPT_IN_ENV = "PRESENCE_EXPERIMENTAL_WINDOWS_ENABLED"


def ensure_runtime_enabled(
    *,
    platform_name: str | None = None,
    experimental_windows_enabled: bool = False,
) -> str:
    selected = (platform_name or sys.platform).lower()
    if selected.startswith("linux"):
        return "linux"
    if selected in WINDOWS_PLATFORM_NAMES:
        if experimental_windows_enabled:
            return "windows"
        raise UnsupportedPlatformError(
            "O runtime Windows e experimental e esta desativado nesta release. "
            f"Defina {WINDOWS_OPT_IN_ENV}=true somente para validacao controlada."
        )
    raise UnsupportedPlatformError(
        f"Plataforma sem adaptador operacional habilitado: {selected}."
    )


class PlatformIntegrationFactory(ABC):
    platform_name: str

    @abstractmethod
    def create_gui_dispatcher(
        self,
        *,
        x_ratio: float,
        y_ratio: float,
    ) -> GuiAnswerDispatcher: ...

    @abstractmethod
    def create_alarm_process_backend(self) -> AlarmProcessBackend: ...

    @abstractmethod
    def create_background_service_manager(self) -> BackgroundServiceManager: ...


class LinuxPlatformFactory(PlatformIntegrationFactory):
    platform_name = "linux"

    def create_gui_dispatcher(
        self,
        *,
        x_ratio: float,
        y_ratio: float,
    ) -> GuiAnswerDispatcher:
        from .gui_answer import X11GuiAnswerDispatcher

        return X11GuiAnswerDispatcher(x_ratio=x_ratio, y_ratio=y_ratio)

    def create_alarm_process_backend(self) -> AlarmProcessBackend:
        from .alarm_process import LinuxAlarmProcessBackend

        return LinuxAlarmProcessBackend()

    def create_background_service_manager(self) -> BackgroundServiceManager:
        from .background_service import LinuxBackgroundServiceManager

        return LinuxBackgroundServiceManager()


class WindowsPlatformFactory(PlatformIntegrationFactory):
    platform_name = "windows"

    def create_gui_dispatcher(
        self,
        *,
        x_ratio: float,
        y_ratio: float,
    ) -> GuiAnswerDispatcher:
        from .win32_gui import Win32GuiAnswerDispatcher

        return Win32GuiAnswerDispatcher(x_ratio=x_ratio, y_ratio=y_ratio)

    def create_alarm_process_backend(self) -> AlarmProcessBackend:
        from .windows_process import WindowsAlarmProcessBackend

        return WindowsAlarmProcessBackend()

    def create_background_service_manager(self) -> BackgroundServiceManager:
        from .windows_task import WindowsTaskSchedulerService

        return WindowsTaskSchedulerService()


def get_platform_factory(
    platform_name: str | None = None,
    *,
    experimental_windows_enabled: bool = False,
) -> PlatformIntegrationFactory:
    selected = ensure_runtime_enabled(
        platform_name=platform_name,
        experimental_windows_enabled=experimental_windows_enabled,
    )
    if selected == "linux":
        return LinuxPlatformFactory()
    return WindowsPlatformFactory()
