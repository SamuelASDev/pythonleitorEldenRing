"""Screenshot requests via the installed RTSS SDK shared-memory protocol.

Layout: RTSS SDK/Include/RTSSSharedMemory.h, v2 APP_ENTRY prefix.
Only RTSS-owned shared memory is opened; game processes are never opened here.
"""
import ctypes as ct
from ctypes import wintypes as wt
from pathlib import Path
import struct
import tempfile
import time
import os
import shutil
import uuid

import atomics

import cv2
import numpy as np


class CaptureDirectory:
    """Inherit the user's TEMP permissions so the unelevated renderer can write.

    Python's TemporaryDirectory uses mode 0700. On Windows, when created by
    our elevated process, that can exclude the game's normal user token.
    """
    def __init__(self):
        path = Path(tempfile.gettempdir()) / f"elden_rtss_{uuid.uuid4().hex}"
        path.mkdir(mode=0o777)
        self.name = str(path)

    def cleanup(self):
        try:
            shutil.rmtree(self.name)
        except FileNotFoundError:
            pass


class AppEntry(ct.Structure):
    _fields_ = [
        ("pid", ct.c_uint32), ("name", ct.c_char * 260),
        ("flags", ct.c_uint32), ("timing", ct.c_uint32 * 4),
        ("statistics", ct.c_uint32 * 8), ("osd", ct.c_uint32 * 5),
        ("capture_flags", ct.c_uint32), ("capture_path", ct.c_char * 260),
    ]


