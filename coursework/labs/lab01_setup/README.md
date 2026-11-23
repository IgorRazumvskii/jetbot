# Лабораторная работа 1. Настройка программ на ноутбуке с ОС macOS

## Краткое содержание:

1. Установить и запустить ROS 2 на ноутбуке.
2. Импортировать модель робота в симулятор Gazebo.
3. Установить и настроить Visual Studio Code.

## Дополнительные материалы:

- [Gazebo](https://gazebosim.org/docs/harmonic/).
- [ROS 2 Jazzy](https://docs.ros.org/en/jazzy/).
- [Модель JetBot](https://github.com/KirillMouraviev/jetbot_ros_gazebo).

## Описание используемого оборудования и программного обеспечения:

Ноутбук с macOS и процессором Apple Silicon. Gazebo Harmonic устанавливается через Homebrew, ROS 2 Jazzy запускается в окружении Pixi. Команды ниже выполняются из терминала macOS.

### 1. Установка и запуск ROS 2

Установить [Homebrew](https://brew.sh/) и [Pixi](https://pixi.sh/). Установить Gazebo:

```bash
brew tap osrf/simulation
brew trust osrf/simulation
brew install gz-harmonic
```

Окружение ROS 2 уже описано в `tools/ros-jazzy/pixi.toml`. Установить его и проверить запуск:

```bash
cd ~/Documents/CCM_courses/Robotics/tools/ros-jazzy
pixi install --locked
pixi run --frozen ros2 --help
```

Должна появиться справка команды `ros2`.

### 2. Импорт модели JetBot в Gazebo

В папке `src/jetbot_ros_gazebo` находится пакет с моделью преподавателя. В файле `models/jetbot/model.config` выбрана детализированная модель `model_high_resolution.sdf`.

Сначала запустить сервер Gazebo. Оставить терминал открытым:

```bash
cd ~/Documents/CCM_courses/Robotics
export GZ_IP=127.0.0.1 GZ_PARTITION=robotics
export GZ_SIM_RESOURCE_PATH="$PWD/src/jetbot_ros_gazebo/models"
gz sim -v 4 shapes.sdf -s
```

Во втором терминале открыть окно Gazebo:

```bash
export GZ_IP=127.0.0.1 GZ_PARTITION=robotics
gz sim -v 4 -g
```

В третьем терминале добавить робота:

```bash
cd ~/Documents/CCM_courses/Robotics
export GZ_IP=127.0.0.1 GZ_PARTITION=robotics
gz service -s /world/shapes/create \
  --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 5000 \
  --req "sdf_filename: \"$PWD/src/jetbot_ros_gazebo/models/jetbot/model_high_resolution.sdf\", name: \"jetbot\""
```

Ответ `data: true` означает, что модель добавлена. Найти `jetbot` в дереве объектов Gazebo. После проверки завершить сервер и окно Gazebo сочетанием `Ctrl+C` в их терминалах.

### 3. Установка и настройка Visual Studio Code

Установить [Visual Studio Code](https://code.visualstudio.com/) и открыть в нём папку `~/Documents/CCM_courses/Robotics`. Для команды `code` в палитре команд VS Code выполнить `Shell Command: Install 'code' command in PATH`.
