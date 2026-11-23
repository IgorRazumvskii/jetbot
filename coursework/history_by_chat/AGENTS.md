# AGENTS.md — контекст и правила работы с проектом Robotics

## Обновление — 05.10.2026

- Пользователь подтвердил физическое движение JetBot с W/A/S/D после настройки текущих скоростей. Это подтверждение пользователя, а не измерение скорости агентом.
- Текущий адрес: `jetbot@172.20.10.4`. Адрес DHCP; `.2` ниже относится к прошлой сессии.
- Старый `/home/app/wasd_teleop.py` отсутствует. Скрипт восстановлен в `/home/app/ros2_ws/src/wasd_teleop.py`, на хосте — `~/IntelligentRobotics/jetbot_ros2_mipt/src/wasd_teleop.py`. Папка `src` подключена с хоста. Копия в Mac-проекте: `scripts/wasd_teleop.py`.
- Teleop публикует `Twist` в `/cmd_vel`. Текущие команды: W/S ±0.5 м/с, A/D ±3.0 рад/с. Пробел — стоп, Q/Ctrl+C — выход; отсутствие ввода 0.3 с — нулевая команда. Увеличение ещё в 10 раз не применялось.
- Драйверы уже работали; повторный bringup не запускать. В контейнере (`app@jetbotj0`) выполнить оба `source`, затем `python3 /home/app/ros2_ws/src/wasd_teleop.py`. Docker-команды выполнять только на хосте (`jetbot@jetbotj0`).
- Команды повторного запуска сохранены в `labs/lab02_sensors_actuators/README.md`. Не пересоздавать контейнер без необходимости и не очищать workspace.
- Камера около 29–30 FPS подтверждена предыдущей сессией. В текущей сессии повторно не проверена. Продолжить с запуска камеры вместе с работающим bringup.

Остальные разделы ниже сохраняют историю предыдущей сессии. При расхождении текущего пути teleop или IP использовать это обновление.

## 1. Назначение этого файла

Этот файл — оперативная память для AI-агента, который продолжает работу с репозиторием `robotics-course-macos` и физическим JetBot. Не предполагай, что новый чат знает историю настройки: перед изменениями прочитай этот файл, корневой `README.md`, README нужной лабораторной и материалы преподавателя.

Основной принцип: **не ломать уже проверенный стек ради “более правильной” архитектуры**. Сначала воспроизводи известный рабочий путь, затем меняй только то, для чего есть конкретная причина и проверка.

Состояние ниже основано на реально выполненных командах и логах предыдущей сессии. Отделяй:
- **проверено** — реально запускалось на этом Mac / JetBot;
- **настроено, но требует повторной проверки** — файлы изменены, однако после последнего restart/rebuild не весь стек проверен одновременно;
- **следующий шаг** — ещё не считать выполненным.

---

## 2. Два независимых окружения

В проекте есть два разных стека. Не смешивать их.

### 2.1. Симуляция на Mac

Рабочий ноутбук:
- macOS;
- Apple Silicon;
- Gazebo Harmonic установлен через Homebrew;
- ROS 2 Jazzy находится в Pixi-окружении `tools/ros-jazzy`;
- локальный ROS workspace: `ros2_ws`;
- симуляционная модель: `src/jetbot_ros_gazebo`;
- основной launcher: `scripts/jetbot.sh`.

Репозиторий обычно расположен в:

```bash
~/Documents/CCM_courses/Robotics
```

Рабочий запуск симуляции:

```bash
cd ~/Documents/CCM_courses/Robotics
./scripts/jetbot.sh
```

Остановка:

```bash
./scripts/jetbot.sh down
```

Скрипт поднимает `tmux` с окнами:
- `server` — Gazebo server;
- `gui` — Gazebo GUI;
- `bridge` — `ros_gz_bridge`;
- `ros` — интерактивное ROS-окружение.

Для симуляции скрипт сейчас задаёт:

