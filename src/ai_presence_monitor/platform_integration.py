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


def get_platform_factory(platform_name: str | None = None) -> PlatformIntegrationFactory:
    selected = (platform_name or sys.platform).lower()
    if selected.startswith("linux"):
        return LinuxPlatformFactory()
    if selected in {"win32", "windows", "cygwin"}:
        return WindowsPlatformFactory()
    raise UnsupportedPlatformError(
        f"Plataforma sem adaptador operacional: {selected}."
    )
