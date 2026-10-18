import ctypes as ct
from pathlib import Path
import queue
import unittest
from unittest.mock import Mock, patch
from desktop_integration import RTSSLifecycle, TrayIcon


class DesktopTests(unittest.TestCase):
    @patch('desktop_integration.ct.WinDLL')
    @patch('desktop_integration.psutil.Process')
    @patch('desktop_integration.subprocess.Popen')
    @patch('desktop_integration.psutil.process_iter', return_value=[])
    @patch('desktop_integration.find_rtss', return_value=Path('C:/RTSS/RTSS.exe'))
    def test_launches_hidden_and_waits_for_shared_memory(self, find, processes, launch, process, dll):
        dll.return_value.OpenFileMappingW.return_value = 123
        lifecycle = RTSSLifecycle()
        lifecycle.start()
        self.assertEqual(len(lifecycle.processes), 1)
        self.assertEqual(launch.call_args.kwargs['startupinfo'].wShowWindow, 0)
        dll.return_value.CloseHandle.assert_called_once_with(123)

    @patch('desktop_integration.ct.WinDLL')
    def test_close_requests_exit_and_falls_back_if_rtss_does_not_exit(self, dll):
        import psutil
        lifecycle = RTSSLifecycle()
        process = Mock(pid=123)
        process.wait.side_effect = [psutil.TimeoutExpired(2), 0]
        lifecycle.processes = [process]
        lifecycle.close()
        dll.return_value.EnumWindows.assert_called_once()
        process.terminate.assert_called_once()
        self.assertEqual(lifecycle.processes, [])

    @patch('desktop_integration.pystray.Icon')
    def test_tray_callbacks_queue_ui_actions(self, icon):
        events = queue.Queue()
        tray = TrayIcon(events)
        menu = icon.call_args.kwargs['menu']
        menu.items[0](icon.return_value)
        menu.items[1](icon.return_value)
        menu.items[3](icon.return_value)
        self.assertEqual(list(events.queue), [('tray', 'show'), ('tray', 'pause'), ('tray', 'quit')])
        tray.close()
        icon.return_value.stop.assert_called_once()