```text
GZ_IP=127.0.0.1
GZ_PARTITION=robotics
ROS_DOMAIN_ID=42
ROS_LOCALHOST_ONLY=1
```

Это специально локальная конфигурация. **Она не подходит как есть для подключения к физическому JetBot**, потому что реальный робот сейчас использует другой ROS domain и должен быть доступен по сети.

Подробности виртуальной части находятся в:
- `labs/lab01_setup/README.md`
- `labs/lab02_sensors_actuators/README.md`

`src/jetbot_ros_gazebo` — отдельный Git-репозиторий с локальными изменениями модели/`setup.py`. Не делать `git reset --hard`, не заменять его исходной версией без анализа.

### 2.2. Физический JetBot

Физический робот — отдельная Linux-машина:

```text
hostname: jetbotj0
user: jetbot
Ubuntu: 20.04.6 LTS
arch: aarch64
kernel: 4.9.337-tegra
Jetson/L4T packages: 32.7.6
```

ROS 2 Humble **не установлен как рабочее окружение на host shell**. ROS запускается внутри Docker-контейнера.

Рабочий проект на роботе:

```bash
~/IntelligentRobotics/jetbot_ros2_mipt
```

Docker image:

```text
jetbot_full_ros2
```

Base image проекта:

```dockerfile
FROM ghcr.io/kalanaratnayake/jetson-ros:humble-base-r32.7.1
```

Compose service:

```text
jetbot_educational
```

ROS внутри контейнера:

```text
ROS_DISTRO=humble
```

---

## 3. Подключение к JetBot

### 3.1. USB

USB networking на Mac реально проверен.

JetBot:

```text
192.168.55.1
```

Mac получает адрес примерно:

```text
192.168.55.100
```

На macOS USB-интерфейс отображался как:

```text
Hardware Port: Linux for Tegra
```

Проверка:

```bash
ping 192.168.55.1
```

SSH обязательно с именем пользователя:

```bash
ssh jetbot@192.168.55.1
```

Не использовать:

```bash
ssh 192.168.55.1
```

Иначе SSH подставит macOS username, которого на JetBot нет.

### 3.2. Wi‑Fi

Во время предыдущей настройки JetBot имел:

```text
172.20.10.2
```

Это DHCP-адрес и он **может измениться**. Брать актуальный адрес с дисплея робота или через `ip addr`.

Рабочая команда в той сети была:

```bash
ssh jetbot@172.20.10.2
```

В предыдущей сессии Wi‑Fi субъективно работал отзывчивее SSH-over-USB, поэтому для интерактивной настройки использовался Wi‑Fi.

---

## 4. Самая важная ментальная модель: HOST vs CONTAINER

Много ошибок возникало из-за выполнения правильной команды не в том shell.

### Host JetBot

Prompt:

```text
jetbot@jetbotj0:~$
```

или:

```text
jetbot@jetbotj0:~/IntelligentRobotics/jetbot_ros2_mipt$
```

Здесь выполнять:
- `docker compose ...`
- `docker ps`
- `gst-launch-1.0` для проверки камеры на host;
- редактирование `docker-compose.yml`;
- проверку `/dev/...`;
- системные NVIDIA/L4T проверки.

### ROS 2 container

Prompt:

```text
app@jetbotj0:~/ros2_ws$
```

Здесь выполнять:
- `ros2 ...`
- `colcon build ...`
- `source /opt/ros/humble/install/setup.bash`
- `source /home/app/ros2_ws/install/setup.bash`
- запуск ROS-ноды камеры;
- launch драйверов.

Если на host выполнить `ros2`, `colcon` или `cd /home/app/ros2_ws`, это закономерно не работает.

Выйти из контейнера:

```bash
exit
```

Войти обратно:

```bash
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose exec -it jetbot_educational bash
```

---

## 5. Docker: проверенный workflow

