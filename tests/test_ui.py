from pathlib import Path
import tempfile
import tkinter as tk
from unittest.mock import patch
import unittest

from entre_terras.tracker_state import Journey, StateStore
from entre_terras.tracker_ui import ControlPanel
from entre_terras.vision import BASE_DIR


class PanelFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.worker_patch = patch("entre_terras.tracker_ui.CaptureWorker")
        self.hotkeys_patch = patch("entre_terras.tracker_ui.GlobalHotkeys")
        self.worker_patch.start()
        self.hotkeys_patch.start()
        self.addCleanup(self.worker_patch.stop)
        self.addCleanup(self.hotkeys_patch.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.store = StateStore(self.folder.name)
        self.app = ControlPanel(self.root, Journey(), self.store, BASE_DIR / "assets/death-message.png", enable_tray=False)
        self.addCleanup(self.app.close)

    def test_full_boss_flow_with_independent_actions_and_restart(self):
        self.app.new_boss_var.set("Margit")
        self.app.start_boss()
        self.app.events.put(("death",))
        self.app.poll()
        self.app.action("total_up")
        self.app.action("boss_up")
        self.assertEqual(self.app.journey.data["total"], 2)
        self.assertEqual(self.app.journey.active["deaths"], 2)
        self.app.action("boss_reset")
        self.assertEqual(self.app.journey.data["total"], 2)
        self.app.action("boss_up")
        self.app.action("victory")
        self.assertIsNone(self.app.journey.active)
        self.assertEqual(self.app.journey.data["sessions"][0]["deaths"], 1)
        restored = self.store.load()
        self.assertEqual(restored.data, self.app.journey.data)

    def test_settings_only_apply_after_native_hotkey_registration_succeeds(self):
        self.app.form["total_template"].set("Jornada = {total}")
        self.app.apply_settings()
        self.assertEqual(self.app.journey.settings["total_template"], "Mortes totais: {total}")
        token = self.app.settings_token
        self.app.events.put(("hotkeys_result", token, True, "OK"))
        self.app.poll()
        self.assertEqual(self.app.journey.overlay().splitlines()[0], "Jornada = 0")
        self.assertEqual(self.store.load().settings["total_template"], "Jornada = {total}")
