"""Capture/detection worker; the UI and global shortcuts remain responsive."""
from pathlib import Path
import subprocess
import threading
import time

import cv2

from vision import DeathCounter, VisualDetector


def create_capture(settings, start_rtss=False):
    if settings["capture"] == "rtss":
        from rtss_capture import RTSSCapture
        try:
            return RTSSCapture()
        except RuntimeError:
            executable = Path("C:/Program Files (x86)/RivaTuner Statistics Server/RTSS.exe")
            if start_rtss and executable.exists():
                try:
                    subprocess.Popen([str(executable)], creationflags=subprocess.CREATE_NO_WINDOW)
                except OSError as error:
                    raise RuntimeError("Abra o RTSS pelo menu Iniciar para conectar ao jogo.") from error
                for attempt in range(10):
                    time.sleep(.2)
                    try:
                        return RTSSCapture()
                    except RuntimeError:
                        pass
            raise
    import dxcam
    return dxcam.create(output_idx=settings["monitor"], output_color="BGR", max_buffer_len=2)


def grab_frame(camera, backend, fresh_only=True):
    if backend == "rtss":
        return camera.grab()
    w, h = camera.width, camera.height
    return camera.grab(region=(int(w*.1), int(h*.35), int(w*.9), int(h*.65)), new_frame_only=fresh_only)


class CaptureWorker:
    def __init__(self, events, reference, settings, paused=False, debug=False):
        self.events = events
        self.reference = reference
        self.lock = threading.Lock()
        self.settings = dict(settings)
        self.paused = paused
        self.overlay = "Mortes totais: 0\nConectando"
        self.stop_event = threading.Event()
        self.debug = debug
        self.thread = threading.Thread(target=self._run, name="GameCapture", daemon=True)
        self.thread.start()

    def configure(self, settings, paused):
        with self.lock:
            self.settings = dict(settings)
            self.paused = paused

    def set_overlay(self, text):
        with self.lock:
            self.overlay = text

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=3)

    def _run(self):
        camera = None
        connection = None
        gate_config = None
        last_frame = None
        last_overlay = None
        next_retry = 0.
        start_attempted = False
        detector = None
        gate = None
        message = "Conectando ao jogo"
        score = 0.
        try:
            # Avoid competing with the game's CPU threads for these small images.
            cv2.setNumThreads(1)
            detector = VisualDetector(self.reference)
            while not self.stop_event.is_set():
                began = time.monotonic()
                with self.lock:
                    settings = dict(self.settings)
                    paused = self.paused
                    overlay = self.overlay
                requested = settings["capture"], settings["monitor"]
                new_gate = settings["confirmation_frames"], settings["clear_seconds"]
                if gate_config != new_gate:
                    gate = DeathCounter(*new_gate)
                    gate_config = new_gate
                detector.threshold = settings["threshold"]
                if connection != requested:
                    gate.interrupt()
                    if camera:
                        camera.release()
                    camera = None
                    last_frame = None
                    last_overlay = None
                    connection = requested
                    next_retry = 0.
                if camera is None and began >= next_retry:
                    try:
                        camera = create_capture(settings, start_rtss=not start_attempted)
                        start_attempted = True
                        last_overlay = None
                    except Exception as error:
                        start_attempted = True
                        message = str(error)
                        next_retry = began + 3
                if camera is not None:
                    try:
                        if paused:
                            gate.interrupt()
                            cancel = getattr(camera, "cancel_pending", None)
                            if cancel:
                                cancel()
                        frame = None if paused else grab_frame(camera, settings["capture"])
                        if frame is not None:
                            last_frame = time.monotonic()
                            score = detector.score(frame)
                            fired = gate.update(score >= detector.threshold, last_frame)
                            if fired and not paused:
                                self.events.put(("death",))
                            message = "Monitorando"
                            if self.debug:
                                cv2.imshow("Captura visual", frame)
                                cv2.waitKey(1)
                        elif last_frame is None:
                            message = getattr(camera, "status", "Aguardando imagem do jogo")
                        elif began - last_frame > 3:
                            message = "Sem imagem do jogo"
                    except Exception as error:
                        gate.interrupt()
                        message = str(error)
                        # RTSS may have restarted, or the display mode changed.
                        try:
                            camera.release()
                        except Exception:
                            pass
                        camera = None
                        next_retry = began + 3
                    if camera is not None and settings["capture"] == "rtss" and overlay != last_overlay:
                        try:
                            if camera.update_osd(overlay):
                                last_overlay = overlay
                        except Exception as error:
                            message = str(error)
                            try:
                                camera.release()
                            except Exception:
                                pass
                            camera = None
                            next_retry = began + 3
                self.events.put(("health", "Detecção pausada" if paused else message, score, last_frame is not None and began-last_frame < 3))
                # Once counted, one sample/s is sufficient to watch for clearing.
                # Keep polling while paused so overlay and settings remain live.
                fps = min(settings["fps"], 1) if gate.active and not paused else settings["fps"]
                interval = max(.01, 1 / fps - (time.monotonic()-began))
                self.stop_event.wait(interval)
        except Exception as error:
            self.events.put(("health", f"Falha na captura: {error}", 0., False))
        finally:
            if camera:
                camera.release()
            if self.debug:
                cv2.destroyAllWindows()
