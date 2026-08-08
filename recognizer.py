"""
recognizer.py

Phase 1: Face Recognition Module.

Responsibilities:
    - Scan dataset/<MemberName>/*.jpg|png and compute face encodings.
    - Cache encodings to encodings/encodings.pkl so repeated runs don't
      re-process images unless the dataset has changed.
    - Match a live face encoding against known members using Euclidean
      distance, per the threshold configured in config.py.
"""

import os
import pickle
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import face_recognition
import numpy as np

from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png")


@dataclass
class EncodingCache:
    """Container for cached encodings plus a fingerprint of the dataset."""

    names: List[str] = field(default_factory=list)
    encodings: List[np.ndarray] = field(default_factory=list)
    # Maps "MemberName/file.jpg" -> file mtime, used to detect dataset changes.
    fingerprint: Dict[str, float] = field(default_factory=dict)


class FaceRecognizer:
    """
    Loads/encodes the member dataset and matches live faces against it.
    """

    def __init__(self) -> None:
        Config.ensure_directories()
        self.known_names: List[str] = []
        self.known_encodings: List[np.ndarray] = []
        self._fingerprint: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Dataset scanning / fingerprinting
    # ------------------------------------------------------------------

    def _scan_dataset(self) -> Dict[str, float]:
        """
        Walk dataset/<MemberName>/* and build a fingerprint mapping each
        image's relative path to its last-modified time. Used to detect
        whether the cache is stale without re-reading every image.

        Returns:
            Dict of {"MemberName/file.ext": mtime}.
        """
        fingerprint: Dict[str, float] = {}

        if not os.path.isdir(Config.DATASET_DIR):
            logger.warning("Dataset directory not found: %s", Config.DATASET_DIR)
            return fingerprint

        for member_name in sorted(os.listdir(Config.DATASET_DIR)):
            member_dir = os.path.join(Config.DATASET_DIR, member_name)
            if not os.path.isdir(member_dir):
                continue

            for filename in sorted(os.listdir(member_dir)):
                if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
                    continue
                full_path = os.path.join(member_dir, filename)
                key = f"{member_name}/{filename}"
                fingerprint[key] = os.path.getmtime(full_path)

        return fingerprint

    # ------------------------------------------------------------------
    # Encoding cache load / save
    # ------------------------------------------------------------------

    def _load_cache(self) -> Optional[EncodingCache]:
        """Load a previously pickled EncodingCache, if present and valid."""
        if not os.path.exists(Config.ENCODINGS_FILE):
            return None
        try:
            with open(Config.ENCODINGS_FILE, "rb") as f:
                cache: EncodingCache = pickle.load(f)
            return cache
        except (pickle.PickleError, EOFError, OSError, AttributeError) as exc:
            logger.warning("Failed to load encodings cache (%s). Will rebuild.", exc)
            return None

    def _save_cache(self) -> None:
        """Persist current encodings + fingerprint to disk."""
        cache = EncodingCache(
            names=self.known_names,
            encodings=self.known_encodings,
            fingerprint=self._fingerprint,
        )
        try:
            with open(Config.ENCODINGS_FILE, "wb") as f:
                pickle.dump(cache, f)
            logger.info("Saved %d face encodings to %s", len(self.known_names), Config.ENCODINGS_FILE)
        except OSError as exc:
            logger.error("Could not save encodings cache: %s", exc)

    # ------------------------------------------------------------------
    # Encoding computation
    # ------------------------------------------------------------------

    def _encode_dataset(self, fingerprint: Dict[str, float]) -> None:
        """
        Compute face encodings for every image in the dataset from scratch.

        Args:
            fingerprint: Precomputed {"Member/file.ext": mtime} map to save
                for future staleness checks.
        """
        names: List[str] = []
        encodings: List[np.ndarray] = []

        for member_name in sorted(os.listdir(Config.DATASET_DIR)):
            member_dir = os.path.join(Config.DATASET_DIR, member_name)
            if not os.path.isdir(member_dir):
                continue

            image_count = 0
            for filename in sorted(os.listdir(member_dir)):
                if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
                    continue

                full_path = os.path.join(member_dir, filename)
                try:
                    image = face_recognition.load_image_file(full_path)
                    face_locations = face_recognition.face_locations(
                        image, model=Config.FACE_DETECTION_MODEL
                    )

                    if not face_locations:
                        logger.warning("No face found in %s - skipping.", full_path)
                        continue

                    if len(face_locations) > 1:
                        logger.warning(
                            "Multiple faces found in %s - using the first one. "
                            "Use single-face images for best accuracy.",
                            full_path,
                        )

                    face_encs = face_recognition.face_encodings(
                        image,
                        known_face_locations=[face_locations[0]],
                        num_jitters=Config.NUM_JITTERS,
                    )
                    if not face_encs:
                        continue

                    names.append(member_name)
                    encodings.append(face_encs[0])
                    image_count += 1

                except Exception as exc:  # noqa: BLE001 - keep encoding robust to bad files
                    logger.error("Failed to encode %s: %s", full_path, exc)

            logger.info("Encoded %d image(s) for member '%s'", image_count, member_name)

        self.known_names = names
        self.known_encodings = encodings
        self._fingerprint = fingerprint

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_or_build_encodings(self, force_rebuild: bool = False) -> None:
        """
        Load cached encodings if the dataset hasn't changed; otherwise
        (re)compute encodings and refresh the cache.

        Args:
            force_rebuild: If True, ignore the cache and always re-encode.
        """
        current_fingerprint = self._scan_dataset()

        if not force_rebuild:
            cache = self._load_cache()
            if cache is not None and cache.fingerprint == current_fingerprint:
                self.known_names = cache.names
                self.known_encodings = cache.encodings
                self._fingerprint = cache.fingerprint
                logger.info(
                    "Loaded %d cached face encodings (dataset unchanged).",
                    len(self.known_names),
                )
                return
            logger.info("Dataset changed or no valid cache found - rebuilding encodings.")

        self._encode_dataset(current_fingerprint)
        self._save_cache()

    def match_face(self, face_encoding: np.ndarray) -> Tuple[str, float]:
        """
        Compare a single live face encoding against all known encodings
        using Euclidean distance, returning the closest match.

        Args:
            face_encoding: 128-d encoding of a detected face.

        Returns:
            (name, distance) tuple. name is Config.UNKNOWN_LABEL if no
            known face is within the configured threshold.
        """
        if not self.known_encodings:
            return Config.UNKNOWN_LABEL, float("inf")

        distances = face_recognition.face_distance(self.known_encodings, face_encoding)
        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])

        if best_distance <= Config.FACE_MATCH_THRESHOLD:
            return self.known_names[best_index], best_distance

        return Config.UNKNOWN_LABEL, best_distance

    def match_faces_batch(
        self, face_encodings: List[np.ndarray]
    ) -> List[Tuple[str, float]]:
        """
        Convenience wrapper to match multiple face encodings from one frame.

        Args:
            face_encodings: List of 128-d face encodings from a single frame.

        Returns:
            List of (name, distance) tuples, one per input encoding.
        """
        return [self.match_face(enc) for enc in face_encodings]

    @property
    def known_member_count(self) -> int:
        """Number of unique members currently loaded (by distinct name)."""
        return len(set(self.known_names))