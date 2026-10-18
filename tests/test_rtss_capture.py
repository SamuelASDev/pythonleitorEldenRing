import ctypes as ct
import csv
import io
from pathlib import Path
import struct
import tempfile
import time
import unittest
import subprocess

import cv2
import numpy as np

from entre_terras.rtss_capture import AppEntry, CaptureDirectory, RTSSCapture


class CaptureDirectoryTests(unittest.TestCase):
    def test_capture_directory_inherits_permissions_and_is_cleaned(self):
        directory = CaptureDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        # Check the user SID, not the (I) display marker: some Windows/Python
        # versions materialize inherited permissions as explicit ACEs.
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                  capture_output=True, check=True)
        sid = next(csv.reader(io.StringIO(identity.stdout.decode("mbcs"))))[1]
        with tempfile.TemporaryDirectory() as temporary:
            saved_acl = Path(temporary) / "acl.txt"
            subprocess.run(["icacls", str(path), "/save", str(saved_acl)],
                           capture_output=True, check=True)
            self.assertIn(sid, saved_acl.read_text(encoding="utf-16-le"))
        (path / "frame.bmp").write_bytes(b"capture")
        directory.cleanup()
        self.assertFalse(path.exists())


class RTSSProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.memory = ct.create_string_buffer(40 + ct.sizeof(AppEntry))
        ct.c_uint32.from_buffer(self.memory).value = 0x52545353
        self.entry = AppEntry.from_buffer(self.memory, 40)
        self.entry.pid = 123
        self.entry.name = b"C:\\Games\\eldenring.exe"
        self.capture = RTSSCapture.__new__(RTSSCapture)
        self.capture.address = ct.addressof(self.memory)
        self.capture.count = 1
        self.capture.offset = 40
        self.capture.stride = ct.sizeof(AppEntry)
        self.capture.process_name = "eldenring.exe"
        self.capture.path = Path(self.temp.name) / "frame.bmp"
        self.capture.path_bytes = str(self.capture.path).encode("mbcs")
        self.capture.pending = None

    def test_sdk_offsets(self):
        self.assertEqual(AppEntry.capture_flags.offset, 336)
        self.assertEqual(AppEntry.capture_path.offset, 340)

    def test_request_complete_frame_and_requeue(self):
        self.assertIsNone(self.capture.grab())
        self.assertEqual(self.entry.capture_flags, 1)
        self.assertEqual(bytes(self.entry.capture_path), self.capture.path_bytes)
        # Simulate the RTSS screenshot writer completing the request.
        image = np.full((1080, 1920, 3), (15, 25, 35), np.uint8)
        self.assertTrue(cv2.imwrite(str(self.capture.path), image))
        self.entry.capture_flags = 0
        result = self.capture.grab()
        self.assertEqual(result.shape, (324, 1536, 3))
        self.assertEqual(tuple(result[0, 0]), (15, 25, 35))
        self.assertEqual(self.entry.capture_flags, 1)

    def test_partial_frame_is_not_a_negative_detection(self):
        self.capture.grab()
        self.capture.path.write_bytes(b"BM" + struct.pack("<I", 5000) + bytes(100))
        self.assertIsNone(self.capture.grab())

    def test_other_request_is_not_overwritten(self):
        self.entry.capture_flags = 1
        self.entry.capture_path = b"other.bmp"
        self.assertIsNone(self.capture.grab())
        self.assertEqual(bytes(self.entry.capture_path), b"other.bmp")

    def test_missing_game_does_not_request_capture(self):
        self.entry.name = b"different.exe"
        self.assertIsNone(self.capture.grab())
        self.assertEqual(self.entry.capture_flags, 0)

    def test_timeout_allows_retry(self):
        self.capture.grab()
        self.capture.pending = time.monotonic() - 6
        with self.assertRaises(RuntimeError):
            self.capture.grab()
        self.assertIsNone(self.capture.pending)
        self.assertEqual(self.entry.capture_flags, 0)
        self.capture.grab()
        self.assertEqual(self.entry.capture_flags, 1)

    def test_pause_cancels_own_pending_request(self):
        self.capture.grab()
        self.capture.cancel_pending()
        self.assertIsNone(self.capture.pending)
        self.assertEqual(self.entry.capture_flags, 0)

    def test_pause_preserves_another_clients_request(self):
        self.capture.grab()
        self.entry.capture_path = b"other.bmp"
        self.capture.cancel_pending()
        self.assertEqual(self.entry.capture_flags, 1)
        self.assertEqual(bytes(self.entry.capture_path), b"other.bmp")


class RTSSOverlayTests(unittest.TestCase):
    def setUp(self):
        self.stride = 4608
        self.memory = ct.create_string_buffer(96 + self.stride * 4)
        ct.c_uint32.from_buffer(self.memory).value = 0x52545353
        self.capture = RTSSCapture.__new__(RTSSCapture)
        self.capture.address = ct.addressof(self.memory)
        self.capture.osd_offset = 96
        self.capture.osd_stride = self.stride
        self.capture.osd_count = 4
        self.capture.osd_owner = b"test-counter"
        self.primary = self.capture.address + 96
        ct.memmove(self.primary + 256, b"Afterburner", 11)
        self.busy = ct.c_uint32.from_address(self.capture.address + 36)

    def test_publish_update_release_preserves_other_clients(self):
        self.assertTrue(self.capture.update_osd("Mortes: 0\nMonitorando"))
        slot = self.primary + self.stride
        self.assertEqual(ct.string_at(slot + 256), b"test-counter")
        self.assertEqual(ct.string_at(slot + 512), b"Mortes: 0\nMonitorando")
        self.assertTrue(self.capture.update_osd("Mortes: 1"))
        self.assertEqual(ct.string_at(slot + 512), b"Mortes: 1")
        self.assertTrue(self.capture.update_osd(None))
        self.assertEqual(ct.string_at(slot + 256), b"")
        self.assertEqual(ct.string_at(slot + 512), b"")
        self.assertEqual(ct.string_at(self.primary + 256), b"Afterburner")
        self.assertEqual(self.busy.value, 0)

    def test_busy_renderer_is_not_overwritten_or_unlocked(self):
        self.busy.value = 1
        self.assertFalse(self.capture.update_osd("Mortes: 0"))
        self.assertEqual(self.busy.value, 1)
        self.assertEqual(ct.string_at(self.primary + self.stride + 256), b"")

    def test_full_slots_are_not_overwritten(self):
        for index in range(1, 4):
            ct.memmove(self.primary + index * self.stride + 256, b"other", 5)
        self.assertFalse(self.capture.update_osd("Mortes: 0"))
        self.assertEqual(self.busy.value, 0)
