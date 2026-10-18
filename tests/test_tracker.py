import unittest

import cv2
import numpy as np

from elden_ring_tracker import BASE_DIR, DeathCounter, VisualDetector


class VisualDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = VisualDetector(BASE_DIR / "3.png")
        cls.reference = cv2.imdecode(np.fromfile(BASE_DIR / "3.png", dtype=np.uint8), cv2.IMREAD_COLOR)

    def test_message_at_different_sizes_and_brightness(self):
        for scale in (0.65, 1.0, 1.5, 2.0):
            for brightness in (0.65, 1.0):
                with self.subTest(scale=scale, brightness=brightness):
                    frame = np.full((324, 1536, 3), (32, 38, 40), dtype=np.uint8)
                    message = cv2.resize(self.reference, None, fx=scale, fy=scale)
                    message = (message * brightness).astype(np.uint8)
                    h, w = message.shape[:2]
                    frame[100:100+h, 768-w//2:768-w//2+w] = message
                    self.assertGreaterEqual(self.detector.score(frame), self.detector.threshold)

    def test_negative_screens(self):
        rng = np.random.default_rng(42)
        wrong_text = np.zeros((324, 1536, 3), np.uint8)
        cv2.putText(wrong_text, "INIMIGO DERROTADO", (300, 170), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 180), 3)
        for image in (
            np.zeros((324, 1536, 3), np.uint8),
            np.full((324, 1536, 3), (0, 0, 180), np.uint8),
            rng.integers(0, 256, (324, 1536, 3), dtype=np.uint8),
            wrong_text,
        ):
            self.assertLess(self.detector.score(image), self.detector.threshold)


class CounterTests(unittest.TestCase):
    def test_capture_gap_expires_pending_confirmation(self):
        counter = DeathCounter()
        self.assertFalse(counter.update(True, 0))
        self.assertFalse(counter.update(True, 60))
        self.assertTrue(counter.update(True, 60.5))

    def test_interrupt_keeps_counted_death_latched(self):
        counter = DeathCounter()
        counter.update(True, 0)
        counter.update(True, .5)
        counter.interrupt()
        self.assertFalse(counter.update(True, 60))
        self.assertFalse(counter.update(True, 60.5))
        self.assertEqual(counter.count, 1)

    def test_confirmation_flicker_and_rearm(self):
        counter = DeathCounter()
        self.assertFalse(counter.update(True, 0))
        self.assertTrue(counter.update(True, 0.2))
        for now in (0.4, 1, 2, 5):
            self.assertFalse(counter.update(True, now))
        counter.update(False, 5.2)
        counter.update(False, 6)
        counter.update(True, 6.2)
        self.assertEqual(counter.count, 1)
        counter.update(False, 7)
        counter.update(False, 9.1)
        self.assertFalse(counter.update(True, 9.3))
        self.assertTrue(counter.update(True, 9.5))
        self.assertEqual(counter.count, 2)

    def test_isolated_positive_does_not_count(self):
        counter = DeathCounter()
        for now in range(10):
            counter.update(now % 2 == 0, now)
        self.assertEqual(counter.count, 0)


if __name__ == "__main__":
    unittest.main()