Преподаватель в методичке использует `docker compose run -it ...`, но фактически для нашей работы оказался удобнее и проверен один постоянный service container:

```bash
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose up -d
docker compose exec -it jetbot_educational bash
```

Это позволяет открыть несколько терминалов в **одном и том же** контейнере:
- терминал 1 — bringup;
- терминал 2 — camera;
- терминал 3 — диагностика / teleop.

Старые контейнеры с именами вида:

```text
jetbot_ros2_mipt-jetbot_educational-run-...
```

остались от `docker compose run`. Compose может писать `Found orphan containers`. Это не фатальная ошибка. Не удалять их во время работающей лабораторной без необходимости.

### Критическое правило

Не запускать `activate_all_drivers.launch.py` второй раз, пока первый экземпляр жив.

Дублирование уже приводило к:
- `LibSerial::OpenFailed: Bad file descriptor` для моторов;
- `Address already in use` для HTTP server на порту 8000;
- конфликтам с serial devices.

Если неизвестно, что осталось запущено, безопасный путь:

```bash
# на host JetBot
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose restart jetbot_educational
docker compose exec -it jetbot_educational bash
```

После restart проверить, что старых процессов нет:

```bash
ps aux | grep -E "ros2_control|rplidar|robot_state|twist_mux|http.server" | grep -v grep
```

---

## 6. Hardware devices

На host JetBot были проверены:

```text
/dev/ttyLIDAR -> ttyUSB0
/dev/ttyMOTOR -> ttyTHS1
/dev/video0
```

Проверка:

```bash
ls -l /dev/ttyMOTOR /dev/ttyLIDAR /dev/video0
```

`docker-compose.yml` пробрасывает эти устройства в container.

---

## 7. ROS workspace на физическом JetBot

Container workspace:

```bash
/home/app/ros2_ws
```

Source mount с host:

```text
host:      ~/IntelligentRobotics/jetbot_ros2_mipt/src
container: /home/app/ros2_ws/src
```

Пакеты, которые реально видели:

```text
diffdrive_jetbot
jetbot_bringup
pi_camera_ros   -> ROS package pi_camera
```

Launch-файлы:

```text
jetbot_bringup/launch/activate_all_drivers.launch.py
jetbot_bringup/launch/rplidar.launch.py
```

### Важное свойство container recreation

В `docker-compose.yml` persistent volume есть для `src`, но `build/`, `install/`, `log/` живут внутри контейнера.

После:

```bash
docker compose up -d --force-recreate
```

исходники сохраняются, но старые build/install могут исчезнуть. После recreate нужно быть готовым пересобрать пакеты.

---

## 8. Сборка workspace и известная stale-build проблема

Полный build однажды упал:

```text
error: can't copy .../all_robot_launches_slam_localization.launch.py:
doesn't exist or not a regular file
```

В `src/jetbot_bringup/launch` реально были только:

```text
activate_all_drivers.launch.py
rplidar.launch.py
```

`setup.py` использует:

```python
glob('launch/*.launch.py')
```

То есть ошибка была не в source, а в stale artifact в `build/jetbot_bringup`.

Рабочее исправление:

```bash
cd /home/app/ros2_ws

rm -rf \
  build/jetbot_bringup \
  install/jetbot_bringup

colcon build \
  --symlink-install \
  --packages-select jetbot_bringup \
  --event-handlers console_direct+
```

После этого `jetbot_bringup` собрался успешно.

`pi_camera` затем отдельно:

```bash
colcon build \
  --symlink-install \
  --packages-select pi_camera \
  --event-handlers console_direct+
```

Также успешно.

Не удалять весь workspace без причины. Для stale package сначала чистить только `build/<pkg>` и `install/<pkg>`.

---

## 9. Bringup моторов и лидара

Внутри container:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash

