from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from entre_terras.global_hotkeys import parse_hotkey, validate_hotkeys
from entre_terras.tracker_state import Journey, StateStore, DEFAULTS, validate_template


class JourneyTests(unittest.TestCase):
    def test_detected_death_increments_total_and_only_active_boss(self):
        j = Journey()
        first = j.start("Margit")
        j.record_death()
        j.finish()
        second = j.start("Godrick")
        j.record_death()
        j.record_death()
        self.assertEqual(j.data["total"], 3)
        self.assertEqual(first["deaths"], 1)
        self.assertEqual(second["deaths"], 2)

    def test_manual_corrections_and_reset_are_independent(self):
        j = Journey()
        boss = j.start("Margit")
        j.record_death()
        j.adjust("total", 4)
        self.assertEqual(boss["deaths"], 1)
        j.set_count(boss["id"], 0)
        self.assertEqual(j.data["total"], 5)
        j.set_count("total", 0)
        j.adjust(boss["id"], 3)
        self.assertEqual(j.data["total"], 0)
        self.assertEqual(boss["deaths"], 3)
        j.adjust("total", -10)
        self.assertEqual(j.data["total"], 0)

    def test_paused_deaths_are_ignored_but_manual_edit_still_works(self):
        j = Journey()
        boss = j.start("Margit")
        j.data["paused"] = True
        self.assertFalse(j.record_death())
        j.adjust(boss["id"], 1)
        self.assertEqual(j.data["total"], 0)
        self.assertEqual(boss["deaths"], 1)

    def test_win_retains_session_and_overlay_order(self):
        j = Journey()
        boss = j.start("Margit")
        j.record_death()
        ended = j.finish()
        self.assertIsNone(j.active)
        self.assertEqual(ended["status"], "won")
        self.assertTrue(ended["ended"])
        boss["pinned"] = True
        j.start("Godrick")
        self.assertEqual(j.overlay().splitlines()[:3], ["Mortes totais: 1", "Godrick = 0", "Margit = 1"])
        j.settings["show_status"] = False
        j.settings["show_boss"] = False
        self.assertEqual(j.overlay(), "Mortes totais: 1")

    def test_no_second_active_session(self):
        j = Journey()
        j.start("Margit")
        with self.assertRaises(ValueError):
            j.start("Godrick")
        self.assertEqual(len(j.data["sessions"]), 1)

    def test_bad_templates_are_rejected(self):
        for text in ("", "sem contagem", "{total.__class__}", "{total:1000}", "{total!r}", "{total}\nmais", "<P=0>{total}", "{total"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_template(text, {"total"})
        self.assertEqual(validate_template("{nome} = {mortes}", {"nome", "mortes"}), "{nome} = {mortes}")


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = StateStore(self.temp.name)

    def test_restart_restores_active_session_history_and_settings(self):
        j = Journey()
        j.start("Margit")
        j.record_death()
        j.finish()
        j.start("Godrick")
        j.settings["hotkeys"]["total_up"] = "Ctrl+Alt+F8"
        self.store.save(j)
        restored = self.store.load()
        self.assertEqual(restored.data, j.data)

    def test_corrupt_primary_recovers_previous_backup(self):
        j = Journey()
        j.record_death()
        self.store.save(j)
        j.record_death()
        self.store.save(j)
        self.store.path.write_text("broken", encoding="utf-8")
        restored = self.store.load()
        self.assertEqual(restored.data["total"], 1)
        self.assertIn("backup", self.store.warning)
        self.store.save(restored)
        self.assertEqual(self.store.load().data["total"], 1)

    def test_invalid_data_preserved_before_new_save(self):
        self.store.path.write_text("{}", encoding="utf-8")
        restored = self.store.load()
        self.assertTrue(list(Path(self.temp.name).glob("*.invalid-*")))
        self.assertEqual(restored.data["total"], 0)


class ShortcutParsingTests(unittest.TestCase):
    def test_defaults_unique_and_supported(self):
        parsed = validate_hotkeys(DEFAULTS["hotkeys"])
        self.assertEqual(len(parsed), 8)
        self.assertEqual(parse_hotkey("Ctrl+Alt+F8"), (3, 0x77))
        self.assertIsNone(parse_hotkey(""))

    def test_repeated_shortcuts_rejected(self):
        keys = deepcopy(DEFAULTS["hotkeys"])
        keys["total_down"] = "Alt+Ctrl+PageUp"
        with self.assertRaises(ValueError):
            validate_hotkeys(keys)

    def test_unsafe_or_invalid_shortcuts_rejected(self):
        for text in ("A", "Ctrl+Ctrl+A", "Ctrl++A", "Ctrl+F99", "Other+A"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hotkey(text)
