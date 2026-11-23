# Лабораторная работа 3. Запуск и комплексирование одометрии

На роботе `jetbotj3` использовать проект `~/robotics-course`. Команды аппаратной части и журнал прогонов находятся на роботе в `labs/lab03_odometry/README.md`. Здесь приведены команды для Mac.

## 1. Трансформы робота

Открыть [дерево TF с jetbotj3](results/tf-tree-jetbotj3.pdf), полученное через `ros2 run tf2_tools view_frames` в работающем контейнере. В дереве `odom → base_footprint → base_link`. От `base_link` идут фреймы камеры, лидара, опорного шарика и обоих колёс.

Из корня проекта запустить передачу данных с робота по SSH:

```bash
ssh -T jetbot@192.168.50.206 \
  'cd ~/robotics-course && ./dockers/scripts/ros.sh python3 - send' \
  < labs/lab03_odometry/relay.py \
  | ROS_DOMAIN_ID=3 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
      ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_STATIC_PEERS= \
      pixi run --manifest-path tools/ros-jazzy/pixi.toml --as-is \
      python labs/lab03_odometry/relay.py receive
```

В другом терминале запустить локальный RViz:

```bash
ROS_DOMAIN_ID=3 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_STATIC_PEERS= \
  pixi run --manifest-path tools/ros-jazzy/pixi.toml --as-is \
  rviz2 -d labs/lab03_odometry/tf.rviz
```

В конфигурации выбран фиксированный фрейм `odom`. По умолчанию на сетке с шагом 5 см видны `base_link` (корпус), `camera_link` (камера) и `lidar_link` (лидар). Красная ось — X, зелёная — Y, синяя — Z. Фреймы колёс и опорного шарика можно включить в `TF → Frames`, а полную иерархию открыть в `TF → Tree`.

Чтобы повернуть сцену, выберите инструмент перемещения камеры (`Move Camera`) и потяните сцену в центральной области, удерживая левую кнопку. На трекпаде нажмите до щелчка и ведите палец, удерживая нажатие. Прокрутка меняет масштаб. Курс, наклон и расстояние до точки обзора можно задать вручную в панели `Views → Current View` с помощью параметров `Yaw`, `Pitch` и `Distance`.

Перед следующим этапом дождаться появления цепочки фреймов в RViz. Передача идёт в сторону Mac и включает `/tf`, `/tf_static` и колесную одометрию.

Результаты для демонстрации находятся в `results/`. См. [проверку после перезапуска JetBot](results/01-tf-check.md).

## 2. Визуализация колёсной одометрии

Открыть [пульт JetBot на Mac](teleop/README.md). Во вкладке **Колёсная** смотреть положение и траекторию во время заезда. Перед заездом отметить точку старта и сбросить одометрию перезапуском драйверов. Сохранить замеры после одного и после трёх кругов в `results/`.

## 3. Лидарная одометрия

На JetBot в `~/robotics-course` клонировать ветку `ros2` пакета [rf2o_laser_odometry](https://github.com/MAPIRlab/rf2o_laser_odometry/tree/ros2) в `ros2_ws/src`. Проверенная ревизия — `b38c68e46387b98845ecbfeb6660292f967a00d3`. До сборки скопировать [файл запуска для JetBot](jetbot_lab03_rf2o.launch.py) в `ros2_ws/src/rf2o_laser_odometry/launch/`.

```bash
./dockers/scripts/ros.sh env MAKEFLAGS=-j1 CMAKE_BUILD_PARALLEL_LEVEL=1 bash -c '
  cd /home/app/ros2_ws
  colcon build --symlink-install --executor sequential --packages-select rf2o_laser_odometry
'
```

После запуска драйверов дождаться свежего `/scan` и трансформа `base_footprint → lidar_link`, затем запустить RF2O в отдельном терминале JetBot.

```bash
./dockers/scripts/ros.sh ros2 launch rf2o_laser_odometry jetbot_lab03_rf2o.launch.py
```

RF2O читает `/scan` и пишет независимую позу в `/odom_rf2o` с фреймом `lidar_odom`. Параметр `publish_tf` выключен, колесный контроллер публикует свой трансформ как прежде.

В пульте открыть вкладку **Лидарная**. Сверху видны точки текущего скана в координатах `lidar_link` с выбираемым радиусом. Снизу — траектория и показания RF2O. Для сравнения запустить обе одометрии с одной физической стартовой позы. Снять оба показания на возврате после одного и после трёх кругов, сохраняя один и тот же старт.

## 4. Комплексирование одометрии

В `ros2_ws/src` JetBot нужны [robot_localization](https://github.com/cra-ros-pkg/robot_localization/tree/humble-devel), ревизия `7ebaee2b7b206942a6580cdfef433c1eb063c23f`, и [geographic_info](https://github.com/ros-geographic-info/geographic_info/tree/1.0.6), тег `1.0.6`. В активном контейнере Ubuntu Focal установлены ARM64-пакеты `libgeographic19` и `libgeographic-dev` версии `1.50.1-1build1` из [Ubuntu Ports](https://ports.ubuntu.com/ubuntu-ports/pool/universe/g/geographiclib/). Для нового контейнера эту зависимость нужно установить снова.

Скопировать [параметры EKF](params/ekf_jetbot.yaml) в `robot_localization/params/`. Положить [файл запуска](jetbot_lab03_ekf.launch.py) и [адаптер RF2O](rf2o_ekf_input.py) в `robot_localization/launch/`. Выполнить на JetBot из `~/robotics-course`.

```bash
./dockers/scripts/ros.sh env MAKEFLAGS=-j1 CMAKE_BUILD_PARALLEL_LEVEL=1 bash -c '
  cd /home/app/ros2_ws
  colcon build --symlink-install --executor sequential \
    --packages-select geographic_msgs robot_localization \
    --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release "-DCMAKE_CXX_FLAGS_RELEASE=-O1 -DNDEBUG"
'
./dockers/scripts/ros.sh ros2 launch robot_localization jetbot_lab03_ekf.launch.py
```

Драйверы и RF2O должны работать до запуска фильтра. EKF берёт продольную скорость, измерение нулевой боковой скорости колёсной базы и угловую скорость из `/diffbot_base_controller/odom`. От RF2O поступают X, Y и курс. Адаптер передаёт позу в `/lab03/rf2o_for_ekf` и задаёт стартовые стандартные отклонения 5 см и 5°. Это параметры настройки, измеренной калибровки для них пока нет.

В режиме `odom1_relative` первая поза RF2O задаёт начало отсчёта. Фильтр выдаёт `/odometry/filtered` в `ekf_odom`. `publish_tf=false` оставляет публикацию `odom → base_footprint` колёсному контроллеру.

В пульте открыть **EKF**. Три траектории рисуются от общего старта. Кнопка **Отметить старт** готовит общий ноль на всех вкладках. Пульт фиксирует исходные позы при первой ненулевой команде. Для эксперимента поставить робота на стартовую отметку, запустить обе одометрии и EKF с неё и выполнить один круг с возвращением на метку.
