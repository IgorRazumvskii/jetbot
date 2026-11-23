# Лабораторная работа 4. Карта и локализация

## 1. Картирование

В рабочем контейнере JetBot уже есть `slam_toolbox` для ROS 2 Humble. В `~/robotics-course` на JetBot скопировать [параметры для JetBot](params/mapper_params_jetbot.yaml) в `ros2_ws/src/jetbot_bringup/config/mapper_params_lab04.yaml`. Использованы параметры привязки базового фрейма из [примера курса](https://github.com/KirillMouraviev/jetbot_ros_gazebo/blob/master/config/mapper_params_online_async.yaml) и [примера SLAM Toolbox для Humble](https://github.com/SteveMacenski/slam_toolbox/blob/humble/config/mapper_params_online_async.yaml).

Дождаться `/scan` с драйвера лидара, колёсной одометрии `odom → base_footprint` и трансформа до `lidar_link`. Запустить из `~/robotics-course` на JetBot.

```bash
./dockers/scripts/ros.sh ros2 launch slam_toolbox online_async_launch.py \
  use_sim_time:=false \
  slam_params_file:=/home/app/ros2_ws/src/jetbot_bringup/config/mapper_params_lab04.yaml
```

Скан принимается из `/scan`. Предел картирования 3 м, размер ячейки 5 см. SLAM использует начальные позы из колёсного TF и публикует `map → odom`. Для проверки графа узлов на JetBot выполнить `./dockers/scripts/ros.sh ros2 node info /slam_toolbox`.

В [пульте JetBot](http://127.0.0.1:8766/) открыть **SLAM**. На карте видны свободные ячейки, препятствия и стрелка робота. Флажок **Граф** показывает ключевые кадры и связи. Карта приходит из `/map`, граф — из `/slam_toolbox/graph_visualization`.

Для заезда поставить робота на пол в выбранной стартовой позе и запустить чистое картирование. Проехать на малой скорости вокруг стола и по комнате, наблюдая за добавлением ключевых кадров. После остановки сохранить карту и сериализованный граф.

[Проверка первого запуска](results/01-slam-check.md) и [результаты первого круга](results/02-first-lap/README.md).

## 2. Локализация по сохранённой карте

Остановить узел картирования. Подготовить файлы графа и сканов в доступном контейнеру каталоге. Скопировать [конфиг локализации](params/localization_jetbot.yaml) в `ros2_ws/src/jetbot_bringup/config/localization_params_lab04.yaml` на JetBot.

```bash
cd ~/robotics-course
mkdir -p data/.runtime/lab04/first-lap
cp data/lab04/first-lap/map_serialized.{posegraph,data} data/.runtime/lab04/first-lap/
./dockers/scripts/ros.sh ros2 launch slam_toolbox localization_launch.py \
  use_sim_time:=false \
  slam_params_file:=/home/app/ros2_ws/src/jetbot_bringup/config/localization_params_lab04.yaml
```

В конфиге начальная поза взята из конца заезда вокруг стола. В пульте открыть вкладку **SLAM** и проверить стрелку робота у старта. Если робот переставлен, задать его текущие координаты и курс в системе `map` через топик `/initialpose`. [Запуск локализации в Humble](https://github.com/SteveMacenski/slam_toolbox/blob/humble/launch/localization_launch.py) · [Подписка на начальную позу](https://github.com/SteveMacenski/slam_toolbox/blob/humble/src/slam_toolbox_localization.cpp)

На малой скорости повторить круг по нанесённому на карту маршруту. Сверять положение стрелки с поворотами и остановками робота. Остановиться на стартовой отметке и проверить конечную позу.

[Протокол заезда в режиме локализации](results/03-localization.md).
