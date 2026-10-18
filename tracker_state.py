"""Persistent journey, independent boss sessions and overlay formatting."""
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from string import Formatter
import uuid


HOTKEY_LABELS = {
    "total_up": "Geral: aumentar", "total_down": "Geral: diminuir", "total_reset": "Geral: zerar",
    "boss_up": "Chefe ativo: aumentar", "boss_down": "Chefe ativo: diminuir", "boss_reset": "Chefe ativo: zerar",
    "pause": "Pausar / retomar detecção", "victory": "Chefe vencido: encerrar sessão",
}
DEFAULTS = {
    "total_template": "Mortes totais: {total}", "boss_template": "{nome} = {mortes}",
    "show_status": True, "show_boss": True, "capture": "rtss", "monitor": 0,
    "fps": 2, "threshold": 0.70, "confirmation_frames": 2, "clear_seconds": 2.0,
    "hotkeys": {
        "total_up": "Ctrl+Alt+PageUp", "total_down": "Ctrl+Alt+PageDown", "total_reset": "Ctrl+Alt+Home",
        "boss_up": "Ctrl+Shift+PageUp", "boss_down": "Ctrl+Shift+PageDown", "boss_reset": "Ctrl+Shift+Home",
        "pause": "Ctrl+Alt+P", "victory": "Ctrl+Alt+End",
    },
}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def validate_template(text, allowed):
    if not isinstance(text, str) or not text.strip() or len(text) > 120:
        raise ValueError("Use um texto de 1 a 120 caracteres.")
    if any(char in text for char in "\n\r<>\x00"):
        raise ValueError("O texto deve ter uma linha, sem os sinais < e >.")
    try:
        fields = list(Formatter().parse(text))
    except ValueError as error:
        raise ValueError("Confira as chaves do texto, por exemplo: {nome} = {mortes}.") from error
    for _, field, spec, conversion in fields:
        if field is not None and (field not in allowed or spec or conversion):
            raise ValueError("Campos permitidos: " + ", ".join("{" + item + "}" for item in sorted(allowed)))
    required = "total" if "total" in allowed else "mortes"
    if not any(field == required for _, field, _, _ in fields):
        raise ValueError("Inclua {" + required + "} para exibir a contagem.")
    return text.strip()


def validate_settings(settings):
    result = deepcopy(DEFAULTS)
    result.update(settings)
    result["total_template"] = validate_template(result["total_template"], {"total"})
    result["boss_template"] = validate_template(result["boss_template"], {"nome", "mortes"})
    if result["capture"] not in ("rtss", "dxgi"):
        raise ValueError("Selecione RTSS ou DXGI.")
    for key, low, high in (("fps", 1, 15), ("monitor", 0, 16), ("confirmation_frames", 2, 5)):
        value = result[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key}: use um inteiro entre {low} e {high}.")
    for key, low, high in (("threshold", .50, .95), ("clear_seconds", 1., 10.)):
        value = result[key]
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValueError(f"{key}: use um valor entre {low} e {high}.")
    for key in ("show_status", "show_boss"):
        if type(result[key]) is not bool:
            raise ValueError(f"Configuração inválida: {key}")
    keys = result["hotkeys"]
    if not isinstance(keys, dict) or set(keys) != set(HOTKEY_LABELS) or any(not isinstance(v, str) for v in keys.values()):
        raise ValueError("Configuração de atalhos inválida.")
    return result


