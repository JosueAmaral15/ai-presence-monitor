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
    ensure_runtime_enabled,
    get_platform_factory,
)


class PlatformIntegrationFactoryTests(unittest.TestCase):
    def test_selects_concrete_family_from_platform_name(self) -> None:
        self.assertIsInstance(get_platform_factory("linux"), LinuxPlatformFactory)
        self.assertIsInstance(get_platform_factory("linux2"), LinuxPlatformFactory)
        with self.assertRaisesRegex(UnsupportedPlatformError, "experimental"):
            get_platform_factory("win32")
        self.assertIsInstance(
            get_platform_factory("win32", experimental_windows_enabled=True),
            WindowsPlatformFactory,
        )
        self.assertIsInstance(
            get_platform_factory("windows", experimental_windows_enabled=True),
            WindowsPlatformFactory,
        )

        with self.assertRaisesRegex(UnsupportedPlatformError, "darwin"):
            get_platform_factory("darwin")

    def test_default_selection_uses_runtime_platform(self) -> None:
        with patch("ai_presence_monitor.platform_integration.sys.platform", "win32"):
            with self.assertRaisesRegex(UnsupportedPlatformError, "desativado"):
                get_platform_factory()
            self.assertIsInstance(
                get_platform_factory(experimental_windows_enabled=True),
                WindowsPlatformFactory,
            )

    def test_runtime_policy_normalizes_supported_platforms(self) -> None:
        self.assertEqual(ensure_runtime_enabled(platform_name="linux2"), "linux")
        self.assertEqual(
            ensure_runtime_enabled(
                platform_name="win32",
                experimental_windows_enabled=True,
            ),
            "windows",
        )
        with self.assertRaisesRegex(UnsupportedPlatformError, "darwin"):
            ensure_runtime_enabled(platform_name="darwin")

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