ros2 launch jetbot_bringup activate_all_drivers.launch.py
```

Проверенный успешный bringup поднимал:

```text
/controller_manager
/diffbot_base_controller
/joint_state_broadcaster
/robot_state_publisher
/rplidar_node
/twist_mux
```

Проверенные/ожидаемые ROS topics:

```text
/cmd_vel
/cmd_vel_joy
/cmd_vel_robot_steering
/diagnostics
/diffbot_base_controller/cmd_vel_unstamped
/diffbot_base_controller/odom
/dynamic_joint_states
/joint_states
/robot_description
/scan
/tf
/tf_static
```

`twist_mux` принимает обычное управление на:

```text
/cmd_vel
```

и передаёт его в controller.

### Лидар

В успешном логе:
- RPLidar SDK 2.0.0;
- health status `OK`;
- scan frequency около `10 Hz`;
- max distance `12.0 m`.

### Моторный controller

В успешном логе:
- hardware `DiffBot` инициализирован;
- `joint_state_broadcaster` активирован;
- `diffbot_base_controller` активирован;
- max motor speed: `300 RPM`;
- encoder counts/rev: `1760`.

Нефатальные предупреждения, которые уже наблюдались:
- `No real-time kernel detected`;
- deprecated `robot_description` parameter path;
- `Timeout waiting for flash setting line 9`, если после него идёт `Successfully configured!` и `Successfully activated!`.

---

## 10. Проверенное управление движением

Проверен topic:

```bash
ros2 topic info /cmd_vel -v
```

Тип:

```text
geometry_msgs/msg/Twist
```

Subscriber:

```text
twist_mux
```

### Короткое движение вперёд

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.05}, angular: {z: 0.0}}"
```

Робот физически проехал немного вперёд.

### Короткий поворот

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.3}}"
```

Робот физически повернулся.

Перед любым тестом движения убедиться, что вокруг робота свободно. Не давать большие скорости вслепую.

---

## 11. WASD teleop: что было сделано

Был проверен кастомный Python teleop:
- `W` — вперёд;
- `S` — назад;
- `A` — влево;
- `D` — вправо;
- `Space` — стоп;
- `Q` — выход.

Он публиковал `geometry_msgs/Twist` в `/cmd_vel` с небольшими скоростями.

Важно: скрипт был создан как:

```text
~/wasd_teleop.py
```

**внутри container** до нескольких `--force-recreate`, поэтому не считать, что файл сейчас существует. Если teleop понадобится снова, создать его в persistent source tree или в этом Mac-репозитории (`scripts/`), а не в ephemeral container home.

Raw-terminal поведение было ожидаемым: при запущенном скрипте буквы не отображались в терминале, потому что использовался `tty.setraw`.

---

## 12. Pi Camera: железо на host проверено

На физическом JetBot стоит Pi Camera / CSI camera.

Host test, который реально завершился с `EXIT=0`:

```bash
gst-launch-1.0 -q \
  nvarguscamerasrc num-buffers=1 sensor-id=0 \
  ! 'video/x-raw(memory:NVMM),width=1280,height=720,format=NV12,framerate=30/1' \
  ! nvvidconv \
  ! 'video/x-raw,format=BGRx' \
  ! fakesink

