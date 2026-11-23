# Лабораторные работы по робототехнике на macOS

Рабочий ноутбук: Mac с Apple Silicon. Используются Gazebo Harmonic и ROS 2 Jazzy.

Скачать проект на Mac:

```bash
mkdir -p ~/Documents/CCM_courses
git clone https://github.com/MakVlad2003/robotics-course-macos.git ~/Documents/CCM_courses/Robotics
```

После клонирования выполнить лабораторные работы по порядку:

1. [Лабораторная работа 1. Настройка программ на ноутбуке с ОС macOS](labs/lab01_setup/README.md).
2. [Лабораторная работа 2. Знакомство с роботом реальным и виртуальным](labs/lab02_sensors_actuators/README.md).
3. [Лабораторная работа 3. Запуск и комплексирование одометрии](labs/lab03_odometry/README.md).
4. [Лабораторная работа 4. Карта и локализация](labs/lab04_mapping/README.md).

[Домашнее задание 2. Восстановление траектории из rosbag](homework/hw02_slam/README.md).

Оформление интерфейсов для демонстраций описано в [DESIGN.md](DESIGN.md).

Исходное описание курса и заданий преподавателя хранится локально в `course_description.pages` и не входит в открытый репозиторий.

## Подключение к учебному JetBot № 3

На 20.11.2026 проверен вход по Wi‑Fi:

```bash
ssh jetbot@192.168.50.206
cd ~/robotics-course
```

При смене адреса посмотреть новый IP на дисплее JetBot. Команды просмотра камеры и WASD находятся на роботе в `~/robotics-course/labs/lab02_sensors_actuators/README.md`.

### Подключение по USB

Включить JetBot, подключить его к Mac штатным USB-кабелем из комплекта и выполнить в терминале Mac:

```bash
ssh jetbot@192.168.55.1
```

Запуски на `jetbotj0` описаны в [истории проекта](history_by_chat/README.md).
