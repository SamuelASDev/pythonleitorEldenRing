from pathlib import Path
import sys

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR.parent


def red_mask(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    selected = cv2.inRange(hsv, (0, 75, 15), (12, 255, 255)) | cv2.inRange(hsv, (168, 75, 15), (179, 255, 255))
    blue, green, red = cv2.split(image)
    # Preserve antialiased edges; normalized correlation tolerates fading text.
    redness = cv2.subtract(red, cv2.max(blue, green))
    return cv2.bitwise_and(redness, redness, mask=selected)


class VisualDetector:
    def __init__(self, reference, threshold=0.70):
        image = cv2.imdecode(np.fromfile(reference, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot read reference: {reference}")
        mask = red_mask(image)
        points = cv2.findNonZero(mask)
        if points is None:
            raise ValueError("Reference must contain the red death message.")
        x, y, w, h = cv2.boundingRect(points)
        mask = mask[y:y+h, x:x+w]
        self.templates = []
        # Search different message sizes; matching stays at a small working resolution.
        for width in np.geomspace(40, 289, 36):
            width = int(width)
            height = max(5, round(mask.shape[0] * width / mask.shape[1]))
            template = cv2.resize(mask, (width, height), interpolation=cv2.INTER_AREA)
            self.templates.append(template)
        self.threshold = threshold

    def score(self, frame):
        height = max(1, round(frame.shape[0] * 320 / frame.shape[1]))
        small = cv2.resize(frame, (320, height), interpolation=cv2.INTER_AREA)
        mask = red_mask(small)
        if cv2.countNonZero(mask) < 40:
            return 0.0
        best = 0.0
        for template in self.templates:
            if template.shape[0] > mask.shape[0]:
                continue
            result = cv2.matchTemplate(mask, template, cv2.TM_CCOEFF_NORMED)
            best = max(best, float(cv2.minMaxLoc(result)[1]))
        return best


class DeathCounter:
    def __init__(self, confirmation_frames=2, clear_seconds=2.0):
        self.count = 0
        self.hits = 0
        self.active = False
        self.clear_since = None
        self.confirmation_frames = confirmation_frames
        self.clear_seconds = clear_seconds
        self.last_sample = None

    def interrupt(self):
        # Keep the latch: reconnecting on the same death must not count twice.
        self.hits = 0
        self.clear_since = None
        self.last_sample = None

    def update(self, detected, now):
        if self.last_sample is not None and now - self.last_sample > 3:
            self.interrupt()
        self.last_sample = now
        if detected:
            self.clear_since = None
            self.hits += 1
            if not self.active and self.hits >= self.confirmation_frames:
                self.count += 1
                self.active = True
                return True
        else:
            self.hits = 0
            if self.active:
                if self.clear_since is None:
                    self.clear_since = now
                if now - self.clear_since >= self.clear_seconds:
                    self.active = False
        return False


