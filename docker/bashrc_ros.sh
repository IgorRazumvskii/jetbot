# Окружение ROS2 для интерактивных shell-сессий в контейнере
source /opt/ros/humble/setup.bash

ROS_WS="$HOME/ros2_ws"
if [ -f "$ROS_WS/install/setup.bash" ]; then
    source "$ROS_WS/install/setup.bash"
fi

if [ -f /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash ]; then
    source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash
fi

export RCUTILS_COLORIZED_OUTPUT=1

# Сборка workspace и обновление окружения в текущем shell
cb() {
    (cd "$ROS_WS" && colcon build --symlink-install "$@") && source "$ROS_WS/install/setup.bash"
}
