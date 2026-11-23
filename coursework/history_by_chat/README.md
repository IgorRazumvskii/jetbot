# Robotics course on macOS + physical JetBot

Этот репозиторий — рабочая среда курса по робототехнике, адаптированная под Mac с Apple Silicon. В нём поддерживаются два режима:

1. **виртуальный JetBot** в Gazebo Harmonic на macOS;
2. **физический JetBot** с ROS 2 Humble в Docker на самом роботе.

В предыдущей сессии проверены симуляция, управление реальным роботом, RPLidar и Pi Camera с raw ROS-потоком около 29–30 FPS.

## Зафиксированный результат — 05.10.2026

Пользователь подтвердил: реальный JetBot ездит с W/A/S/D. Текущий SSH-адрес — `172.20.10.4` (DHCP). Драйверы уже запущены в сервисе `jetbot_educational`; второй bringup не запускать.

Teleop восстановлен в `/home/app/ros2_ws/src/wasd_teleop.py`. Эта папка подключена с хоста `~/IntelligentRobotics/jetbot_ros2_mipt/src`, поэтому файл сохраняется при пересоздании контейнера. Старого `/home/app/wasd_teleop.py` больше нет.

Внутри контейнера (`app@jetbotj0`) повторный запуск:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
python3 /home/app/ros2_ws/src/wasd_teleop.py
```

W/S — вперёд/назад, A/D — поворот, пробел — стоп, Q/Ctrl+C — выход. Английская раскладка. Задаваемые скорости после двух повышений: ±0,5 м/с и ±3 рад/с; фактические скорости не измерены. Отсутствие ввода 0,3 с вызывает отправку нулевой команды. Повышение ещё в 10 раз не применялось.

Полная инструкция повторного запуска — [ЛР 2](../labs/lab02_sensors_actuators/README.md). Копия скрипта для восстановления — [scripts/wasd_teleop.py](../scripts/wasd_teleop.py).

Камера в этой сессии повторно не проверена. Следующий этап — воспроизвести её запуск и проверить совместно с драйверами. Разделы ниже сохраняют историю предыдущей настройки; старый IP `172.20.10.2` заменять актуальным адресом.

> Подробный технический контекст, найденные проблемы и правила для AI-агента находятся в [`AGENTS.md`](AGENTS.md).

---

## Структура проекта

```text
.
├── AGENTS.md
├── README.md
├── labs/
│   ├── lab01_setup/
│   └── lab02_sensors_actuators/
├── scripts/
│   └── jetbot.sh
├── src/
│   └── jetbot_ros_gazebo/
├── ros2_ws/
└── tools/
    └── ros-jazzy/
```

Материалы преподавателя находятся в `course_description.pages`.

---

# Часть A. Симуляция на Mac

## 1. Требования

Рабочая конфигурация:

```text
macOS
Apple Silicon
Gazebo Harmonic
ROS 2 Jazzy
Pixi
tmux
```

Gazebo устанавливается через Homebrew, ROS 2 находится в Pixi-окружении `tools/ros-jazzy`.

Подробная первоначальная настройка:

- [ЛР 1 — настройка программ на macOS](labs/lab01_setup/README.md)
- [ЛР 2 — сенсоры и актуаторы](labs/lab02_sensors_actuators/README.md)

## 2. Клонирование

```bash
mkdir -p ~/Documents/CCM_courses
git clone https://github.com/MakVlad2003/robotics-course-macos.git \
  ~/Documents/CCM_courses/Robotics

cd ~/Documents/CCM_courses/Robotics
```

## 3. Запуск виртуального JetBot

Один раз установить `tmux`:

```bash
brew install tmux
```

Запуск:

```bash
cd ~/Documents/CCM_courses/Robotics
./scripts/jetbot.sh
```

Откроется `tmux` с окнами:

```text
0 server
1 gui
2 bridge
3 ros
```

Переключение:

```text
Ctrl+B, затем 0..3
```

Остановка из другого terminal:

```bash
./scripts/jetbot.sh down
```

Сцена склада:

```text
labs/lab02_sensors_actuators/worlds/tugbot_warehouse_jetbot.sdf
```

Модель:

```text
src/jetbot_ros_gazebo/models/jetbot/model_high_resolution.sdf
```

Скрипт уже поднимает ROS↔Gazebo bridge для управления, odometry, camera и lidar.

---

# Часть B. Физический JetBot

## 4. Подключение

### USB

Проверенный адрес JetBot:

```text
192.168.55.1
```

Подключение:

```bash
ssh jetbot@192.168.55.1
```

### Wi‑Fi

В предыдущей сессии JetBot находился по:

```text
172.20.10.2
```

Это DHCP-адрес, поэтому использовать актуальный IP с дисплея робота.

Пример:

```bash
ssh jetbot@172.20.10.2
```

Важно: всегда указывать пользователя `jetbot@`. Иначе SSH подставит username с Mac.

---

## 5. JetBot software stack

Проверенная система:

```text
hostname: jetbotj0
Ubuntu 20.04.6
aarch64
kernel 4.9.337-tegra
ROS 2 Humble: внутри Docker
```

Проект на robot host:

```bash
cd ~/IntelligentRobotics/jetbot_ros2_mipt
```

Запустить постоянный container:

```bash
docker compose up -d
```

Войти:

```bash
docker compose exec -it jetbot_educational bash
```

После этого prompt меняется с:

```text
jetbot@jetbotj0:...
```

на:

```text
app@jetbotj0:~/ros2_ws$
```

Все `ros2` и `colcon` команды ниже выполняются **в container**.

---

## 6. Сборка ROS workspace

В container:

```bash
source /opt/ros/humble/install/setup.bash
cd /home/app/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

