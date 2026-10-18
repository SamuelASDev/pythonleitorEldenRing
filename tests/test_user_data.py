import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from entre_terras.tracker_state import Journey, StateStore
from entre_terras.user_data import default_data_dir, migrate_legacy_data


class UserDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.legacy = self.root / "portable/data"
        self.destination = self.root / "LocalAppData/EntreTerras"

    def test_uses_user_local_appdata(self):
        with patch.dict("os.environ", {"LOCALAPPDATA": str(self.root)}):
            self.assertEqual(default_data_dir(), self.root / "EntreTerras")

    def test_migration_preserves_history_and_original(self):
        journey = Journey()
        journey.start("Margit")
        journey.record_death()
        original = StateStore(self.legacy)
        original.save(journey)
        before = original.path.read_bytes()
        migrate_legacy_data(self.destination, [self.legacy])
        self.assertEqual(StateStore(self.destination).load().data, journey.data)
        self.assertEqual(original.path.read_bytes(), before)

    def test_migration_never_overwrites_existing_user_data(self):
        old = Journey()
        old.record_death()
        StateStore(self.legacy).save(old)
        current = StateStore(self.destination)
        current.save(Journey())
        migrate_legacy_data(self.destination, [self.legacy])
        self.assertEqual(current.load().data["total"], 0)

    def test_uses_valid_backup_without_modifying_corrupt_source(self):
        self.legacy.mkdir(parents=True)
        (self.legacy / "state.json").write_text("corrupt", encoding="utf-8")
        journey = Journey()
        journey.record_death()
        (self.legacy / "state.json.bak").write_text(json.dumps(journey.data), encoding="utf-8")
        migrate_legacy_data(self.destination, [self.legacy])
        self.assertEqual(StateStore(self.destination).load().data["total"], 1)
        self.assertEqual((self.legacy / "state.json").read_text(), "corrupt")

    def test_corrupt_legacy_data_is_left_untouched(self):
        self.legacy.mkdir(parents=True)
        (self.legacy / "state.json").write_text("{}", encoding="utf-8")
        migrate_legacy_data(self.destination, [self.legacy])
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.legacy.iterdir()), [self.legacy / "state.json"])
