"""User-owned storage, including migration from older portable versions."""
import os
import json
from pathlib import Path

from entre_terras.tracker_state import Journey, StateStore


def default_data_dir():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "EntreTerras"


def migrate_legacy_data(destination, candidates):
    destination = Path(destination)
    if any((destination / name).exists() for name in ("state.json", "state.json.bak")):
        return
    for candidate in candidates:
        candidate = Path(candidate)
        if candidate.resolve() == destination.resolve():
            continue
        if not any((candidate / name).is_file() for name in ("state.json", "state.json.bak")):
            continue
        for name in ("state.json", "state.json.bak"):
            try:
                journey = Journey(json.loads((candidate / name).read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError, TypeError):
                continue
            StateStore(destination).save(journey)
            return
