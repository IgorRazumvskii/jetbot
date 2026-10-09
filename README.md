# JetBot: ЛР 2 (телеуправление и камера) и ДЗ 1 (подъезд к маркеру)

Ноутбук работает в Docker-контейнере с ROS2 Humble, робот — в своём контейнере `jetbot_ros2_mipt-jetbot_educational-1`.
Оба должны быть **в одной Wi-Fi сети** (точка доступа телефона) и с одинаковым `ROS_DOMAIN_ID` (у нашего робота — `0`).

Где выполнять команду, подписано у каждого блока:
- **[ноутбук]** — обычный терминал на хосте;
- **[ноутбук-контейнер]** — терминал внутри `./dev.sh shell` (приглашение `ros@danil-G16-24`);
- **[робот]** — внутри контейнера на роботе (приглашение `app@jetbotj0`).

## 0. Первая настройка ноутбука (один раз)

**[ноутбук]**
```bash
git clone -b hw1-laptop https://github.com/IgorRazumvskii/jetbot.git jetbot_work
cd jetbot_work
git clone https://github.com/KirillMouraviev/jetbot_ros_gazebo ros2_ws/src/jetbot_ros_gazebo   # модель для Gazebo
./dev.sh build      # образ jetbot-ros2-humble (~4 ГБ, первый раз долго)
./dev.sh up         # запустить контейнер в фоне
./dev.sh shell
```
**[ноутбук-контейнер]**
```bash
cb                  # = colcon build --symlink-install + source install/setup.bash
```

Команды `dev.sh`:

| команда | что делает |
|---|---|
| `./dev.sh build` | собрать образ (после правок в `docker/`) |
| `./dev.sh up` / `down` | запустить / удалить контейнер |
| `./dev.sh shell` | открыть ещё один терминал в контейнере |
| `./dev.sh status` | состояние контейнера |
| `ROS_DOMAIN_ID=N ./dev.sh shell` | терминал для робота с другим номером |

GPU (NVIDIA) пробрасывается автоматически, GUI (rviz2, rqt, Gazebo) открываются на рабочем столе.
Docker на этой машине стоит через snap, поэтому GPU подключается не через `--gpus`, а скриптом
`docker/setup_host_gpu.sh` — ничего делать не нужно. Отключить GPU: `USE_NVIDIA=0 ./dev.sh up`.

## 1. Запуск робота (каждый раз после включения)

IP робота показан на дисплее сзади (в нашей точке доступа был `172.20.10.4`). Пароль: `jetbot`.

**Терминал 1 [ноутбук] → [робот] — драйверы лидара и моторов**
```bash
ssh jetbot@172.20.10.4
docker exec -it jetbot_ros2_mipt-jetbot_educational-1 bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 launch jetbot_bringup activate_all_drivers.launch.py
```

**Терминал 2 [ноутбук] → [робот] — камера**
```bash
ssh jetbot@172.20.10.4
docker exec -it jetbot_ros2_mipt-jetbot_educational-1 bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 run pi_camera publish_raw
```
Ожидается `Публикую 1280x720 bgr8 @ 30 FPS`, через 10 с — `30.0 FPS`.

Если контейнера на роботе нет (`docker ps` пустой):
`cd ~/IntelligentRobotics/jetbot_ros2_mipt && docker compose up -d`.

**Проверка с ноутбука [ноутбук-контейнер]**
```bash
ros2 topic list     # должны быть /scan, /cmd_vel, /camera/image/raw, /camera/image/raw/compressed
```

## 2. ЛР 2: лидар, телеуправление, камера

**RViz [ноутбук-контейнер]**
```bash
rviz2 -d ~/ros2_ws/real_robot.rviz
```
Если с нуля: Fixed Frame = `lidar_link`, Add → By topic → `/scan` → LaserScan.

**Телеуправление [ноутбук-контейнер]**
```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p speed:=0.15 -p turn:=0.8
```
`i` вперёд, `,` назад, `j`/`l` поворот, `k` стоп, `q`/`z` быстрее/медленнее.

**Камера [ноутбук-контейнер]**
```bash
ros2 run rqt_image_view rqt_image_view
```
В списке (кнопка обновления, если пусто) выбрать **`/camera/image/raw/compressed`**.
Несжатый `/camera/image/raw` по Wi-Fi не смотреть — 80 МБ/с не пролезут.

### Драйвер камеры `publish_raw`

Код: [robot/pi_camera_ros/pi_camera/publish_raw.py](robot/pi_camera_ros/pi_camera/publish_raw.py).
На роботе лежит в `~/IntelligentRobotics/jetbot_ros2_mipt/src/pi_camera_ros/` (в контейнере — `/home/app/ros2_ws/src/`),
прежняя версия сохранена рядом как `publish_raw.py.prev`.

- GStreamer `nvarguscamerasrc` → сырые BGR-кадры → `/camera/image/raw` (1280x720, 30 FPS);
- JPEG 640x360 → `/camera/image/raw/compressed` (для ноутбука по Wi-Fi);
- параметры: `width`, `height`, `fps`, `flip_method` (2 — поворот на 180°), `compressed_rate`,
  `compressed_scale`, `jpeg_quality`, `camera_info_file`, `source:=test` (videotestsrc, проверка без камеры).

Обновить драйвер на роботе после правок **[ноутбук]**:
```bash
scp robot/pi_camera_ros/pi_camera/publish_raw.py \
    jetbot@172.20.10.4:~/IntelligentRobotics/jetbot_ros2_mipt/src/pi_camera_ros/pi_camera/
```
Пересборка не нужна (сборка `--symlink-install`), достаточно перезапустить `publish_raw`.

## 3. ДЗ 1: подъезд к маркеру

