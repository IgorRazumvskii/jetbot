"""ДЗ 1: движение JetBot к ArUco-маркеру.

Узел получает изображения камеры, находит на них целевой маркер, оценивает
расстояние и угол до него и публикует команды скорости в /cmd_vel_nav.
Объединение с teleop — через twist_mux (см. launch/aruco_approach.launch.py).

Состояния:
  WAIT     — цель только что пропала (или узел только запущен): стоим и ждём,
             вдруг её ненадолго перекрыли;
  SEARCH   — цели нет дольше search_delay: медленно вращаемся на месте в сторону,
             где её видели последний раз (поведение восстановления);
  APPROACH — едем к цели: ПИД по углу и по расстоянию;
  REACHED  — стоим на расстоянии stop_distance (с гистерезисом).
"""
import math

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from std_msgs.msg import String

from aruco_approach.detector import ArucoDetector, intrinsics_from_fov
from aruco_approach.pid import PID

WAIT = 'WAIT'
SEARCH = 'SEARCH'
APPROACH = 'APPROACH'
REACHED = 'REACHED'


def clamp(value, limit):
    return max(-limit, min(limit, value))


def image_msg_to_bgr(msg: Image):
    """sensor_msgs/Image -> numpy BGR без cv_bridge (его может не быть на роботе)."""
    enc = msg.encoding.lower()
    channels = {'bgr8': 3, 'rgb8': 3, 'bgra8': 4, 'rgba8': 4, 'mono8': 1, '8uc1': 1}.get(enc)
    if channels is None:
        return None
    data = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    img = data[:, :msg.width * channels].reshape(msg.height, msg.width, channels)
    if enc == 'rgb8':
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if enc == 'rgba8':
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    if enc == 'bgra8':
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if channels == 1:
        return cv2.cvtColor(img.reshape(msg.height, msg.width), cv2.COLOR_GRAY2BGR)
    return img


def rotation_to_quaternion(rvec):
    """Вектор Родрига -> кватернион (x, y, z, w)."""
    angle = float(np.linalg.norm(rvec))
    if angle < 1e-9:
        return 0.0, 0.0, 0.0, 1.0
    axis = np.asarray(rvec, dtype=float) / angle
    s = math.sin(angle / 2.0)
    return axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0)


