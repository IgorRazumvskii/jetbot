"""Распознавание ArUco-маркера и оценка его положения относительно камеры.

Работает и со старым API OpenCV (4.5.x в Ubuntu 22.04), и с новым (4.7+).
Координаты — в оптической системе камеры OpenCV: x вправо, y вниз, z вперёд.
"""
import math
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np


@dataclass
class MarkerObservation:
    marker_id: int
    corners: np.ndarray   # 4x2, пиксели: левый верхний, правый верхний, правый нижний, левый нижний
    rvec: np.ndarray      # ориентация маркера (вектор Родрига)
    tvec: np.ndarray      # центр маркера в оптической СК камеры, м
    distance: float       # расстояние до маркера в горизонтальной плоскости камеры (x-z), м
    bearing: float        # угол на маркер, рад; > 0 — маркер слева (как yaw в ROS)
    size_px: float        # средняя длина стороны маркера на изображении, пиксели


def intrinsics_from_fov(width: int, height: int, hfov: float,
                        focal_length_px: float = 0.0) -> np.ndarray:
    """Матрица камеры-обскуры по горизонтальному углу обзора (если нет калибровки)."""
    f = focal_length_px if focal_length_px > 0 else (width / 2.0) / math.tan(hfov / 2.0)
    return np.array([[f, 0.0, width / 2.0],
                     [0.0, f, height / 2.0],
                     [0.0, 0.0, 1.0]])


class ArucoDetector:
    """Детектор квадратных маркеров: ArUco (cv2.aruco) или STag (пакет stag-python).

    Для STag dictionary — номер библиотеки: 'HD15' (или просто '15').
    marker_size — сторона внешнего чёрного квадрата, м.
    """

    def __init__(self, dictionary: str = 'DICT_4X4_50', marker_size: float = 0.1,
                 marker_type: str = 'aruco'):
        self.marker_type = marker_type
        self.marker_size = marker_size
        if marker_type == 'stag':
            import stag  # pip install stag-python
            self._stag = stag
            self._stag_library = int(str(dictionary).upper().replace('HD', ''))
            if self._stag_library not in (11, 13, 15, 17, 19, 21, 23):
                raise ValueError(f'Неизвестная библиотека STag: {dictionary}')
            self._detect = self._detect_stag
            return
        if marker_type != 'aruco':
            raise ValueError(f"marker_type должен быть 'aruco' или 'stag', получено '{marker_type}'")

        aruco = cv2.aruco
        if not hasattr(aruco, dictionary):
            raise ValueError(f'Неизвестный словарь ArUco: {dictionary}')
        dict_id = getattr(aruco, dictionary)
        if hasattr(aruco, 'getPredefinedDictionary'):
            self.dictionary = aruco.getPredefinedDictionary(dict_id)
        else:
            self.dictionary = aruco.Dictionary_get(dict_id)

        if hasattr(aruco, 'ArucoDetector'):  # OpenCV >= 4.7
            params = aruco.DetectorParameters()
            params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
            detector = aruco.ArucoDetector(self.dictionary, params)
            self._detect = detector.detectMarkers
        else:
            params = aruco.DetectorParameters_create()
            params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
            self._detect = lambda gray: aruco.detectMarkers(gray, self.dictionary, parameters=params)

    def _detect_stag(self, gray):
        """STag плохо находит крупные (> ~500 px) маркеры — тогда повтор на уменьшенном кадре."""
        scale = 1.0
        image = gray
        while True:
            corners, ids, rejected = self._stag.detectMarkers(image, self._stag_library)
            if (ids is not None and len(ids) > 0) or min(image.shape[:2]) < 240:
                break
            scale *= 0.5
            image = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if ids is None or len(ids) == 0:
            return [], None, rejected
        corners = [np.asarray(c, dtype=np.float32).reshape(1, 4, 2) / scale for c in corners]
        return corners, np.asarray(ids).reshape(-1, 1), rejected

    @property
    def marker_size(self) -> float:
        return self._marker_size

    @marker_size.setter
    def marker_size(self, size: float):
        # углы маркера в его собственной СК в порядке, который требует SOLVEPNP_IPPE_SQUARE
        half = size / 2.0
        self._marker_size = size
        self._object_points = np.array([[-half, half, 0.0],
                                        [half, half, 0.0],
                                        [half, -half, 0.0],
                                        [-half, -half, 0.0]])

    def detect(self, gray: np.ndarray, camera_matrix: np.ndarray,
               dist_coeffs: Optional[np.ndarray] = None,
               distortion_model: str = 'plumb_bob') -> List[MarkerObservation]:
        corners_list, ids, _ = self._detect(gray)
        if ids is None:
            return []
        observations = []
        for corners, marker_id in zip(corners_list, ids.flatten()):
            obs = self._estimate_pose(int(marker_id), corners.reshape(4, 2),
                                      camera_matrix, dist_coeffs, distortion_model)
            if obs is not None:
                observations.append(obs)
        return observations

    def _estimate_pose(self, marker_id, corners, camera_matrix, dist_coeffs, distortion_model):
        image_points = corners.astype(np.float64).reshape(-1, 1, 2)
        if dist_coeffs is None or len(dist_coeffs) == 0:
            dist = np.zeros(5)
        elif distortion_model in ('equidistant', 'fisheye'):
            # широкоугольная (fisheye) калибровка: сначала убираем дисторсию углов
            d = np.asarray(dist_coeffs, dtype=np.float64)[:4].reshape(4, 1)
            image_points = cv2.fisheye.undistortPoints(image_points, camera_matrix, d,
                                                       P=camera_matrix)
            dist = np.zeros(5)
        else:
            dist = np.asarray(dist_coeffs, dtype=np.float64)

        ok, rvec, tvec = cv2.solvePnP(self._object_points, image_points, camera_matrix, dist,
                                      flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok:
            return None
        tvec = tvec.flatten()
        x, z = float(tvec[0]), float(tvec[2])
        if z <= 0.0:
            return None
        sides = np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)
        return MarkerObservation(
            marker_id=marker_id,
            corners=corners,
            rvec=rvec.flatten(),
            tvec=tvec,
            distance=math.hypot(x, z),
            bearing=math.atan2(-x, z),
            size_px=float(sides.mean()),
        )

    @staticmethod
    def select(observations: List[MarkerObservation],
               marker_id: int = -1) -> Optional[MarkerObservation]:
        """Целевой маркер: с заданным id (или любой при -1), ближайший по размеру на кадре."""
        candidates = [o for o in observations if marker_id < 0 or o.marker_id == marker_id]
        if not candidates:
            return None
        return max(candidates, key=lambda o: o.size_px)


def generate_marker(dictionary: str, marker_id: int, side_px: int) -> np.ndarray:
    """Изображение маркера (без белой рамки) со стороной side_px пикселей."""
    aruco = cv2.aruco
    dict_id = getattr(aruco, dictionary)
    if hasattr(aruco, 'getPredefinedDictionary'):
        dic = aruco.getPredefinedDictionary(dict_id)
    else:
        dic = aruco.Dictionary_get(dict_id)
    if hasattr(aruco, 'generateImageMarker'):
        return aruco.generateImageMarker(dic, marker_id, side_px)
    return aruco.drawMarker(dic, marker_id, side_px)
