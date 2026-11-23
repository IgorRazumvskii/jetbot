# diffdrive_jetbot

Аппаратный интерфейс ROS 2 для дифференциального привода JetBot.

## Возможности
- Совместимость с `diff_drive_controller` из `ros2_control`.
- Управление скоростью двух моторов и получение обратной связи по последовательному порту.

## Установка
```bash
# Клонировать пакет в рабочее пространство
cd ~/ros2_ws/src
git clone https://github.com/your_user/diffdrive_jetbot.git
# Собрать пакет
cd ~/ros2_ws
colcon build --packages-select diffdrive_jetbot
```

## Запуск
```bash
# Запустить аппаратный интерфейс, контроллеры и RViz
ros2 launch diffdrive_jetbot diffbot.launch.py
```
