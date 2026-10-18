"""Windows global shortcuts via RegisterHotKey; no keyboard hook."""
import ctypes as ct
from ctypes import wintypes as wt
import queue
import threading

from entre_terras.tracker_state import HOTKEY_LABELS

MODIFIERS = {"CTRL": 2, "ALT": 1, "SHIFT": 4, "WIN": 8}
NAMED_KEYS = {"PAGEUP": 0x21, "PAGEDOWN": 0x22, "HOME": 0x24, "END": 0x23,
              "INSERT": 0x2D, "DELETE": 0x2E, "SPACE": 0x20,
              "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28}


def parse_hotkey(text):
    if not text.strip():
        return None
    parts = [p.strip().upper() for p in text.split("+")]
    if any(not p for p in parts) or len(parts) < 2:
        raise ValueError("Use um modificador e uma tecla, por exemplo Ctrl+Alt+F8.")
    modifiers = 0
    for part in parts[:-1]:
        if part not in MODIFIERS or modifiers & MODIFIERS[part]:
            raise ValueError("Modificadores válidos: Ctrl, Alt, Shift e Win, sem repetição.")
        modifiers |= MODIFIERS[part]
    key = parts[-1]
    if len(key) == 1 and key in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        code = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        code = 0x70 + int(key[1:]) - 1
    elif key in NAMED_KEYS:
        code = NAMED_KEYS[key]
    else:
        raise ValueError("Tecla inválida. Use letras, números, F1–F24, Home, End, PageUp ou PageDown.")
    return modifiers, code


def validate_hotkeys(mapping):
    parsed = {}
    used = set()
    for action, text in mapping.items():
        try:
            combination = parse_hotkey(text)
        except ValueError as error:
            raise ValueError(f"{HOTKEY_LABELS[action]}: {error}") from error
        if combination is not None:
            if combination in used:
                raise ValueError(f"Atalho repetido: {text}.")
            used.add(combination)
            parsed[action] = combination
    return parsed


class GlobalHotkeys:
    def __init__(self, events):
        self.events = events
        self.commands = queue.Queue()
        self.thread = threading.Thread(target=self._run, name="GlobalHotkeys", daemon=True)
        self.thread.start()

    def configure(self, mapping, token=None):
        self.commands.put(("configure", dict(mapping), token))

    def close(self):
        self.commands.put(("stop", None, None))
        self.thread.join(timeout=2)

    def _run(self):
        api = ct.WinDLL("user32", use_last_error=True)
        api.RegisterHotKey.argtypes = [wt.HWND, ct.c_int, wt.UINT, wt.UINT]
        api.RegisterHotKey.restype = wt.BOOL
        api.UnregisterHotKey.argtypes = [wt.HWND, ct.c_int]
        api.UnregisterHotKey.restype = wt.BOOL
        api.PeekMessageW.argtypes = [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
        api.PeekMessageW.restype = wt.BOOL
        # Establish a queue on this dedicated thread. Tk cannot consume its messages.
        message = wt.MSG()
        api.PeekMessageW(ct.byref(message), None, 0, 0, 0)
        registered = {}
        old = {}

        def clear():
            for identifier in list(registered):
                api.UnregisterHotKey(None, identifier)
            registered.clear()

        def register(parsed):
            failures = []
            for index, (action, (modifiers, key)) in enumerate(parsed.items(), 1):
                identifier = 0x1100 + index
                if api.RegisterHotKey(None, identifier, modifiers | 0x4000, key):
                    registered[identifier] = action
                else:
                    failures.append(HOTKEY_LABELS[action])
            return failures

        try:
            while True:
                try:
                    command, mapping, token = self.commands.get(timeout=.025)
                except queue.Empty:
                    command = None
                if command == "stop":
                    break
                if command == "configure":
                    try:
                        parsed = validate_hotkeys(mapping)
                        clear()
                        failures = register(parsed)
                        if failures:
                            clear()
                            rollback_failures = register(old)
                            reason = "Atalhos já usados por outro programa: " + ", ".join(failures) + ". Escolha outras combinações."
                            if rollback_failures:
                                reason += " Alguns atalhos anteriores também ficaram indisponíveis."
                            self.events.put(("hotkeys_result", token, False, reason))
                        else:
                            old = parsed
                            self.events.put(("hotkeys_result", token, True, "Atalhos globais ativos"))
                    except ValueError as error:
                        self.events.put(("hotkeys_result", token, False, str(error)))
                while api.PeekMessageW(ct.byref(message), None, 0x0312, 0x0312, 1):
                    action = registered.get(message.wParam)
                    if action:
                        self.events.put(("hotkey", action))
        finally:
            clear()
