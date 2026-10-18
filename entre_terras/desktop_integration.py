"""Tray icon and RTSS lifecycle for the Windows desktop application."""
import ctypes as ct
from ctypes import wintypes as wt
import os
from pathlib import Path
import subprocess
import time
import winreg

import psutil
from PIL import Image
import pystray

from entre_terras.vision import BASE_DIR


def find_rtss():
    candidates = []
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\RTSS",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\RTSS"):
            try:
                with winreg.OpenKey(root, key) as handle:
                    candidates.append(Path(winreg.QueryValueEx(handle, "InstallLocation")[0]) / "RTSS.exe")
            except OSError:
                pass
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        candidates.append(Path(os.environ.get(variable, "C:/Program Files (x86)")) / "RivaTuner Statistics Server/RTSS.exe")
    return next((p for p in candidates if p.is_file()), None)


class RTSSLifecycle:
    def __init__(self):
        self.processes = []

    def start(self):
        executable = find_rtss()
        if executable is None:
            raise RuntimeError("Instale o RivaTuner Statistics Server (RTSS) antes de abrir o contador.")
        expected = str(executable.resolve()).casefold()
        for process in psutil.process_iter(["name", "exe"]):
            if (process.info["name"] or "").casefold() == "rtss.exe" and (process.info["exe"] or "").casefold() == expected:
                self.processes.append(process)
        if not self.processes:
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            launched = subprocess.Popen([str(executable)], startupinfo=startup,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
            self.processes.append(psutil.Process(launched.pid))
        kernel = ct.WinDLL("kernel32", use_last_error=True)
        kernel.OpenFileMappingW.argtypes = [wt.DWORD, wt.BOOL, wt.LPCWSTR]
        kernel.OpenFileMappingW.restype = wt.HANDLE
        kernel.CloseHandle.argtypes = [wt.HANDLE]
        for _ in range(80):
            handle = kernel.OpenFileMappingW(4, False, "RTSSSharedMemoryV2")
            if handle:
                kernel.CloseHandle(handle)
                return
            time.sleep(.1)
        raise RuntimeError("O RTSS não ficou pronto. Verifique se ele exige execução como administrador.")

    def close(self):
        # The user explicitly requested that RTSS exit with this application.
        user = ct.WinDLL("user32", use_last_error=True)
        callback_type = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        user.EnumWindows.argtypes = [callback_type, wt.LPARAM]
        user.GetWindowThreadProcessId.argtypes = [wt.HWND, ct.POINTER(wt.DWORD)]
        user.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        for process in self.processes:
            try:
                if not process.is_running():
                    continue
                def close_window(hwnd, _):
                    pid = wt.DWORD()
                    user.GetWindowThreadProcessId(hwnd, ct.byref(pid))
                    if pid.value == process.pid:
                        user.PostMessageW(hwnd, 0x0010, 0, 0)
                    return True
                user.EnumWindows(callback_type(close_window), 0)
                try:
                    process.wait(timeout=2)
                except psutil.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=2)
            except psutil.NoSuchProcess:
                pass
            except (psutil.AccessDenied, psutil.TimeoutExpired) as error:
                print(f"Não foi possível encerrar o RTSS: {error}")
        self.processes.clear()


class TrayIcon:
    def __init__(self, events):
        self.events = events
        with Image.open(BASE_DIR / "assets/entre-terras.ico") as image:
            picture = image.convert("RGBA")
        def send(action):
            return lambda icon, item: events.put(("tray", action))
        self.icon = pystray.Icon("EntreTerras", picture, "Entre Terras • Contador de mortes",
                                 menu=pystray.Menu(
                                     pystray.MenuItem("Abrir painel", send("show"), default=True),
                                     pystray.MenuItem("Pausar / retomar detecção", send("pause")),
                                     pystray.Menu.SEPARATOR,
                                     pystray.MenuItem("Encerrar contador e RTSS", send("quit"))))
        self.icon.run_detached()

    def close(self):
        self.icon.stop()