Если `jetbot_bringup` падает на старом несуществующем launch-файле, очистить только его stale build:

```bash
cd /home/app/ros2_ws

rm -rf \
  build/jetbot_bringup \
  install/jetbot_bringup

colcon build \
  --symlink-install \
  --packages-select jetbot_bringup
```

Камера отдельно:

```bash
colcon build \
  --symlink-install \
  --packages-select pi_camera
```

---

## 7. Запуск моторов и лидара

Terminal 1, внутри container:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash

ros2 launch jetbot_bringup activate_all_drivers.launch.py
```

Успешный запуск поднимает как минимум:

```text
/controller_manager
/diffbot_base_controller
/joint_state_broadcaster
/robot_state_publisher
/rplidar_node
/twist_mux
```

В отдельном terminal войти в тот же container и проверить:

```bash
ros2 node list
ros2 topic list -t
```

Основные topics:

```text
/cmd_vel
/diffbot_base_controller/odom
/joint_states
/scan
/tf
/tf_static
```

Проверка lidar:

```bash
ros2 topic hz /scan
```

RPLidar в рабочем запуске выдавал около:

```text
10 Hz
```

---

## 8. Проверка движения

Перед тестом освободить пространство вокруг robot.

Коротко вперёд:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.05}, angular: {z: 0.0}}"
```

Короткий поворот:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.3}}"
```

Оба теста физически проверены.

Не запускать второй экземпляр `activate_all_drivers.launch.py`: это уже приводило к конфликту motor serial port и занятому HTTP port.

---

# Часть C. Pi Camera

## 9. Проверка камеры на JetBot host

Эта команда выполняется **не в Docker**, а на host:

```bash
gst-launch-1.0 -q \
  nvarguscamerasrc num-buffers=1 sensor-id=0 \
  ! 'video/x-raw(memory:NVMM),width=1280,height=720,format=NV12,framerate=30/1' \
  ! nvvidconv \
  ! 'video/x-raw,format=BGRx' \
  ! fakesink

echo $?
```

Рабочий результат:

```text
GST_ARGUS: Done Success
0
```

---

## 10. Docker configuration для Pi Camera

Камера потребовала явного подключения NVIDIA runtime и EGL.

В `docker-compose.yml` service `jetbot_educational` должны быть camera-related параметры:

```yaml
runtime: nvidia

group_add:
  - "44"

volumes:
  - /tmp/.X11-unix:/tmp/.X11-unix
  - /tmp/argus_socket:/tmp/argus_socket
  - /etc/glvnd/egl_vendor.d/10_nvidia.json:/tmp/10_nvidia.json:ro
  - ./src:/home/app/ros2_ws/src

environment:
  - DISPLAY=${DISPLAY}
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=all
  - LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libGLdispatch.so.0
  - __EGL_VENDOR_LIBRARY_FILENAMES=/tmp/10_nvidia.json
  - ROS_DOMAIN_ID=0
  - ROS_LOCALHOST_ONLY=0
  - RMW_IMPLEMENTATION=rmw_fastrtps_cpp

devices:
  - /dev/input:/dev/input
  - /dev/ttyLIDAR:/dev/ttyLIDAR
  - /dev/ttyMOTOR:/dev/ttyMOTOR
  - /dev/video0:/dev/video0
```

На JetBot host также создан:

```text
/etc/glvnd/egl_vendor.d/10_nvidia.json
```

с содержимым:

```json
{
  "file_format_version": "1.0.0",
  "ICD": {
    "library_path": "libEGL_nvidia.so.0"
  }
}
```

После изменения Compose нужен именно recreate:

```bash
docker compose config -q
docker compose up -d --force-recreate
```

Обычный `docker compose restart` не применит новые mounts/environment/groups.

---

## 11. Проверка GStreamer внутри Docker

В container или через `docker compose exec`:

```bash
gst-inspect-1.0 nvarguscamerasrc
gst-inspect-1.0 nvvidconv
```

Проверенный capture:

```bash
gst-launch-1.0 -q \
  nvarguscamerasrc num-buffers=1 sensor-id=0 \
  ! "video/x-raw(memory:NVMM),width=1280,height=720,format=NV12,framerate=30/1" \
  ! nvvidconv \
  ! "video/x-raw,format=BGRx" \
  ! fakesink
