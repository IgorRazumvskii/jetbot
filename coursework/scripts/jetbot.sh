#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION=jetbot
SOCKET=robotics-course
WORLD="$ROOT/labs/lab02_sensors_actuators/worlds/tugbot_warehouse_jetbot.sdf"

gazebo_env() {
  export GZ_IP=127.0.0.1
  export GZ_PARTITION=robotics
  export GZ_SIM_RESOURCE_PATH="$ROOT/src/jetbot_ros_gazebo/models"
}

ros_env() {
  gazebo_env
  export ROS_DOMAIN_ID=42
  export ROS_LOCALHOST_ONLY=1
  export ROS_LOG_DIR="$ROOT/ros2_ws/log/runtime"
  mkdir -p "$ROS_LOG_DIR"
  cd "$ROOT"
  set +u
  source ros2_ws/install/setup.bash
  set -u
}

stop_session() {
  if ! tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    return
  fi
  while IFS= read -r pane_pid; do
    if [[ "$pane_pid" != "$$" ]]; then
      kill -TERM "$pane_pid" 2>/dev/null || true
    fi
  done < <(tmux -L "$SOCKET" list-panes -s -t "$SESSION" -F '#{pane_pid}' 2>/dev/null)
  sleep 0.3
  tmux -L "$SOCKET" kill-session -t "$SESSION" 2>/dev/null || true
}

case "${1:-up}" in
  server)
    gazebo_env
    exec gz sim -v 4 -r -s "$WORLD"
    ;;
  gui)
    gazebo_env
    gz sim -v 4 -g &
    gui_pid=$!
    trap 'kill "$gui_pid" 2>/dev/null || true; wait "$gui_pid" 2>/dev/null || true' EXIT
    trap 'exit 0' HUP INT TERM
    sensitivity_applied=false
    for ((attempt=0; attempt<40; attempt++)); do
      if ! kill -0 "$gui_pid" 2>/dev/null; then
        wait "$gui_pid" || true
        stop_session
        exit 0
      fi
      sensitivity="${JETBOT_GUI_SENSITIVITY:-0.15}"
      result="$(gz service -s /gui/camera/view_control/sensitivity \
        --reqtype gz.msgs.Double --reptype gz.msgs.Boolean \
        --timeout 1000 --req "data: $sensitivity" 2>&1 || true)"
      if [[ "$result" == *'data: true'* ]]; then
        echo "Чувствительность камеры: $sensitivity"
        sensitivity_applied=true
        break
      fi
      sleep 1
    done
    if [[ "$sensitivity_applied" == false ]]; then
      echo 'Не удалось изменить чувствительность камеры; проверьте окно Gazebo.' >&2
    fi
    wait "$gui_pid" || true
    stop_session
    ;;
  bridge)
    cd "$ROOT/tools/ros-jazzy"
    exec pixi run --frozen bash --noprofile --norc "$ROOT/scripts/jetbot.sh" bridge-run
    ;;
  bridge-run)
    ros_env
    exec ros2 run ros_gz_bridge parameter_bridge \
      /model/jetbot/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist \
      /model/jetbot/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry \
      /world/world_demo/model/jetbot/link/camera_link/sensor/color/image@sensor_msgs/msg/Image@gz.msgs.Image \
      /world/world_demo/model/jetbot/link/camera_link/sensor/color/camera_info@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo \
      /world/world_demo/model/jetbot/link/lidar_link/sensor/scan_front/scan@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan
    ;;
  ros)
    cd "$ROOT/tools/ros-jazzy"
    exec pixi run --frozen bash --noprofile --norc "$ROOT/scripts/jetbot.sh" ros-shell
    ;;
  ros-shell)
    ros_env
    export PS1='[JetBot ROS] \w $ '
    exec bash --noprofile --norc -i
    ;;
  down)
    if command -v tmux >/dev/null 2>&1; then
      stop_session
    fi
    ;;
  up)
    if ! command -v tmux >/dev/null 2>&1; then
      echo 'tmux не установлен. Один раз выполните: brew install tmux' >&2
      exit 1
    fi
    if tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
      if [[ -n "$(tmux -L "$SOCKET" list-clients -t "$SESSION" -F '#{client_tty}' 2>/dev/null)" ]]; then
        echo 'Сессия JetBot уже открыта в другом терминале.' >&2
        exit 1
      fi
      stop_session
    fi
    if pgrep -f 'gz sim.*tugbot_warehouse_jetbot.sdf' >/dev/null 2>&1; then
      echo 'Старая сцена склада ещё запущена. Остановите её в прежнем терминале, затем повторите команду.' >&2
      exit 1
    fi
    cd "$ROOT"
    trap stop_session EXIT
    trap 'exit 0' HUP INT TERM
    tmux -L "$SOCKET" new-session -d -s "$SESSION" -n server -c "$ROOT" 'bash scripts/jetbot.sh server'
    tmux -L "$SOCKET" set-option -g mouse on
    tmux -L "$SOCKET" set-option -g history-limit 50000
    tmux -L "$SOCKET" set-option -g mode-keys vi
    tmux -L "$SOCKET" set-option -t "$SESSION" remain-on-exit on
    tmux -L "$SOCKET" new-window -d -t "$SESSION" -n gui -c "$ROOT" 'bash scripts/jetbot.sh gui'
    tmux -L "$SOCKET" new-window -d -t "$SESSION" -n bridge -c "$ROOT" 'bash scripts/jetbot.sh bridge'
    tmux -L "$SOCKET" new-window -d -t "$SESSION" -n ros -c "$ROOT" 'bash scripts/jetbot.sh ros'
    tmux -L "$SOCKET" select-window -t "$SESSION:gui"
    tmux -L "$SOCKET" attach-session -t "$SESSION"
    ;;
  *)
    echo "Использование: $0 [up|down]" >&2
    exit 2
    ;;
esac
