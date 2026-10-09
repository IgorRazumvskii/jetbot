"""Проверка распознавания и оценки дальности на синтетических кадрах."""
import math

import cv2
import numpy as np
import pytest

from aruco_approach.detector import ArucoDetector, generate_marker, intrinsics_from_fov

W, H = 1280, 720
MARKER = 0.10


def render(tx, ty, tz, yaw=0.0, marker_id=0, k=None):
    """Кадр с маркером, центр которого в точке (tx, ty, tz) оптической СК камеры."""
    k = intrinsics_from_fov(W, H, math.radians(62.2)) if k is None else k
    side, border = 400, 80
    src = np.full((side + 2 * border,) * 2, 255, np.uint8)
    src[border:border + side, border:border + side] = generate_marker('DICT_4X4_50', marker_id, side)

    # маркер смотрит на камеру; yaw — поворот вокруг вертикали
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]]) @ np.diag([1.0, -1.0, -1.0])
    h = MARKER / 2.0 * (side + 2 * border) / side   # с учётом белой рамки
    obj = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]])
    cam = (rot @ obj.T).T + np.array([tx, ty, tz])
    img_pts, _ = cv2.projectPoints(cam, np.zeros(3), np.zeros(3), k, np.zeros(5))
    n = side + 2 * border
    src_pts = np.float32([[0, 0], [n, 0], [n, n], [0, n]])
    hom = cv2.getPerspectiveTransform(src_pts, img_pts.reshape(4, 2).astype(np.float32))
    canvas = np.full((H, W), 128, np.uint8)
    cv2.warpPerspective(src, hom, (W, H), dst=canvas, borderMode=cv2.BORDER_TRANSPARENT)
    return canvas, k


@pytest.mark.parametrize('tx,tz', [(0.0, 0.5), (0.0, 1.0), (0.2, 1.0), (-0.3, 1.5), (0.0, 2.5)])
def test_distance_and_bearing(tx, tz):
    img, k = render(tx, 0.05, tz)
    det = ArucoDetector('DICT_4X4_50', MARKER)
    obs = det.select(det.detect(img, k))
    assert obs is not None
    assert obs.distance == pytest.approx(math.hypot(tx, tz), rel=0.03)
    assert obs.bearing == pytest.approx(math.atan2(-tx, tz), abs=0.02)


def test_bearing_sign_left_is_positive():
    det = ArucoDetector('DICT_4X4_50', MARKER)
    left = det.select(det.detect(*render(-0.3, 0.0, 1.0)))
    right = det.select(det.detect(*render(0.3, 0.0, 1.0)))
    assert left.bearing > 0.0 > right.bearing


def test_rotated_marker_distance():
    img, k = render(0.1, 0.0, 1.2, yaw=math.radians(35))
    det = ArucoDetector('DICT_4X4_50', MARKER)
    obs = det.select(det.detect(img, k))
    assert obs is not None
    assert obs.distance == pytest.approx(math.hypot(0.1, 1.2), rel=0.04)


def test_select_by_id():
    img_a, k = render(-0.25, 0.0, 1.0, marker_id=3)
    img_b, _ = render(0.25, 0.0, 0.8, marker_id=7)
    img = np.minimum(img_a, img_b)  # два маркера на одном кадре
    det = ArucoDetector('DICT_4X4_50', MARKER)
    obs = det.detect(img, k)
    assert sorted(o.marker_id for o in obs) == [3, 7]
    assert det.select(obs, 3).marker_id == 3
    assert det.select(obs, -1).marker_id == 7   # ближний (крупнее на кадре)
    assert det.select(obs, 5) is None


def test_no_marker():
    det = ArucoDetector('DICT_4X4_50', MARKER)
    k = intrinsics_from_fov(W, H, 1.0)
    assert det.detect(np.full((H, W), 128, np.uint8), k) == []


def test_stag_photo_detected():
    """Фото маркера курса (STag HD15 id 54), в том числе крупное — через уменьшение кадра."""
    import os
    path = os.path.join(os.path.dirname(__file__), 'data', 'stag_hd15_54.jpg')
    gray = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2GRAY)
    det = ArucoDetector('HD15', MARKER, marker_type='stag')
    for scale in (1.0, 0.3):
        img = cv2.resize(gray, None, fx=scale, fy=scale)
        k = intrinsics_from_fov(img.shape[1], img.shape[0], math.radians(62.2))
        obs = det.select(det.detect(img, k), 54)
        assert obs is not None, f'scale {scale}'
        assert obs.distance > 0.0
