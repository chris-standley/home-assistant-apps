"""Per-photo quality analysis on Immich's preview image.

For each photo this measures:

- sharpness: variance of the Laplacian, over the whole frame and over faces;
- exposure: how far the brightness is from mid-grey, and clipped highlights
  or shadows;
- faces (OpenCV's YuNet detector): for each face big enough to matter, whether
  it is turned towards the camera (from the eye and nose landmarks), whether
  its eyes are open (OpenCV's eye cascade finds open eyes far more readily
  than closed ones), and whether it is smiling;
- a 64-bit difference hash, used to find near-identical shots.

Results are cached in SQLite by asset id and checksum, so each photo is
downloaded and analysed once.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable

import cv2
import numpy as np

log = logging.getLogger(__name__)

YUNET_MODEL = os.environ.get(
    "YUNET_MODEL", os.path.join(os.path.dirname(__file__), "models", "face_detection_yunet_2023mar.onnx")
)
ANALYSIS_VERSION = 1
MAX_SIDE = 1440  # Immich's preview size; larger images are scaled down to this


@dataclass
class Face:
    size: float  # face width as a fraction of image width
    frontal: float  # 1 = looking straight at the camera, 0 = side on
    eyes_open: float  # 0, 0.5 (one eye found) or 1
    sharpness: float
    smiling: bool

    @property
    def looking(self) -> float:
        """How well this face is 'looking at the camera with eyes open'."""
        return self.frontal * (0.4 + 0.6 * self.eyes_open)


@dataclass
class Analysis:
    sharpness: float
    exposure: float  # 1 = well exposed, 0 = badly over/under exposed
    dhash: int
    faces: list[Face] = field(default_factory=list)

    @property
    def face_sharpness(self) -> float | None:
        if not self.faces:
            return None
        total = sum(f.size for f in self.faces)
        return sum(f.sharpness * f.size for f in self.faces) / total

    @property
    def looking_count(self) -> float:
        return sum(f.looking for f in self.faces)

    @property
    def looking_fraction(self) -> float:
        return self.looking_count / len(self.faces) if self.faces else 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Analysis":
        d = json.loads(data)
        d["faces"] = [Face(**f) for f in d.get("faces", [])]
        return cls(**d)


def _laplacian_var(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _dhash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


class Analyzer:
    def __init__(self, model_path: str = YUNET_MODEL):
        self.model_path = model_path
        self._local = threading.local()
        cascades = cv2.data.haarcascades
        self._eye_path = os.path.join(cascades, "haarcascade_eye_tree_eyeglasses.xml")
        self._smile_path = os.path.join(cascades, "haarcascade_smile.xml")

    def _tools(self):
        # OpenCV detectors aren't thread-safe; keep one set per thread.
        t = self._local
        if not hasattr(t, "detector"):
            t.detector = cv2.FaceDetectorYN.create(self.model_path, "", (320, 320), 0.75, 0.3, 50)
            t.eyes = cv2.CascadeClassifier(self._eye_path)
            t.smile = cv2.CascadeClassifier(self._smile_path)
        return t

    def analyse(self, image_bytes: bytes) -> Analysis | None:
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        scale = MAX_SIDE / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        mean = float(gray.mean()) / 255
        clipped = float(((gray < 8) | (gray > 247)).mean())
        exposure = max(0.0, 1 - abs(mean - 0.5) * 1.6 - clipped * 2)

        return Analysis(
            sharpness=_laplacian_var(gray),
            exposure=round(exposure, 3),
            dhash=_dhash(gray),
            faces=self._faces(img, gray),
        )

    def _faces(self, img: np.ndarray, gray: np.ndarray) -> list[Face]:
        tools = self._tools()
        h, w = gray.shape
        tools.detector.setInputSize((w, h))
        _, found = tools.detector.detect(img)
        faces: list[Face] = []
        if found is None:
            return faces
        for row in found:
            x, y, fw, fh = (int(v) for v in row[:4])
            # Ignore faces in the background: under 4% of the frame's width.
            if fw < 0.04 * w or fw < 24:
                continue
            rx, ry, lx, ly, nx, ny = row[4:10]
            eye_dist = max(1.0, float(np.hypot(lx - rx, ly - ry)))
            # Yaw: the nose sits midway between the eyes when facing the camera.
            yaw = abs(nx - (rx + lx) / 2) / eye_dist
            frontal = float(max(0.0, 1 - yaw * 2.0))
            x0, y0 = max(0, x), max(0, y)
            crop = gray[y0 : min(h, y + fh), x0 : min(w, x + fw)]
            if crop.size == 0:
                continue
            crop = cv2.resize(crop, (160, int(160 * crop.shape[0] / max(1, crop.shape[1]))))
            ch = crop.shape[0]
            eyes = tools.eyes.detectMultiScale(crop[: int(ch * 0.6)], 1.1, 4, minSize=(14, 14))
            smiles = tools.smile.detectMultiScale(crop[int(ch * 0.55) :], 1.6, 18, minSize=(30, 12))
            faces.append(
                Face(
                    size=round(fw / w, 4),
                    frontal=round(frontal, 3),
                    eyes_open=min(1.0, len(eyes) / 2),
                    sharpness=round(_laplacian_var(crop), 2),
                    smiling=len(smiles) > 0,
                )
            )
        return faces


class AnalysisCache:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS analysis (id TEXT PRIMARY KEY, checksum TEXT, version INT, data TEXT)"
        )
        self.db.commit()

    def get(self, asset_id: str, checksum: str) -> Analysis | None:
        with self.lock:
            row = self.db.execute(
                "SELECT checksum, version, data FROM analysis WHERE id = ?", (asset_id,)
            ).fetchone()
        if not row or row[0] != checksum or row[1] != ANALYSIS_VERSION:
            return None
        return Analysis.from_json(row[2])

    def put(self, asset_id: str, checksum: str, analysis: Analysis) -> None:
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO analysis VALUES (?, ?, ?, ?)",
                (asset_id, checksum, ANALYSIS_VERSION, analysis.to_json()),
            )
            self.db.commit()


def analyse_photos(
    photos: Iterable,
    fetch: Callable[[str], bytes],
    cache: AnalysisCache,
    analyzer: Analyzer,
    workers: int = 4,
) -> dict[str, Analysis]:
    """Analyse each photo (from cache where possible). Returns {asset id: Analysis}."""
    results: dict[str, Analysis] = {}
    todo = []
    for p in photos:
        cached = cache.get(p.id, p.checksum)
        if cached:
            results[p.id] = cached
        else:
            todo.append(p)
    if not todo:
        return results
    log.info("Analysing %d new photos (faces, focus, exposure)", len(todo))

    def work(p):
        try:
            a = analyzer.analyse(fetch(p.id))
        except Exception as err:  # one bad image shouldn't stop the run
            log.debug("Could not analyse %s: %s", p.id, err)
            return p, None
        if a:
            cache.put(p.id, p.checksum, a)
        return p, a

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for p, a in pool.map(work, todo):
            if a:
                results[p.id] = a
    return results