```

Даже если появляется:

```text
nvbuf_utils: Could not get EGL display connection
```

критерий успеха — pipeline доходит до:

```text
GST_ARGUS: Done Success
```

и возвращает code `0`.

---

## 12. Raw ROS camera node

Source package:

```text
/home/app/ros2_ws/src/pi_camera_ros
```

В `setup.py` добавлен entry point:

```python
'publish_raw = pi_camera.publish_raw:main',
```

Запуск:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash

ros2 run pi_camera publish_raw
```

Topic:

```text
/camera/image/raw
```

Type:

```text
sensor_msgs/msg/Image
```

Проверить FPS:

```bash
ros2 topic hz /camera/image/raw
```

Проверенный результат:

```text
~29-30 Hz
```

### Критическая оптимизация

Для `Image.data` нельзя возвращать старый вариант:

```python
msg.data = frame.tobytes()
```

На JetBot он давал около `0.69 Hz`.

Рабочий вариант:

```python
from array import array
...
msg.data = array('B', data)
```

Также publisher использует:

```python
from rclpy.qos import qos_profile_sensor_data
```

После оптимизации raw camera идёт около 30 FPS.

---

# Часть D. Текущий рабочий сценарий

## 13. Terminal layout

Практичнее держать три terminal windows.

### Terminal 1 — drivers

Mac:

```bash
ssh jetbot@<JETBOT_IP>
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose exec -it jetbot_educational bash
```

Container:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 launch jetbot_bringup activate_all_drivers.launch.py
```

Оставить работать.

### Terminal 2 — camera

Зайти в тот же container:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 run pi_camera publish_raw
```

Оставить работать.

### Terminal 3 — диагностика / управление

Проверки:

```bash
ros2 node list
ros2 topic list -t
ros2 topic hz /scan
ros2 topic hz /camera/image/raw
ros2 topic echo /diffbot_base_controller/odom --once
```

Движение:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.05}, angular: {z: 0.0}}"
```

---

# Часть E. Важные замечания

## 14. ROS domain

Симуляция на Mac сейчас использует:

```text
ROS_DOMAIN_ID=42
ROS_LOCALHOST_ONLY=1
```

Физический JetBot Compose сейчас:

```text
ROS_DOMAIN_ID=0
ROS_LOCALHOST_ONLY=0
```

Это разные режимы.

Преподаватель требует устанавливать `ROS_DOMAIN_ID` равным номеру robot, чтобы несколько JetBot не конфликтовали. Перед работой в аудитории заменить `0` на фактический `jetbot_id` и использовать тот же domain на ноутбуке.

---

## 15. Что осталось сделать

На момент последней сессии отдельно проверены:
- motor control;
- odometry/controller stack;
- lidar;
- Pi Camera;
- raw camera ~30 FPS.

Основной bringup после последней rebuild также снова стартовал успешно.

Следующий этап:

1. проверить lidar + motors + camera одновременно;
2. настроить ROS discovery между Mac и physical JetBot;
3. вывести `/scan` и `/camera/image/raw` на Mac через RViz/image viewer;
4. после этого перейти к заданию движения к ArUco marker.

---

## 16. Troubleshooting

### `Package 'pi_camera' not found`

После container recreate package нужно пересобрать:

```bash
cd /home/app/ros2_ws
source /opt/ros/humble/install/setup.bash
colcon build --symlink-install --packages-select pi_camera
source install/setup.bash
```

### `LibSerial::OpenFailed` или `Address already in use`

Скорее всего bringup запущен дважды.

Остановить старый process или на host:

```bash
docker compose restart jetbot_educational
```

### `nvarguscamerasrc` / `nvvidconv` not found

Проверить camera-related параметры Compose из раздела 10 и сделать:

```bash
docker compose up -d --force-recreate
```

### `/camera/image/raw` около 0.7 Hz

Проверить, что в `publish_raw.py` используется:

```python
msg.data = array('B', data)
```

а не `frame.tobytes()`.

### Команда `ros2` или `colcon` не найдена

Скорее всего команда выполняется на JetBot host. Сначала войти в container:

```bash
docker compose exec -it jetbot_educational bash
```

---

Дополнительный подробный контекст для продолжения работы: [`AGENTS.md`](AGENTS.md).
