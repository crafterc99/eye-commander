"""9-point calibration logic — collects iris samples and saves calibration.json."""

import json
import os
import numpy as np
import config


# 9-point grid positions as fractions of screen (col, row)
GRID_POSITIONS = [
    (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
    (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),
    (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
]


class Calibration:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._data = []   # list of (iris_norm, screen_pos)

    def dot_screen_positions(self):
        return [
            (int(fx * self.screen_w), int(fy * self.screen_h))
            for fx, fy in GRID_POSITIONS
        ]

    def record_sample(self, dot_index, iris_samples, frame_w, frame_h):
        """
        iris_samples: list of (raw_x, raw_y) pixel positions in frame
        """
        if not iris_samples:
            return
        arr = np.array(iris_samples)
        median_x = float(np.median(arr[:, 0]))
        median_y = float(np.median(arr[:, 1]))
        norm = (median_x / frame_w, median_y / frame_h)
        screen_pos = self.dot_screen_positions()[dot_index]
        self._data.append((norm, screen_pos))

    def save(self):
        serialisable = [
            {"iris_norm": list(iris), "screen_pos": list(sp)}
            for iris, sp in self._data
        ]
        with open(config.CALIBRATION_FILE, "w") as f:
            json.dump(serialisable, f, indent=2)

    @staticmethod
    def load():
        if not os.path.exists(config.CALIBRATION_FILE):
            return None
        with open(config.CALIBRATION_FILE, "r") as f:
            raw = json.load(f)
        return [(tuple(item["iris_norm"]), tuple(item["screen_pos"])) for item in raw]

    def get_data(self):
        return list(self._data)