echo $?
```

Результат:

```text
GST_ARGUS: Done Success
0
```

Следовательно, камера, Argus и Jetson multimedia stack на host исправны.

Host packages:

```text
nvidia-l4t-gstreamer 32.7.6
nvidia-l4t-multimedia 32.7.6
nvidia-l4t-multimedia-utils 32.7.6
```

---

## 13. Camera support внутри Docker: важная история диагностики

Изначально внутри container:

```bash
gst-inspect-1.0 nvarguscamerasrc
gst-inspect-1.0 nvvidconv
```

не находили plugins.

На host plugins были:

```text
/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstnvarguscamerasrc.so
/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstnvvidconv.so
```

NVIDIA runtime был установлен:

```text
Runtimes: ... nvidia ...
Default Runtime: nvidia
```

`l4t.csv` уже перечислял нужные Tegra/GStreamer библиотеки.

Проблема решилась после явной настройки NVIDIA runtime + EGL.

### 13.1. Текущие необходимые изменения `docker-compose.yml`

В service `jetbot_educational` должны присутствовать как минимум следующие camera-related additions:

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

`video` group на host имел GID `44`.

### 13.2. NVIDIA EGL vendor file на host

На host был создан:

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

Compose монтирует его в container как:

```text
/tmp/10_nvidia.json
```

а переменная:

```text
__EGL_VENDOR_LIBRARY_FILENAMES=/tmp/10_nvidia.json
```

заставляет EGL использовать NVIDIA ICD.

### 13.3. Проверенный Docker camera test

После этих изменений и `--force-recreate` внутри container камера успешно отработала:

```bash
gst-launch-1.0 -q \
  nvarguscamerasrc num-buffers=1 sensor-id=0 \
  ! "video/x-raw(memory:NVMM),width=1280,height=720,format=NV12,framerate=30/1" \
  ! nvvidconv \
  ! "video/x-raw,format=BGRx" \
  ! fakesink
```

Результат:

```text
GST_ARGUS: Done Success
EXIT=0
```

При этом могли оставаться warnings:

```text
nvbuf_utils: Could not get EGL display connection
```

и warning про `libgstnvcompositor.so` / `libgstbadvideo-1.0.so.0`.

Для нашего pipeline они оказались нефатальными, потому что capture завершался успешно.

---

## 14. ROS camera package `pi_camera`

Source:

```text
/home/app/ros2_ws/src/pi_camera_ros
```

Пакет:

```text
pi_camera
```

Изначально `setup.py` содержал entry points:

```text
publish_compressed
view_compressed
```

Был добавлен:

```python
'publish_raw = pi_camera.publish_raw:main',
```

и файл:

```text
pi_camera/publish_raw.py
```

### 14.1. GStreamer pipeline для raw

Проверенная логика:

```text
nvarguscamerasrc sensor-id=0
-> NVMM 1280x720 NV12 30 FPS
-> nvvidconv
-> BGRx
-> videoconvert
-> BGR
-> filesink /dev/stdout
```

ROS topic:

```text
/camera/image/raw
```

Message:

```text
sensor_msgs/msg/Image
```

Encoding:

```text
bgr8
```

QoS после оптимизации:

```python
from rclpy.qos import qos_profile_sensor_data
```

и publisher создаётся с `qos_profile_sensor_data`.

### 14.2. Критическая performance находка

Первоначально использовалось:

```python
msg.data = frame.tobytes()
```

Это оказалось катастрофически медленно в `rclpy` для кадра 1280x720x3.

Профилирование показало примерно:

```text
read     ~8 ms
prepare  ~1420 ms
publish  ~2 ms
```

ROS topic шёл только около:

```text
0.69 Hz
```

Исправление:

```python
from array import array
...
msg.data = array('B', data)
```

После этого:

```text
read     ~9-15 ms
prepare  ~2.2-2.6 ms
publish  ~3.9-4.2 ms
```

и реальный:

```bash
ros2 topic hz /camera/image/raw
```

дал примерно:

```text
29-30 Hz
```

Это **обязательная оптимизация**. Не возвращать `frame.tobytes()`.

### 14.3. Сам GStreamer не был bottleneck

Тест 300 кадров:

```bash
time gst-launch-1.0 -q \
  nvarguscamerasrc num-buffers=300 sensor-id=0 \
  ! 'video/x-raw(memory:NVMM),width=1280,height=720,format=NV12,framerate=30/1' \
  ! nvvidconv \
  ! 'video/x-raw,format=BGRx' \
  ! videoconvert \
  ! 'video/x-raw,format=BGR' \
  ! fakesink
