"""Оценка фокусного расстояния камеры по маркеру на известном расстоянии.

Нужна, если у камеры робота нет калибровки (camera_info). Поставьте маркер
прямо перед камерой на измеренном расстоянии и запустите:

    ros2 run aruco_approach estimate_focal --ros-args \
        -p true_distance:=0.5 -p marker_size:=0.1 -p use_compressed:=true

Полученное значение передайте узлу aruco_approach в параметр focal_length_px.
"""
import statistics

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image

from aruco_approach.approach_node import image_msg_to_bgr
from aruco_approach.detector import ArucoDetector, intrinsics_from_fov


class FocalEstimator(Node):

    def __init__(self):
        super().__init__('estimate_focal')
        self.true_distance = self.declare_parameter('true_distance', 0.5).value
        self.marker_size = self.declare_parameter('marker_size', 0.1).value
        self.samples = self.declare_parameter('samples', 60).value
        dictionary = self.declare_parameter('aruco_dictionary', 'DICT_4X4_50').value
        marker_type = self.declare_parameter('marker_type', 'aruco').value
        self.marker_id = self.declare_parameter('marker_id', -1).value
        topic = self.declare_parameter('image_topic', '/camera/image/raw').value
        if self.declare_parameter('use_compressed', False).value:
            self.create_subscription(CompressedImage, topic + '/compressed', self._on_compressed,
                                     qos_profile_sensor_data)
        else:
            self.create_subscription(Image, topic, self._on_image, qos_profile_sensor_data)
        self.detector = ArucoDetector(dictionary, self.marker_size, marker_type)
        self.values = []
        self.get_logger().info(f'Маркер {self.marker_size} м на расстоянии '
                               f'{self.true_distance} м, собираю {self.samples} кадров...')

    def _on_image(self, msg):
        frame = image_msg_to_bgr(msg)
        if frame is not None:
            self._process(frame)

    def _on_compressed(self, msg):
        frame = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            self._process(frame)

    def _process(self, frame):
        h, w = frame.shape[:2]
        # фокус 1000 px — произвольный: дальность масштабируется пропорционально фокусу
        k = intrinsics_from_fov(w, h, 1.0, focal_length_px=1000.0)
        obs = self.detector.select(
            self.detector.detect(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), k), self.marker_id)
        if obs is None:
            self.get_logger().warn('Маркер не виден', throttle_duration_sec=2.0)
            return
        # для маркера по центру кадра z пропорционален фокусу
        self.values.append(1000.0 * self.true_distance / float(obs.tvec[2]))
        if len(self.values) >= self.samples:
            f = statistics.median(self.values)
            self.get_logger().info(
                f'Кадр {w}x{h}: focal_length_px = {f:.1f} '
                f'(угол обзора по горизонтали ~{2 * np.degrees(np.arctan(w / 2 / f)):.1f}°)')
            raise SystemExit


def main(args=None):
    rclpy.init(args=args)
    node = FocalEstimator()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