class RTSSCapture:
    def __init__(self, process_name="eldenring.exe"):
        self.process_name = process_name.casefold()
        self.api = ct.WinDLL("kernel32", use_last_error=True)
        self.api.OpenFileMappingW.argtypes = [wt.DWORD, wt.BOOL, wt.LPCWSTR]
        self.api.OpenFileMappingW.restype = wt.HANDLE
        self.api.MapViewOfFile.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD, ct.c_size_t]
        self.api.MapViewOfFile.restype = ct.c_void_p
        self.api.UnmapViewOfFile.argtypes = [ct.c_void_p]
        self.api.UnmapViewOfFile.restype = wt.BOOL
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.api.CloseHandle.restype = wt.BOOL
        self.handle = None
        self.address = None
        self.pending = None
        self.osd_owner = f"EldenDeathCounter-{os.getpid()}".encode("ascii")
        self.width = self.height = 0
        self.directory = CaptureDirectory()
        self.path = Path(self.directory.name) / "frame.bmp"
        self.path_bytes = str(self.path).encode("mbcs", errors="strict")
        if len(self.path_bytes) >= 260:
            self.directory.cleanup()
            raise RuntimeError("RTSS capture path exceeds MAX_PATH.")
        self.status = "Aguardando RTSS"
        try:
            self._connect()
        except Exception:
            self.release()
            raise

    def _connect(self):
        self.handle = self.api.OpenFileMappingW(0xF001F, False, "RTSSSharedMemoryV2")
        if not self.handle:
            raise RuntimeError("Abra o RivaTuner Statistics Server (RTSS) antes do contador.")
        header = self.api.MapViewOfFile(self.handle, 0xF001F, 0, 0, 40)
        if not header:
            raise ct.WinError(ct.get_last_error())
        try:
            values = struct.unpack("<10I", ct.string_at(header, 40))
        finally:
            self.api.UnmapViewOfFile(header)
        signature, version, self.stride, self.offset, self.count = values[:5]
        self.osd_stride, self.osd_offset, self.osd_count = values[5:8]
        if signature != 0x52545353 or version < 0x2000E:
            raise RuntimeError("RTSS shared memory is not initialized.")
        if not (600 <= self.stride <= 1048576 and 0 < self.count <= 4096 and 40 <= self.offset <= 64 * 1048576):
            raise RuntimeError("Unsupported RTSS shared-memory layout.")
        if not (4608 <= self.osd_stride <= 1048576 and 1 <= self.osd_count <= 256 and 40 <= self.osd_offset <= 64 * 1048576):
            raise RuntimeError("Unsupported RTSS OSD layout.")
        length = max(self.offset + self.stride * self.count, self.osd_offset + self.osd_stride * self.osd_count)
        if length > 128 * 1024 * 1024:
            raise RuntimeError("Invalid RTSS application array size.")
        self.address = self.api.MapViewOfFile(self.handle, 0xF001F, 0, 0, length)
        if not self.address:
            raise ct.WinError(ct.get_last_error())

    def update_osd(self, text=None):
        """Publish our own OSD slot, preserving the Afterburner slot and lock.

        None releases our slot. A busy renderer is retried on the next tick.
        """
        if ct.c_uint32.from_address(self.address).value != 0x52545353:
            return False
        lock_buffer = (ct.c_ubyte * 4).from_address(self.address + 36)
        with atomics.atomicview(buffer=lock_buffer, atype=atomics.UINT) as lock:
            if not lock.cmpxchg_strong(0, 1).success:
                return False
            try:
                owned = None
                free = None
                # Slot zero is reserved for the primary client (Afterburner).
                for index in range(1, self.osd_count):
                    slot = self.address + self.osd_offset + index * self.osd_stride
                    owner = ct.string_at(slot + 256, 256).split(b"\0", 1)[0]
                    if owner == self.osd_owner:
                        owned = slot
                        break
                    if not owner and free is None:
                        free = slot
                slot = owned if owned is not None else free
                if text is None:
                    if owned is None:
                        return True
                    ct.memset(owned, 0, self.osd_stride)
                else:
                    if slot is None:
                        return False
                    if owned is None:
                        ct.memset(slot, 0, self.osd_stride)
                        ct.memmove(slot + 256, self.osd_owner, len(self.osd_owner))
                    encoded = text.encode("mbcs", errors="replace")[:4095]
                    ct.memset(slot + 512, 0, 4096)
                    ct.memmove(slot + 512, encoded, len(encoded))
                frame = ct.c_uint32.from_address(self.address + 32)
                frame.value = (frame.value + 1) & 0xFFFFFFFF
                return True
            finally:
                lock.store(0)

    def _entry(self):
        signature = ct.c_uint32.from_address(self.address).value
        if signature != 0x52545353:
            raise RuntimeError("RTSS foi encerrado. Reinicie o RTSS e o contador.")
        for index in range(self.count):
            entry = AppEntry.from_address(self.address + self.offset + index * self.stride)
            name = bytes(entry.name).decode("mbcs", errors="replace").replace("\\", "/").rsplit("/", 1)[-1]
            if entry.pid and name.casefold() == self.process_name:
                return entry
        return None

    def grab(self, region=None, **kwargs):
        entry = self._entry()
        if entry is None:
            self.status = "Aguardando jogo no RTSS (reinicie o jogo)"
            return None
        now = time.monotonic()
        frame = None
        if self.pending is not None:
            if self.path.exists():
                try:
                    data = np.fromfile(self.path, dtype=np.uint8)
                    # BMP header carries the complete file size. Don't accept a
                    # partially written screenshot as a real negative frame.
                    if data.size >= 54 and data[:2].tobytes() == b"BM" and struct.unpack_from("<I", data, 2)[0] == data.size:
                        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
                except (OSError, cv2.error):
                    pass  # The screenshot may still be being written.
            if frame is None:
                self.status = "Aguardando captura do RTSS"
                if now - self.pending > 5:
                    self.pending = None
                    if bytes(entry.capture_path) == self.path_bytes:
                        entry.capture_flags &= ~1
                    raise RuntimeError("RTSS sem quadros ha 5 s. Verifique o perfil do jogo no RTSS.")
                return None
            self.pending = None
            self.height, self.width = frame.shape[:2]
            self.status = "Capturando pelo RTSS"
        # Don't overwrite another application's screenshot request.
        if not entry.capture_flags & 1:
            self.path.unlink(missing_ok=True)
            entry.capture_path = self.path_bytes
            entry.capture_flags = 1  # SCREENCAPTUREFLAG_REQUEST_CAPTURE, without OSD.
            self.pending = now
        if frame is None:
            return None
        h, w = frame.shape[:2]
        return frame[int(h * .35):int(h * .65), int(w * .10):int(w * .90)]

    def cancel_pending(self):
        """Stop requesting screenshots while paused, retaining the OSD slot."""
        if self.pending is None:
            return
        entry = self._entry()
        if entry is not None and bytes(entry.capture_path) == self.path_bytes:
            entry.capture_flags &= ~1
        self.pending = None
        # A renderer already writing may still finish one outstanding image.

    def release(self):
        if self.address:
            # The renderer may briefly hold the OSD lock while closing.
            if hasattr(self, "osd_owner"):
                for attempt in range(10):
                    if self.update_osd(None):
                        break
                    time.sleep(0.01)
            # Cancel only our own outstanding request; leave other clients alone.
            try:
                entry = self._entry()
                if entry is not None and bytes(entry.capture_path) == self.path_bytes:
                    entry.capture_flags &= ~1
            except Exception:
                pass
            self.api.UnmapViewOfFile(self.address)
            self.address = None
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
        self.directory.cleanup()
