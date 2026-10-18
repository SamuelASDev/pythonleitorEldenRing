"""Entry point for the Entre Terras desktop counter."""
import argparse
import ctypes as ct
from ctypes import wintypes as wt
import hashlib
from pathlib import Path
import time
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

# Kept available here for existing integrations and tests.
from entre_terras.vision import APP_DIR, BASE_DIR, DeathCounter, VisualDetector
from entre_terras.tracker_state import StateStore, validate_settings
from entre_terras.user_data import default_data_dir, migrate_legacy_data


def main():
    parser = argparse.ArgumentParser(description="Entre Terras - visual death counter")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--check", action="store_true", help="Test the selected capture backend")
    parser.add_argument("--run-seconds", type=float)
    parser.add_argument("--capture", choices=("rtss", "dxgi"))
    parser.add_argument("--monitor", type=int)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--reference", type=Path, default=BASE_DIR / "assets/death-message.png")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--show", action="store_true", help="Abrir com o painel visível")
    args = parser.parse_args()
    use_default_data = args.data_dir is None
    args.data_dir = (args.data_dir or default_data_dir()).resolve()
    if not args.check and not ct.windll.shell32.IsUserAnAdmin():
        # RTSS requires elevation on this installation, including for shutdown.
        parameters = sys.argv[1:] if getattr(sys, "frozen", False) else ["-m", "entre_terras", *sys.argv[1:]]
        if use_default_data:
            parameters += ["--data-dir", str(args.data_dir)]
        shell = ct.WinDLL("shell32", use_last_error=True)
        shell.ShellExecuteW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ct.c_int]
        shell.ShellExecuteW.restype = ct.c_ssize_t
        result = shell.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline(parameters), str(APP_DIR), 0)
        if result <= 32:
            messagebox.showerror("Entre Terras", "A permissão de administrador é necessária para abrir e encerrar o RTSS junto com o contador.")
            return 1
        return 0
    if sys.stdout is None or sys.stderr is None:
        args.data_dir.mkdir(parents=True, exist_ok=True)
        log = (args.data_dir / "app.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    if not args.check:
        candidates = [APP_DIR / "data"]
        if getattr(sys, "frozen", False) and APP_DIR.parent.name == "dist":
            candidates.append(APP_DIR.parent.parent / "data")
        # An explicit data directory keeps portable installations independent.
        if use_default_data or args.data_dir == default_data_dir().resolve():
            migrate_legacy_data(args.data_dir, candidates)
    first_run = not (args.data_dir / "state.json").exists()
    store = StateStore(args.data_dir)
    camera = None
    mutex = None
    running_mutex = None
    kernel = None
    root = None
    rtss = None
    app = None
    try:
        if not args.check:
            kernel = ct.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = [ct.c_void_p, wt.BOOL, wt.LPCWSTR]
            kernel.CreateMutexW.restype = wt.HANDLE
            kernel.CloseHandle.argtypes = [wt.HANDLE]
            name = "Local\\EntreTerras-" + hashlib.sha256(str(store.path.resolve()).casefold().encode()).hexdigest()[:20]
            mutex = kernel.CreateMutexW(None, False, name)
            if not mutex:
                raise ct.WinError(ct.get_last_error())
            if ct.get_last_error() == 183:
                messagebox.showinfo("Entre Terras", "O contador já está aberto. Use o ícone Entre Terras na bandeja, perto do relógio, para abrir o painel.")
                return 0
            running_mutex = kernel.CreateMutexW(None, False, "Local\\EntreTerras-Running")
            if not running_mutex:
                raise ct.WinError(ct.get_last_error())
        journey = store.load()
        for key in ("capture", "monitor", "fps", "threshold"):
            value = getattr(args, key)
            if value is not None:
                journey.settings[key] = value
        journey.data["settings"] = validate_settings(journey.settings)
        if args.check:
            from entre_terras.tracker_runtime import create_capture, grab_frame
            detector = VisualDetector(args.reference, journey.settings["threshold"])
            camera = create_capture(journey.settings, start_rtss=True)
            deadline = time.monotonic() + 8
            frame = None
            while frame is None and time.monotonic() < deadline:
                frame = grab_frame(camera, journey.settings["capture"], fresh_only=False)
                if frame is None:
                    time.sleep(.2)
            if frame is None:
                raise RuntimeError(getattr(camera, "status", "No frame available"))
            print(f"OK: {journey.settings['capture']} capture; {frame.shape[1]}x{frame.shape[0]}; score {detector.score(frame):.3f}")
            return 0
        from entre_terras.tracker_ui import ControlPanel
        from entre_terras.desktop_integration import RTSSLifecycle, ensure_rtss_installed
        if not ensure_rtss_installed():
            return 1
        rtss = RTSSLifecycle()
        rtss.start()
        ct.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EntreTerras.DeathCounter.Desktop")
        root = tk.Tk()
        root.withdraw()
        app = ControlPanel(root, journey, store, args.reference, args.debug)
        if args.show or first_run:
            app.show_window()
        if args.run_seconds is not None:
            root.after(max(1, round(args.run_seconds * 1000)), app.close)
        root.mainloop()
        return 0
    except Exception as error:
        print(f"Error: {error}")
        if not args.check:
            messagebox.showerror("Entre Terras", str(error), parent=root)
        return 1
    finally:
        if app and not app.closed:
            app.close()
        if camera:
            camera.release()
        if rtss:
            rtss.close()
        if mutex:
            kernel.CloseHandle(mutex)
        if running_mutex:
            kernel.CloseHandle(running_mutex)
        if root:
            try:
                root.destroy()
            except tk.TclError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
