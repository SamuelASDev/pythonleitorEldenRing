import queue
import threading
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch
from entre_terras.tracker_runtime import CaptureWorker
from entre_terras.tracker_state import DEFAULTS


class WorkerTests(unittest.TestCase):
    def run_worker(self, paused=False, osd_error=False):
        worker = CaptureWorker.__new__(CaptureWorker)
        worker.events = queue.Queue()
        worker.reference = 'entre_terras/assets/death-message.png'
        worker.lock = threading.Lock()
        worker.settings = deepcopy(DEFAULTS)
        worker.paused = paused
        worker.overlay = 'Mortes: 0'
        worker.debug = False
        worker.stop_event = threading.Event()
        worker.stop_event.wait = lambda interval: worker.stop_event.set()
        camera = Mock()
        camera.grab.return_value = None
        if osd_error:
            camera.update_osd.side_effect = RuntimeError('OSD indisponivel')
        with patch('entre_terras.tracker_runtime.create_capture', return_value=camera):
            worker._run()
        return worker, camera

    def test_paused_worker_keeps_osd_without_capturing(self):
        worker, camera = self.run_worker(paused=True)
        camera.grab.assert_not_called()
        camera.cancel_pending.assert_called_once()
        camera.update_osd.assert_called_once_with('Mortes: 0')
        camera.release.assert_called_once()

    def test_osd_failure_is_handled_without_fatal_worker_error(self):
        worker, camera = self.run_worker(osd_error=True)
        camera.release.assert_called_once()
        events = list(worker.events.queue)
        self.assertTrue(any(event[0] == 'health' for event in events))
        self.assertFalse(any('Falha na captura:' in str(event) for event in events))