class Journey:
    def __init__(self, data=None):
        self.data = data if data is not None else {"version": 1, "total": 0, "paused": False, "active_id": None, "sessions": [], "settings": deepcopy(DEFAULTS)}
        self.validate()

    def validate(self):
        d = self.data
        if not isinstance(d, dict) or d.get("version") != 1:
            raise ValueError("Formato de dados não reconhecido.")
        if type(d.get("total")) is not int or d["total"] < 0 or type(d.get("paused")) is not bool:
            raise ValueError("Contador salvo inválido.")
        if not isinstance(d.get("sessions"), list) or not isinstance(d.get("settings"), dict):
            raise ValueError("Dados de sessões inválidos.")
        ids = set()
        for session in d["sessions"]:
            if not isinstance(session, dict) or not isinstance(session.get("id"), str) or session["id"] in ids:
                raise ValueError("Identificador de sessão inválido.")
            ids.add(session["id"])
            self.clean_name(session.get("name"))
            if type(session.get("deaths")) is not int or session["deaths"] < 0 or session.get("status") not in ("active", "won", "archived"):
                raise ValueError("Sessão salva inválida.")
            if not isinstance(session.get("started"), str) or type(session.get("pinned")) is not bool:
                raise ValueError("Histórico salvo inválido.")
            if session.get("ended") is not None and not isinstance(session["ended"], str):
                raise ValueError("Data de sessão inválida.")
        active = [s["id"] for s in d["sessions"] if s["status"] == "active"]
        if active != ([d["active_id"]] if d.get("active_id") else []):
            raise ValueError("Sessão ativa inconsistente.")
        d["settings"] = validate_settings(d["settings"])

    @staticmethod
    def clean_name(name):
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60 or any(c in name for c in "\r\n<>\x00"):
            raise ValueError("Digite um nome de 1 a 60 caracteres, em uma linha, sem < e >.")
        return name.strip()

    @property
    def active(self):
        return next((s for s in self.data["sessions"] if s["id"] == self.data["active_id"]), None)

    @property
    def settings(self):
        return self.data["settings"]

    def start(self, name):
        if self.active:
            raise ValueError("Encerre ou arquive o chefe atual antes de iniciar outro.")
        session = {"id": uuid.uuid4().hex, "name": self.clean_name(name), "deaths": 0, "started": now_iso(), "ended": None, "status": "active", "pinned": False}
        self.data["sessions"].append(session)
        self.data["active_id"] = session["id"]
        return session

    def finish(self, won=True):
        if not self.active:
            raise ValueError("Não há chefe ativo.")
        session = self.active
        session["status"] = "won" if won else "archived"
        session["ended"] = now_iso()
        self.data["active_id"] = None
        return session

    def set_count(self, target, value):
        if type(value) is not int or value < 0:
            raise ValueError("A contagem deve ser um inteiro maior ou igual a zero.")
        if target == "total":
            self.data["total"] = value
        else:
            session = next((s for s in self.data["sessions"] if s["id"] == target), None)
            if session is None:
                raise ValueError("Selecione um chefe.")
            session["deaths"] = value

    def adjust(self, target, delta):
        value = self.data["total"] if target == "total" else next((s["deaths"] for s in self.data["sessions"] if s["id"] == target), None)
        if value is None:
            raise ValueError("Não há chefe ativo.")
        self.set_count(target, max(0, value + delta))

    def record_death(self):
        if self.data["paused"]:
            return False
        self.data["total"] += 1
        if self.active:
            self.active["deaths"] += 1
        return True

    def overlay(self, status="Monitorando"):
        settings = self.settings
        lines = [settings["total_template"].format(total=self.data["total"])]
        if settings["show_boss"]:
            if self.active:
                lines.append(settings["boss_template"].format(nome=self.active["name"], mortes=self.active["deaths"]))
            for session in self.data["sessions"]:
                if session["pinned"] and session["status"] != "active":
                    lines.append(settings["boss_template"].format(nome=session["name"], mortes=session["deaths"]))
        if settings["show_status"]:
            lines.append("Detecção pausada" if self.data["paused"] else status)
        return "\n".join(lines)


class StateStore:
    def __init__(self, directory):
        self.path = Path(directory) / "state.json"
        self.backup = self.path.with_suffix(".json.bak")
        self.warning = None

    def load(self):
        for candidate in (self.path, self.backup):
            if not candidate.exists():
                continue
            try:
                journey = Journey(json.loads(candidate.read_text(encoding="utf-8")))
                if candidate == self.backup:
                    self.warning = "O arquivo principal estava indisponível. O backup foi recuperado."
                return journey
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.warning = f"Não foi possível ler {candidate.name}: {error}"
        if self.path.exists() or self.backup.exists():
            # Preserve damaged data before a future autosave replaces the file.
            for candidate in (self.path, self.backup):
                if candidate.exists():
                    shutil.copy2(candidate, candidate.with_name(candidate.name + ".invalid-" + uuid.uuid4().hex[:8]))
            self.warning = "Os dados não puderam ser recuperados. Uma cópia dos arquivos foi preservada na pasta de dados."
        return Journey()

    def save(self, journey):
        journey.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name("state-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(journey.data, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            if self.path.exists():
                try:
                    Journey(json.loads(self.path.read_text(encoding="utf-8")))
                except (ValueError, OSError, KeyError, TypeError):
                    pass
                else:
                    shutil.copy2(self.path, self.backup)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
