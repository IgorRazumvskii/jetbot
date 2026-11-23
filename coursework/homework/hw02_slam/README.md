# ДЗ 2. Восстановление траектории из rosbag

## 1. Подготовить фрагмент

Из каталога `homework/hw02_slam` скачать первый 89,8-секундный фрагмент. Скрипт читает каталог ZIP по HTTP Range и скачивает выбранную запись (381,1 МиБ). При обрыве повтор той же команды продолжит загрузку. Для распаковки понадобится около 1,8 ГБ свободного места. В архиве пять фрагментов. [Датасет курса](https://disk.yandex.ru/d/Ze3yVF2UNOq6Aw)

```bash
python3 scripts/download_bag.py --segment 0
```

## 2. Воспроизвести проход в демке

На Mac из того же каталога выполнить:

```bash
pixi install --locked
pixi run --locked build
```

Если в `results/replay-first-segment` ещё нет готовых файлов просмотра, один раз запустить экспорт. Нужны ROS 2 из Pixi и `ffmpeg`. Экспорт сохраняет промежуточные состояния SLAM по `/clock` и кодирует камеру и облака по временным меткам rosbag. Для нового прогона выбрать новый выходной каталог и передать его в `pixi run --locked start`.

```bash
export ROS_DOMAIN_ID=83 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
pixi run --locked bash -c 'source install/local_setup.bash && python3 demo/export_replay.py bags/2018-01-28-19-15-41_0 results/replay-first-segment'
```

```bash
pixi run --locked start
```

Открыть [демку ДЗ 2](http://127.0.0.1:8767/). Запустить видео или переместить ползунок под ним. Вкладка **Карта и путь** показывает состояние SLAM в выбранный момент. Вкладка **3D-лидар** показывает прореженное облако из того же фрагмента в системе координат лидара. В обеих панелях есть полноэкранный режим. `Ctrl+C` останавливает локальный сервер.

Конвертер берёт срез 3D-лидара в плоскости движения, от −0,20 до +0,25 м относительно лидара. Базовый фрейм — `base_footprint`, лидарный — `rslidar`. Из `/odom` восстанавливается колёсный TF. Угловая привязка, высота лидара относительно базы (0,507 м) и имена фреймов проверены по TF из записи. Старый TF `map → odom` исключён из воспроизведения. Время берётся из rosbag через `/clock`. [Проекция облака в LaserScan](https://github.com/ros-perception/pointcloud_to_laserscan) · [Воспроизведение Jazzy](https://github.com/ros2/rosbag2/blob/jazzy/README.md#using-rosbag2)

SLAM Toolbox публикует `/map` (`nav_msgs/msg/OccupancyGrid`). Узел пакета публикует `/slam_path` (`nav_msgs/msg/Path`), собирая ключевые кадры по порядку из оптимизированного графа. Координаты в графе обновляются при оптимизации. Поворот стрелки в демке приходит из `/pose`. [Формирование графа в Jazzy](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/src/loop_closure_assistant.cpp)

[Карта и траектория полного прогона первого фрагмента](results/02-full-first-segment.md).

Для запуска без демки собрать каталог `package/` в рабочем пространстве ROS 2 Jazzy, установить его зависимости через `rosdep`, активировать `install/setup.bash` и выполнить `ros2 launch scout_bag_slam reconstruct.launch.py bag:=/абсолютный/путь/к/rosbag`.

## 3. Записать видео для сдачи

Открыть RViz в отдельном терминале перед полным прогоном. В сцене есть карта и траектория. Для показа облака точек включить слой 3D-лидара (`3D lidar scan`) в списке дисплеев. Для объёмного обзора выбрать сохранённый вид `3D overview`.

```bash
export ROS_DOMAIN_ID=82 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
pixi run --locked rviz2 -d "$PWD/rviz/slam.rviz" --ros-args -p use_sim_time:=true
```

Запустить запись окна RViz, затем запустить SLAM в другом терминале с теми же настройками ROS.

```bash
export ROS_DOMAIN_ID=82 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
pixi run --locked bash -c 'source install/local_setup.bash && ros2 launch scout_bag_slam reconstruct.launch.py bag:=bags/2018-01-28-19-15-41_0'
```

На видео должны быть видны появление карты и рост траектории. Сохранить видео в `results/`.