```

дал:

```text
real 0m11.357s
```

То есть camera/GStreamer path был порядка 26 FPS+, и основной slowdown действительно был в Python message preparation.

### 14.4. Незакрытая мелочь в `publish_raw.py`

Во время Ctrl+C наблюдалось:

```text
RCLError: failed to shutdown: rcl_shutdown already called
```

Это не проблема камеры, а shutdown logic Python-ноды.

Перед финализацией `publish_raw.py` агенту стоит проверить `main()` и сделать shutdown idempotent, например:

```python
if rclpy.ok():
    rclpy.shutdown()
```

или убрать второй shutdown, если context уже завершён.

Также в source **могли остаться временные timing logs**:

```text
read=... ms, prepare=... ms, publish=... ms
```

Команда на их удаление была предложена, но нет подтверждения, что она была реально выполнена. Перед финальным commit проверить файл.

---

## 15. Запуск camera ROS node

После rebuild:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 run pi_camera publish_raw
```

В другом terminal/container shell:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 topic hz /camera/image/raw
```

Проверенный результат:

```text
~29-30 Hz
```

---

## 16. Текущее состояние на момент последней сессии

### Проверено

- Mac ↔ JetBot по USB.
- Mac ↔ JetBot по Wi‑Fi.
- Docker Compose service запускается.
- ROS 2 Humble внутри container.
- Motor controller работает.
- `/cmd_vel` реально двигает и поворачивает робота.
- RPLidar работает.
- Pi Camera работает на host.
- Pi Camera работает внутри Docker через Argus/GStreamer.
- `publish_raw` публиковал `/camera/image/raw` около 29–30 Hz.
- `jetbot_bringup` и `pi_camera` после cleanup собираются.
- После последней пересборки `activate_all_drivers.launch.py` снова успешно поднял lidar и controllers.

### Текущий runtime момент

В самом конце предыдущего диалога основной bringup был запущен, а следующий план был:
1. в отдельном terminal проверить nodes/topics;
2. проверить `/scan`;
3. проверить `/cmd_vel`;
4. параллельно запустить `pi_camera publish_raw`;
5. затем вывести сенсоры на Mac.

Не считать пункт 5 уже сделанным.

---

## 17. Что ещё НЕ проверено окончательно

### 17.1. Визуализация физического JetBot на Mac

Это следующий крупный шаг.

Симуляционный `scripts/jetbot.sh` сейчас использует:

```text
ROS_DOMAIN_ID=42
ROS_LOCALHOST_ONLY=1
```

Физический JetBot compose сейчас использует:

```text
ROS_DOMAIN_ID=0
ROS_LOCALHOST_ONLY=0
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

Поэтому Mac не надо подключать к реальному роботу через симуляционный shell без изменения сетевых ROS-настроек.

Для реального робота:
- Mac и JetBot должны быть в одной сети;
- `ROS_DOMAIN_ID` должен совпадать;
- `ROS_LOCALHOST_ONLY` должен быть `0`;
- предпочтительно согласовать RMW;
- затем уже проверять discovery и RViz/image visualization.

Преподаватель отдельно требует `ROS_DOMAIN_ID`, равный номеру конкретного робота, чтобы несколько JetBot не конфликтовали. Значение `0` — текущее рабочее значение в нашем compose, но при работе в аудитории его нужно заменить на реальный `jetbot_id`.

### 17.2. Camera + lidar + motors одновременно после последнего rebuild

Каждый компонент проверен, bringup снова стартовал, но после последнего rebuild ещё не зафиксирован итоговый лог, где камера одновременно запущена с новым bringup. Это нужно проверить перед следующим большим изменением.

---

## 18. Диагностический чеклист для агента

### JetBot недоступен

На Mac:

```bash
ping 192.168.55.1
networksetup -listallhardwareports
```

или по Wi‑Fi — актуальный IP с дисплея JetBot.

SSH:

```bash
ssh jetbot@<JETBOT_IP>
```

