"""Публикация несжатых кадров CSI-камеры JetBot (Pi Camera) в ROS2.

Кадры захватываются GStreamer-пайплайном nvarguscamerasrc (ISP Jetson),
gst-launch-1.0 пишет сырые BGR-кадры в stdout, узел читает их порциями
ровно по width*height*3 байт и публикует sensor_msgs/Image (bgr8).

Дополнительно (параметр compressed_rate) публикуется JPEG в
<image_topic>/compressed — его удобно смотреть с ноутбука по Wi-Fi,
несжатый поток 1280x720@30 через Wi-Fi не пролезет.

Параметр source:=test подменяет камеру на videotestsrc — так узел можно
проверить на ноутбуке без робота.
"""
import subprocess
import threading
import time

import cv2
import numpy as np
import rclpy
import yaml
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, CompressedImage, Image


class RawImagePublisher(Node):

    def __init__(self):
        super().__init__('pi_image_raw_publisher')

        self.sensor_id = self.declare_parameter('sensor_id', 0).value
        self.width = self.declare_parameter('width', 1280).value
        self.height = self.declare_parameter('height', 720).value
        self.fps = self.declare_parameter('fps', 30).value
        # Размер публикуемого кадра (масштабирует аппаратно nvvidconv), 0 — как у захвата
        self.out_width = self.declare_parameter('out_width', 0).value or self.width
        self.out_height = self.declare_parameter('out_height', 0).value or self.height
        # 0 — без поворота, 2 — поворот на 180° (если камера стоит вверх ногами)
        self.flip_method = self.declare_parameter('flip_method', 0).value
        self.source = self.declare_parameter('source', 'nvargus').value
        self.frame_id = self.declare_parameter('frame_id', 'camera_link').value
        image_topic = self.declare_parameter('image_topic', '/camera/image/raw').value
        info_topic = self.declare_parameter('camera_info_topic', '/camera/camera_info').value
        self.compressed_rate = self.declare_parameter('compressed_rate', 15.0).value
        self.jpeg_quality = self.declare_parameter('jpeg_quality', 80).value
        # JPEG уменьшается относительно raw: для Wi-Fi и детекции маркера 640x360 хватает
        self.compressed_scale = self.declare_parameter('compressed_scale', 0.5).value
        camera_info_file = self.declare_parameter('camera_info_file', '').value

        self.image_pub = self.create_publisher(Image, image_topic, 1)
        self.compressed_pub = None
        if self.compressed_rate > 0:
            self.compressed_pub = self.create_publisher(
                CompressedImage, image_topic + '/compressed', 1)
        self.info_pub = None
        self.camera_info = None
        if camera_info_file:
            self.camera_info = self._load_camera_info(camera_info_file)
            self.info_pub = self.create_publisher(CameraInfo, info_topic, 1)

        self.frame_size = self.out_width * self.out_height * 3
        self.proc = None
        self.running = True
        self.last_compressed = 0.0
        self.frames = 0
        self.stats_time = time.monotonic()

        self.reader = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader.start()

    def _build_pipeline(self):
        out_caps = f'video/x-raw,format=BGRx,width={self.out_width},height={self.out_height}'
        if self.source == 'test':
            return [
                'gst-launch-1.0', '-q',
                'videotestsrc', 'is-live=true', 'pattern=ball',
                '!', (f'video/x-raw,width={self.out_width},height={self.out_height},'
                      f'framerate={self.fps}/1'),
                '!', 'videoconvert',
                '!', 'video/x-raw,format=BGR',
                '!', 'filesink', 'location=/dev/stdout',
            ]
        return [
            'gst-launch-1.0', '-q',
            'nvarguscamerasrc', f'sensor-id={self.sensor_id}',
            '!', (f'video/x-raw(memory:NVMM),width={self.width},'
                  f'height={self.height},format=NV12,framerate={self.fps}/1'),
            '!', 'nvvidconv', f'flip-method={self.flip_method}',
            '!', out_caps,
            '!', 'videoconvert',
            '!', 'video/x-raw,format=BGR',
            '!', 'filesink', 'location=/dev/stdout',
        ]

    def _reader_loop(self):
        buf = bytearray(self.frame_size)
        view = memoryview(buf)
        while self.running and rclpy.ok():
            pipeline = self._build_pipeline()
            self.get_logger().info('GStreamer: ' + ' '.join(pipeline[2:]))
            self.proc = subprocess.Popen(pipeline, stdout=subprocess.PIPE, bufsize=0)
            self.get_logger().info(
                f'Публикую {self.out_width}x{self.out_height} bgr8 @ {self.fps} FPS '
                f'(source={self.source})')
            while self.running:
                if not self._read_exact(self.proc.stdout, view):
                    break
                self._publish(buf)
            if self.running:
                code = self.proc.poll()
                self.get_logger().error(
                    f'gst-launch завершился (код {code}), перезапуск через 2 с')
                self._stop_pipeline()
                time.sleep(2.0)

    @staticmethod
    def _read_exact(stream, view):
        """Читает ровно len(view) байт; False — поток закрыт."""
        pos = 0
        total = len(view)
        while pos < total:
            n = stream.readinto(view[pos:])
            if not n:
                return False
            pos += n
        return True

    def _publish(self, buf):
        stamp = self.get_clock().now().to_msg()

        msg = Image()
        msg.header.stamp = stamp
        msg.header.frame_id = self.frame_id
        msg.height = self.out_height
        msg.width = self.out_width
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = self.out_width * 3
        # frombytes копирует буфер целиком; присваивание bytes в msg.data
        # в rclpy проверяет каждый элемент и работает на порядки медленнее
        msg.data.frombytes(buf)
        self.image_pub.publish(msg)

        if self.info_pub is not None:
            self.camera_info.header.stamp = stamp
            self.info_pub.publish(self.camera_info)

        now = time.monotonic()
        if self.compressed_pub is not None and now - self.last_compressed >= 1.0 / self.compressed_rate:
            self.last_compressed = now
            frame = np.frombuffer(buf, dtype=np.uint8).reshape(self.out_height, self.out_width, 3)
            if 0.0 < self.compressed_scale < 1.0:
                frame = cv2.resize(frame, None, fx=self.compressed_scale, fy=self.compressed_scale,
                                   interpolation=cv2.INTER_AREA)
            ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            if ok:
                cmsg = CompressedImage()
                cmsg.header = msg.header
                # формат как у image_transport, чтобы rqt/rviz распознали кодировку
                cmsg.format = 'bgr8; jpeg compressed bgr8'
                cmsg.data.frombytes(jpeg.tobytes())
                self.compressed_pub.publish(cmsg)

        self.frames += 1
        if now - self.stats_time >= 10.0:
            self.get_logger().info(f'{self.frames / (now - self.stats_time):.1f} FPS')
            self.frames = 0
            self.stats_time = now

    def _load_camera_info(self, path):
        """CameraInfo из yaml-файла calibration (формат camera_calibration)."""
        with open(path) as f:
            calib = yaml.safe_load(f)
        info = CameraInfo()
        info.header.frame_id = self.frame_id
        info.width = self.out_width
        info.height = self.out_height
        info.distortion_model = calib.get('distortion_model', 'plumb_bob')
        info.d = [float(v) for v in calib['distortion_coefficients']['data']]
        k = np.array(calib['camera_matrix']['data'], dtype=float).reshape(3, 3)
        p = np.array(calib['projection_matrix']['data'], dtype=float).reshape(3, 4)
        # калибровка могла делаться в другом разрешении — масштабируем матрицы
        sx = self.out_width / float(calib['image_width'])
        sy = self.out_height / float(calib['image_height'])
        k[0, :] *= sx
        k[1, :] *= sy
        p[0, :] *= sx
        p[1, :] *= sy
        info.k = k.flatten().tolist()
        info.p = p.flatten().tolist()
        info.r = [float(v) for v in calib['rectification_matrix']['data']]
        self.get_logger().info(f'Калибровка камеры загружена из {path}')
        return info

    def _stop_pipeline(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def destroy_node(self):
        self.running = False
        self._stop_pipeline()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RawImagePublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
