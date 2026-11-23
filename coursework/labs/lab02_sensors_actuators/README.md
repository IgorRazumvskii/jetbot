# Лабораторная работа 2. Знакомство с роботом реальным и виртуальным. Работа с интерфейсами коммуникации, сенсорами, актуаторами и устройствами вывода через ROS

## Виртуальный робот в симуляторе Gazebo

### 1. Установка ROS 2 Jazzy + Gazebo на ноутбук

Выполнить [лабораторную работу 1](../lab01_setup/README.md). Создать рабочее пространство ROS 2 и собрать пакет JetBot:

```bash
cd ~/Documents/CCM_courses/Robotics
mkdir -p ros2_ws/src
test -e ros2_ws/src/jetbot_ros_gazebo || ln -s ../../src/jetbot_ros_gazebo ros2_ws/src/jetbot_ros_gazebo
cd tools/ros-jazzy
pixi shell
```

В открывшемся окружении Pixi выполнить:

```bash
cd ../../ros2_ws
colcon build --symlink-install
source install/setup.zsh
ros2 pkg prefix jetbot_ros_gazebo
```

Последняя команда должна вывести путь к пакету. Выйти из окружения Pixi командой `exit`.

### 2. Запуск Gazebo

Один раз установить `tmux`:

```bash
brew install tmux
```

Закрыть ранее запущенные вручную сервер и окно Gazebo. Запустить сцену, окно Gazebo, мост с ROS 2 и терминал ROS 2 одной командой:

```bash
cd ~/Documents/CCM_courses/Robotics
./scripts/jetbot.sh
```

В `tmux` открываются окна `server`, `gui`, `bridge`, `ros`. Переключаться между ними: `Ctrl+B`, затем номер окна `0`–`3` или `n`/`p`. Вывод прокручивается трекпадом. Для прокрутки с клавиатуры нажать `Ctrl+B`, затем `[`, для выхода — `q`.

Закрытие терминала с `tmux`, окна Gazebo или отсоединение через `Ctrl+B`, затем `d` завершает всю сессию. После этого команду запуска можно выполнить снова. Для явной остановки из другого терминала:

```bash
./scripts/jetbot.sh down
```

### 3. Запуск Gazebo с моделькой джетбота на складе

Сцена `worlds/tugbot_warehouse_jetbot.sdf` основана на складе из задания преподавателя. Вместо Tugbot в ней установлен JetBot. Файл `model.config` выбирает детализированную модель `model_high_resolution.sdf`. Робот расположен перед зарядной станцией и мишенью, камерой к ним.

Дождаться появления склада и робота в окне Gazebo. В панели **Teleop** отправить короткую команду движения. Мост Gazebo–ROS 2 запускается в окне `bridge`. В окне `ros` проверить сообщения:

```bash
ros2 topic list
ros2 topic echo /model/jetbot/odometry --once --timeout 10
ros2 topic echo /world/world_demo/model/jetbot/link/lidar_link/sensor/scan_front/scan --once --timeout 10 --field header
ros2 topic echo /world/world_demo/model/jetbot/link/camera_link/sensor/color/image --once --timeout 10 --field header
```

При запуске чувствительность камеры Gazebo устанавливается в `0.15`. Если прокрутка трекпадом всё ещё слишком резкая, в окне `ros` установить меньшее значение:

```bash
gz service -s /gui/camera/view_control/sensitivity \
  --reqtype gz.msgs.Double --reptype gz.msgs.Boolean \
  --timeout 2000 --req 'data: 0.08'
```

Ответ `data: true` означает, что настройка применена.

## Реальный JetBot

Для `jetbotj3` открыть `~/robotics-course/labs/lab02_sensors_actuators/README.md` на самом роботе. Там находятся актуальные команды запуска драйверов, WASD и просмотра камеры на Mac. Шаги ниже относятся к прежнему окружению `jetbotj0`.

### 1. Подключение к роботу

На Mac выполнить:

```bash
ssh jetbot@172.20.10.4
```

Адрес проверен 05.10.2026 и может измениться. Использовать актуальный адрес робота.

### 2. Запуск драйверов

В первом SSH-терминале на хосте робота (`jetbot@jetbotj0`) выполнить:

```bash
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose up -d
docker compose exec -it jetbot_educational bash
```

В контейнере (`app@jetbotj0:~/ros2_ws`) выполнить:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
ros2 launch jetbot_bringup activate_all_drivers.launch.py
```

Оставить терминал работать. Если драйверы уже запущены, повторно launch не выполнять. В подтверждённой сессии они уже работали.

### 3. Управление с клавиатуры

Во втором SSH-терминале на хосте робота выполнить:

```bash
cd ~/IntelligentRobotics/jetbot_ros2_mipt
docker compose exec -it jetbot_educational bash
```

В контейнере выполнить:

```bash
source /opt/ros/humble/install/setup.bash
source /home/app/ros2_ws/install/setup.bash
python3 /home/app/ros2_ws/src/wasd_teleop.py
```

Включить английскую раскладку. Удерживать W/S для движения вперёд/назад, A/D для поворота. Пробел — остановка, Q или Ctrl+C — выход. При отсутствии ввода в течение 0,3 с скрипт отправляет нулевую команду.

Скрипт публикует в `/cmd_vel`. Задаваемые скорости: ±0,5 м/с и ±3 рад/с. 05.10.2026 пользователь подтвердил, что робот ездит после этих изменений. Фактические скорости не измерялись.

Скрипт хранится в подключённой папке `src` и сохраняется при пересоздании контейнера. Копия для восстановления находится в [scripts/wasd_teleop.py](../../scripts/wasd_teleop.py). Если файл на роботе отсутствует, на Mac из корня проекта выполнить:

```bash
scp scripts/wasd_teleop.py jetbot@172.20.10.4:~/IntelligentRobotics/jetbot_ros2_mipt/src/wasd_teleop.py
```

### 4. Продолжение работы

Третий терминал использовать для диагностики и камеры. По истории предыдущей сессии камера публиковала `/camera/image/raw` с частотой около 29–30 Гц. В текущей сессии камера повторно не проверена. Следующий шаг — воспроизвести её запуск вместе с драйверами. Подробности сохранены в [history_by_chat/README.md](../../history_by_chat/README.md).
