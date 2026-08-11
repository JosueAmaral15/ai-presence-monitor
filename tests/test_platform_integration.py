from __future__ import annotations

import unittest
from unittest.mock import patch

from ai_presence_monitor.alarm_process import LinuxAlarmProcessBackend
from ai_presence_monitor.background_service import LinuxBackgroundServiceManager
from ai_presence_monitor.gui_answer import X11GuiAnswerDispatcher
from ai_presence_monitor.platform_integration import (
    LinuxPlatformFactory,
    UnsupportedPlatformError,
    WindowsPlatformFactory,
    get_platform_factory,
)


class PlatformIntegrationFactoryTests(unittest.TestCase):
    def test_selects_concrete_family_from_platform_name(self) -> None:
        self.assertIsInstance(get_platform_factory("linux"), LinuxPlatformFactory)
        self.assertIsInstance(get_platform_factory("linux2"), LinuxPlatformFactory)
        self.assertIsInstance(get_platform_factory("win32"), WindowsPlatformFactory)
        self.assertIsInstance(get_platform_factory("windows"), WindowsPlatformFactory)

        with self.assertRaisesRegex(UnsupportedPlatformError, "darwin"):
            get_platform_factory("darwin")

    def test_default_selection_uses_runtime_platform(self) -> None:
        with patch("ai_presence_monitor.platform_integration.sys.platform", "win32"):
            self.assertIsInstance(get_platform_factory(), WindowsPlatformFactory)

    def test_linux_factory_builds_coherent_products(self) -> None:
        factory = LinuxPlatformFactory()

        self.assertIsInstance(
            factory.create_gui_dispatcher(x_ratio=0.5, y_ratio=0.9),
            X11GuiAnswerDispatcher,
        )
        self.assertIsInstance(
            factory.create_alarm_process_backend(),
            LinuxAlarmProcessBackend,
        )
        self.assertIsInstance(
            factory.create_background_service_manager(),
            LinuxBackgroundServiceManager,
        )


if __name__ == "__main__":
    unittest.main()