class ArucoApproachNode(Node):

    def __init__(self):
        super().__init__('aruco_approach')

        declare = self.declare_parameter
        # --- параметры, требуемые заданием ---
        declare('stop_distance', 0.5)        # м, на каком расстоянии от цели остановиться
        declare('max_linear_speed', 0.15)    # м/с
        declare('max_angular_speed', 1.0)    # рад/с
        declare('marker_size', 0.10)         # м, реальная сторона маркера (без белой рамки)
        # --- цель и камера ---
        declare('marker_type', 'aruco')      # aruco | stag
        declare('marker_id', -1)             # -1 — любой маркер словаря
        declare('aruco_dictionary', 'DICT_4X4_50')  # для stag: HD11..HD23
        declare('image_topic', '/camera/image/raw')
        declare('use_compressed', False)     # подписаться на <image_topic>/compressed
        declare('camera_info_topic', '/camera/camera_info')
        declare('camera_hfov_deg', 62.2)     # если нет camera_info: угол обзора по горизонтали
        declare('focal_length_px', 0.0)      # если нет camera_info: фокус в пикселях (важнее hfov)
        declare('cmd_vel_topic', '/cmd_vel_nav')
        declare('publish_debug_image', True)
        # --- регуляторы ---
        declare('control_rate', 20.0)
        declare('angular_kp', 1.5)
        declare('angular_ki', 0.0)
        declare('angular_kd', 0.1)
        declare('linear_kp', 0.8)
        declare('linear_ki', 0.0)
        declare('linear_kd', 0.05)
        declare('distance_tolerance', 0.03)  # м, когда считать цель достигнутой
        declare('resume_tolerance', 0.12)    # м, когда снова ехать после REACHED
        declare('angle_tolerance', 0.03)     # рад, мёртвая зона по углу
        declare('heading_slowdown_angle', 0.5)  # рад, при таком угле линейная скорость -> 0
        declare('min_linear_speed', 0.0)     # компенсация мёртвой зоны моторов
        declare('min_angular_speed', 0.0)
        declare('max_linear_accel', 0.4)     # м/с^2
        declare('max_angular_accel', 3.0)    # рад/с^2
        declare('filter_alpha', 0.5)         # сглаживание измерений (1 — без сглаживания)
        # --- восстановление при потере цели ---
        declare('lost_timeout', 0.5)         # с без детекций -> цель потеряна
        declare('search_delay', 1.5)         # с стоять перед началом поиска
        declare('search_angular_speed', 0.5)  # рад/с, вращение на месте при поиске
        declare('search_timeout', 0.0)       # с, 0 — искать бесконечно

        self.ang_pid = PID(0.0)
        self.lin_pid = PID(0.0)
        self.detector = None
        self._load_parameters()
        self._params_dirty = False
        self.add_on_set_parameters_callback(self._on_set_parameters)

        self.camera_info = None
        self.state = WAIT
        self.start_time = self.get_clock().now()
        self.last_seen = None
        self.last_bearing = 0.0
        self.distance = None       # отфильтрованные измерения
        self.bearing = None
        self.target_cmd = (0.0, 0.0)
        self.cmd = (0.0, 0.0)      # последняя опубликованная команда (для ограничения ускорений)
        self.last_tick = None

        image_topic = self.get_parameter('image_topic').value
        if self.get_parameter('use_compressed').value:
            image_topic += '/compressed'
            self.create_subscription(CompressedImage, image_topic, self._on_compressed,
                                     qos_profile_sensor_data)
        else:
            self.create_subscription(Image, image_topic, self._on_image, qos_profile_sensor_data)
        self.create_subscription(CameraInfo, self.get_parameter('camera_info_topic').value,
                                 self._on_camera_info, qos_profile_sensor_data)

        self.cmd_pub = self.create_publisher(Twist, self.get_parameter('cmd_vel_topic').value, 10)
        self.state_pub = self.create_publisher(String, '~/state', 10)
        self.pose_pub = self.create_publisher(PoseStamped, '~/target_pose', 10)
        self.debug_pub = self.create_publisher(Image, '~/debug_image', 1)

        self.timer = self.create_timer(1.0 / self.get_parameter('control_rate').value,
                                       self._on_timer)
        self.get_logger().info(
            f'Жду маркер {self.get_parameter("marker_type").value} '
            f'{self.get_parameter("aruco_dictionary").value} '
            f'id={self.marker_id if self.marker_id >= 0 else "любой"} на {image_topic}; '
            f'остановка в {self.stop_distance:.2f} м')

    # ------------------------------------------------------------------ параметры
    def _load_parameters(self):
        get = lambda name: self.get_parameter(name).value  # noqa: E731
        self.stop_distance = get('stop_distance')
        self.max_linear = get('max_linear_speed')
        self.max_angular = get('max_angular_speed')
        self.marker_id = get('marker_id')
        self.camera_hfov = math.radians(get('camera_hfov_deg'))
        self.focal_length_px = get('focal_length_px')
        self.publish_debug = get('publish_debug_image')
        self.distance_tolerance = get('distance_tolerance')
        self.resume_tolerance = get('resume_tolerance')
        self.angle_tolerance = get('angle_tolerance')
        self.heading_slowdown = get('heading_slowdown_angle')
        self.min_linear = get('min_linear_speed')
        self.min_angular = get('min_angular_speed')
        self.max_lin_acc = get('max_linear_accel')
        self.max_ang_acc = get('max_angular_accel')
        self.alpha = get('filter_alpha')
        self.lost_timeout = get('lost_timeout')
        self.search_delay = get('search_delay')
        self.search_speed = get('search_angular_speed')
        self.search_timeout = get('search_timeout')

        self.ang_pid.kp, self.ang_pid.ki, self.ang_pid.kd = (
            get('angular_kp'), get('angular_ki'), get('angular_kd'))
        self.lin_pid.kp, self.lin_pid.ki, self.lin_pid.kd = (
            get('linear_kp'), get('linear_ki'), get('linear_kd'))
        self.ang_pid.output_limit = self.max_angular
        self.lin_pid.output_limit = self.max_linear
        self.ang_pid.integral_limit = self.max_angular
        self.lin_pid.integral_limit = self.max_linear

        kind = (get('marker_type'), get('aruco_dictionary'))
        if self.detector is None or kind != self._marker_kind:
            self.detector = ArucoDetector(kind[1], get('marker_size'), kind[0])
            self._marker_kind = kind
        self.detector.marker_size = get('marker_size')

    def _on_set_parameters(self, params):
        # Значения применяются после возврата из колбэка, поэтому перечитываем их
        # на следующем тике таймера. Топики меняются только перезапуском узла.
        for p in params:
            if p.name in ('stop_distance', 'marker_size', 'max_linear_speed',
                          'max_angular_speed') and p.value <= 0:
                return SetParametersResult(successful=False, reason=f'{p.name} должен быть > 0')
        self._params_dirty = True
        return SetParametersResult(successful=True)

    # ------------------------------------------------------------------ камера
    def _on_camera_info(self, msg: CameraInfo):
        self.camera_info = msg

    def _on_image(self, msg: Image):
        frame = image_msg_to_bgr(msg)
        if frame is None:
            self.get_logger().error(f'Неподдерживаемая кодировка {msg.encoding}',
                                    throttle_duration_sec=5.0)
            return
        self._process(frame, msg.header)

    def _on_compressed(self, msg: CompressedImage):
        frame = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return
        self._process(frame, msg.header)

    def _camera_model(self, width, height):
        info = self.camera_info
        if info is not None and info.k[0] > 0.0:
            k = np.array(info.k, dtype=float).reshape(3, 3)
            if info.width and info.height and (info.width != width or info.height != height):
                # изображение отмасштабировано относительно калибровки
                k[0, :] *= width / float(info.width)
                k[1, :] *= height / float(info.height)
            return k, np.array(info.d, dtype=float), info.distortion_model
        k = intrinsics_from_fov(width, height, self.camera_hfov, self.focal_length_px)
        return k, None, 'plumb_bob'

    def _process(self, frame, header):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        k, d, model = self._camera_model(frame.shape[1], frame.shape[0])
        observations = self.detector.detect(gray, k, d, model)
        target = self.detector.select(observations, self.marker_id)
        now = self.get_clock().now()

        if target is not None:
            self._update_measurement(target, now)
            pose = PoseStamped()
            pose.header = header
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = (
                float(v) for v in target.tvec)
            q = rotation_to_quaternion(target.rvec)
            (pose.pose.orientation.x, pose.pose.orientation.y,
             pose.pose.orientation.z, pose.pose.orientation.w) = q
            self.pose_pub.publish(pose)

        if self.publish_debug and self.debug_pub.get_subscription_count() > 0:
            self._publish_debug(frame, observations, target, k, d, header)

    # ------------------------------------------------------------------ управление
    def _update_measurement(self, target, now):
        fresh = (self.last_seen is not None
                 and (now - self.last_seen).nanoseconds * 1e-9 < self.lost_timeout)
        dt = (now - self.last_seen).nanoseconds * 1e-9 if fresh else 0.0
        if fresh and self.distance is not None:
            a = self.alpha
            self.distance = a * target.distance + (1.0 - a) * self.distance
            self.bearing = a * target.bearing + (1.0 - a) * self.bearing
        else:
            # цель (вновь) появилась — начинаем с чистого листа
            self.distance, self.bearing = target.distance, target.bearing
            self.ang_pid.reset()
            self.lin_pid.reset()
            dt = 0.05
        self.last_seen = now
        self.last_bearing = self.bearing

        error = self.distance - self.stop_distance
        if self.state == REACHED:
            if abs(error) > self.resume_tolerance:
                self._set_state(APPROACH)
        elif abs(error) <= self.distance_tolerance:
            self._set_state(REACHED)
        else:
            self._set_state(APPROACH)

        if self.state == REACHED:
            self.ang_pid.reset()
            self.lin_pid.reset()
            self.target_cmd = (0.0, 0.0)
            return

        # угол: bearing > 0 — маркер слева -> положительная angular.z (поворот влево)
        bearing = self.bearing if abs(self.bearing) > self.angle_tolerance else 0.0
        angular = self.ang_pid.update(bearing, dt)
        if bearing != 0.0 and abs(angular) < self.min_angular:
            angular = math.copysign(self.min_angular, bearing)

        # расстояние: пока маркер сбоку, сначала доворачиваем, потом едем
        linear = self.lin_pid.update(error, dt)
        heading_factor = max(0.0, 1.0 - abs(self.bearing) / self.heading_slowdown)
        linear *= heading_factor
        if abs(error) > self.distance_tolerance and 0.0 < abs(linear) < self.min_linear \
                and heading_factor > 0.5:
            linear = math.copysign(self.min_linear, linear)

        self.target_cmd = (clamp(linear, self.max_linear), clamp(angular, self.max_angular))

    def _on_timer(self):
        if self._params_dirty:
            self._params_dirty = False
            self._load_parameters()

        now = self.get_clock().now()
        dt = 0.0 if self.last_tick is None else (now - self.last_tick).nanoseconds * 1e-9
        self.last_tick = now

        reference = self.last_seen if self.last_seen is not None else self.start_time
        lost_for = (now - reference).nanoseconds * 1e-9
        if self.last_seen is not None and lost_for < self.lost_timeout:
            linear, angular = self.target_cmd
        else:
            self.distance = self.bearing = None
            if lost_for < self.lost_timeout + self.search_delay:
                self._set_state(WAIT)
                linear, angular = 0.0, 0.0
            elif self.search_timeout > 0.0 and \
                    lost_for > self.lost_timeout + self.search_delay + self.search_timeout:
                self._set_state(WAIT)
                linear, angular = 0.0, 0.0
            else:
                self._set_state(SEARCH)
                direction = 1.0 if self.last_bearing >= 0.0 else -1.0
                linear, angular = 0.0, direction * min(self.search_speed, self.max_angular)

        # плавность: ограничение ускорений
        if dt > 0.0:
            linear = self.cmd[0] + clamp(linear - self.cmd[0], self.max_lin_acc * dt)
            angular = self.cmd[1] + clamp(angular - self.cmd[1], self.max_ang_acc * dt)
        self.cmd = (linear, angular)

        msg = Twist()
        msg.linear.x = float(linear)
        msg.angular.z = float(angular)
        self.cmd_pub.publish(msg)

    def _set_state(self, state):
        if state == self.state:
            return
        info = ''
        if self.distance is not None:
            info = f' (до цели {self.distance:.2f} м, угол {math.degrees(self.bearing):+.1f}°)'
        self.get_logger().info(f'{self.state} -> {state}{info}')
        self.state = state
        self.state_pub.publish(String(data=state))

    # ------------------------------------------------------------------ отладка
    def _publish_debug(self, frame, observations, target, k, d, header):
        img = frame.copy()
        for o in observations:
            pts = o.corners.reshape(-1, 1, 2).astype(np.int32)
            cv2.polylines(img, [pts], True, (0, 255, 0) if o is target else (0, 200, 255), 3)
            cv2.putText(img, str(o.marker_id), tuple(int(v) for v in o.corners[0]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        if target is not None:
            # drawFrameAxes есть не во всех сборках OpenCV, в старых — aruco.drawAxis
            draw_axes = getattr(cv2, 'drawFrameAxes', None) or getattr(cv2.aruco, 'drawAxis', None)
            if draw_axes is not None:
                try:
                    draw_axes(img, k, d if d is not None else np.zeros(5),
                              target.rvec, target.tvec, self.detector.marker_size * 0.5)
                except cv2.error:
                    pass
        lines = [f'state: {self.state}']
        if self.distance is not None:
            lines.append(f'dist: {self.distance:.2f} m (stop {self.stop_distance:.2f})')
            lines.append(f'bearing: {math.degrees(self.bearing):+.1f} deg')
        lines.append(f'cmd: v={self.cmd[0]:+.2f} w={self.cmd[1]:+.2f}')
        for i, text in enumerate(lines):
            y = 28 + 28 * i
            cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
            cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        msg = Image()
        msg.header = header
        msg.height, msg.width = img.shape[:2]
        msg.encoding = 'bgr8'
        msg.step = msg.width * 3
        msg.data.frombytes(np.ascontiguousarray(img).tobytes())
        self.debug_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ArucoApproachNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # перед выходом остановить робота
        if rclpy.ok():
            node.cmd_pub.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