Маркер курса — **STag HD15, id 54**, сторона чёрного квадрата **8 см** (фото: `markers/photo_*.jpg`).
Поддерживаются и ArUco (`marker_type: aruco`, генератор: `ros2 run aruco_approach make_marker`).

Пакет [ros2_ws/src/aruco_approach](ros2_ws/src/aruco_approach), параметры для робота —
[config/approach_real.yaml](ros2_ws/src/aruco_approach/config/approach_real.yaml).

Требуемые заданием параметры узла `aruco_approach`:

| параметр | значение | смысл |
|---|---|---|
| `stop_distance` | 0.5 | м, на каком расстоянии от маркера остановиться |
| `max_linear_speed` | 0.15 | м/с |
| `max_angular_speed` | 1.0 | рад/с |
| `marker_size` | 0.08 | м, реальный размер маркера |

Все шаги ниже — при работающих драйверах и камере на роботе (раздел 1).

### 3.1. Калибровка фокуса (уже сделана: `focal_length_px: 388.8`)

Повторить, если меняли камеру/разрешение. Маркер ровно перед камерой на 0.5 м, по центру кадра.
**[ноутбук-контейнер]**
```bash
ros2 run aruco_approach estimate_focal --ros-args \
  -p true_distance:=0.5 -p marker_size:=0.08 \
  -p marker_type:=stag -p aruco_dictionary:=HD15 -p marker_id:=54 \
  -p use_compressed:=true
```
Результат `focal_length_px = ...` вписать в `config/approach_real.yaml`.

### 3.2. Проверка вхолостую (робот не едет)

**[ноутбук-контейнер]**
```bash
ros2 launch aruco_approach aruco_approach.launch.py cmd_vel_out:=/cmd_vel_dry view:=true
```
В окне отладки: `dist` ≈ реальному расстоянию, маркер слева → `w > 0`, закрыть маркер → `WAIT`, через ~2 с `SEARCH`.

### 3.3. Запуск

**[ноутбук-контейнер]**
```bash
ros2 launch aruco_approach aruco_approach.launch.py teleop:=true view:=true
```
Откроется окно xterm с teleop (кликнуть в него, чтобы перехватить управление) и окно отладки.
Остановить робота: `Ctrl+C` в терминале с launch.

Параметры можно переопределить при запуске:
`stop_distance:=0.4 max_linear_speed:=0.1 max_angular_speed:=0.8 marker_size:=0.08`,
или менять на лету: `ros2 param set /aruco_approach linear_kp 0.6`.

Цепочка команд:
```
teleop_twist_keyboard -> /cmd_vel_teleop -> twist_nonzero_filter -> /cmd_vel_teleop_active -+
                                                                                             +-> twist_mux -> /cmd_vel -> робот
aruco_approach --------------------------------------------------------> /cmd_vel_nav ------+
```
`twist_mux` отдаёт приоритет teleop (100 против 10), но фильтр пропускает к нему только ненулевые
команды — при нулевом/молчащем teleop едет `aruco_approach`. Через 0.7 с после отпускания клавиш
управление возвращается к узлу.

Состояния узла (`ros2 topic echo /aruco_approach/state`):
- `APPROACH` — едет к маркеру: ПИД по углу и по расстоянию, сначала доворачивает, потом едет;
- `REACHED` — стоит на `stop_distance` ± 3 см, снова поедет, если ошибка > 12 см;
- `WAIT` — маркер пропал: 1.5 с стоит (короткое перекрытие);
- `SEARCH` — вращается на месте (0.5 рад/с) в сторону, где маркер видели последним.

### 3.4. Сценарий сдачи

1. Пять стартов с разных мест, откуда маркер виден → остановка в интервале 0.375–0.625 м (мерить от камеры).
2. Во время подъезда отвернуть робота teleop-ом так, чтобы маркер ушёл из кадра, и отпустить → робот находит маркер и доезжает.
3. Закрыть маркер предметом на несколько секунд → робот ждёт / ищет и доезжает после открытия.

### Тесты

**[ноутбук-контейнер]**
```bash
cd ~/ros2_ws/src/aruco_approach && python3 -m pytest -q test
```
Проверяют распознавание и дальность на синтетических кадрах, фото маркера STag и ПИД.

## Если что-то не работает

- **Не видно топиков робота** — ноутбук и робот в разных сетях (ноутбук может сам переключиться на другой
  Wi-Fi: `nmcli -t -f ACTIVE,SSID dev wifi | grep yes`), или разный `ROS_DOMAIN_ID`.
- **Робот пропал из сети / перезагрузился** — обычно просадка батареи. После загрузки контейнер поднимается сам,
  драйверы и камеру нужно запустить заново (раздел 1).
- **`Package 'pi_camera' not found`** — команда выполнена на ноутбуке, а не на роботе.
- **`rqt_image_view` пустой** — нажать обновление списка топиков, DDS находит робота за пару секунд.
- **Маркер STag не находится вблизи** — детектор сам повторяет поиск на уменьшенном кадре; проверить, что маркер целиком в кадре.
- **Робот «не дотягивает» до цели на малой скорости** — поднять `min_linear_speed` (например 0.05)
  и `min_angular_speed` (например 0.3) в `approach_real.yaml`.

## Структура

```
dev.sh                      управление контейнером
docker/                     Dockerfile, entrypoint, подключение GPU
docker-compose*.yml
robot/pi_camera_ros/        драйвер камеры для робота (publish_raw.py)
ros2_ws/src/aruco_approach/ ДЗ 1: узлы, launch, конфиги, тесты
ros2_ws/real_robot.rviz     конфиг RViz для робота
markers/                    маркеры для печати
```
Симуляция в Gazebo (сенсоры JetBot в мире склада) — не доделана.