### Container не запущен

На JetBot host:

```bash
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose up -d
docker ps
```

### Нужно войти в ROS

```bash
docker compose exec -it jetbot_educational bash
```

### ROS package не найден после recreate

```bash
source /opt/ros/humble/install/setup.bash
cd /home/app/ros2_ws
colcon build --symlink-install --packages-select <package>
source install/setup.bash
```

### `ros2 topic list` показывает странно мало topics

Сначала проверить, запущен ли bringup:

```bash
ros2 node list
```

Если launch отсутствует — поднять его. Не пытаться чинить DDS до проверки реальных процессов.

### Motor serial error / port 8000 busy

Почти наверняка дублированный bringup.

Остановить старый launch или:

```bash
# host
docker compose restart jetbot_educational
```

### Camera plugin missing

Проверить:

```bash
gst-inspect-1.0 nvarguscamerasrc
gst-inspect-1.0 nvvidconv
```

и camera-related Compose env/mounts из раздела 13.

После изменений Compose нужен:

```bash
docker compose up -d --force-recreate
```

Обычный `restart` не применяет новые mounts/groups/environment.

### Camera ~0.7 Hz

Проверить, что в `publish_raw.py`:

```python
msg.data = array('B', data)
```

а не:

```python
msg.data = frame.tobytes()
```

---

## 19. Правила для дальнейшего AI-агента

1. Не утверждать, что шаг выполнен, только потому что команда выглядит правильной. Требовать/проверять фактический вывод.
2. Давать пользователю **один логический шаг за раз**. Пользователь предпочитает: команда → вывод → следующая команда. Если несколько проверок тесно связаны, давать один copy-paste block.
3. Всегда явно говорить, где выполнять команду: **Mac**, **JetBot host** или **ROS container**.
4. Не запускать второй hardware bringup поверх первого.
5. Не делать широкие `pkill` и не убивать чужие процессы.
6. Не переустанавливать ROS/NVIDIA stack без необходимости: рабочая система уже есть.
7. Не менять base image, пока проблема не локализована конкретным тестом.
8. После `--force-recreate` помнить, что `src` persistent, а `build/install` могут потребовать rebuild.
9. Сохранять `docker-compose.yml.bak`; перед новым системным изменением делать backup.
10. Для camera performance не использовать `bytes` assignment в `sensor_msgs/Image.data`; использовать `array('B', data)`.
11. Не считать warnings фатальными, если конечный health/test успешен. Оценивать по результату pipeline/controller.
12. При работе с real robot не наследовать автоматически `ROS_DOMAIN_ID=42` и `ROS_LOCALHOST_ONLY=1` из Mac simulation script.
13. Если в аудитории несколько JetBot, обязательно поставить `ROS_DOMAIN_ID` равным номеру робота, как требует преподаватель.
14. Сначала сохранять и документировать работающую конфигурацию, затем рефакторить.

---

## 20. Ближайший разумный план

1. На JetBot оставить один `activate_all_drivers.launch.py`.
2. В другом shell проверить:
   ```bash
   ros2 node list
   ros2 topic list -t
   ros2 topic hz /scan
   ```
3. Запустить `ros2 run pi_camera publish_raw` в третьем shell.
4. Проверить одновременно:
   ```bash
   ros2 topic hz /scan
   ros2 topic hz /camera/image/raw
   ros2 topic echo /diffbot_base_controller/odom --once
   ```
5. Убедиться, что короткий `/cmd_vel` по-прежнему двигает robot.
6. Убрать timing debug и исправить Ctrl+C shutdown в `publish_raw.py`, если они всё ещё присутствуют.
7. Настроить ROS 2 discovery Mac ↔ JetBot с одинаковым `ROS_DOMAIN_ID`.
8. Вывести `/scan` и `/camera/image/raw` на Mac (RViz / image viewer).
9. Только после этого переходить к заданию движения к ArUco marker.
