#!/usr/bin/env bash
# Управление контейнером ROS2 Humble для JetBot.
#
#   ./dev.sh build        собрать образ
#   ./dev.sh up           запустить контейнер (в фоне)
#   ./dev.sh shell        открыть bash в контейнере (можно много терминалов)
#   ./dev.sh run CMD...   выполнить команду в контейнере с окружением ROS
#   ./dev.sh down         остановить и удалить контейнер
#   ./dev.sh status       состояние контейнера
#
# Переменные: ROS_DOMAIN_ID (номер робота), USE_NVIDIA=0 (выключить GPU).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export HOST_UID="$(id -u)" HOST_GID="$(id -g)"
export DISPLAY="${DISPLAY:-:0}"

COMPOSE=(docker compose -f docker-compose.yml)

if [ "${USE_NVIDIA:-1}" = "1" ] && [ -e /dev/nvidiactl ] && ls /usr/lib/x86_64-linux-gnu/libnvidia-glcore.so.* >/dev/null 2>&1; then
    # snap-docker видит хостовую ФС только через /var/lib/snapd/hostfs
    if docker info --format '{{.DockerRootDir}}' 2>/dev/null | grep -q '^/var/snap/'; then
        export HOST_LIB_DIR=/var/lib/snapd/hostfs/usr/lib/x86_64-linux-gnu
    else
        export HOST_LIB_DIR=/usr/lib/x86_64-linux-gnu
    fi
    COMPOSE+=(-f docker-compose.nvidia.yml)
fi

prepare_host() {
    mkdir -p .docker/ignition
    # xauth-cookie с wildcard-хостом: подходит для любого hostname в контейнере
    rm -rf .docker/xauth && touch .docker/xauth
    if command -v xauth >/dev/null && [ -n "${DISPLAY:-}" ]; then
        xauth nlist "$DISPLAY" 2>/dev/null | sed -e 's/^..../ffff/' | xauth -f .docker/xauth nmerge - 2>/dev/null || true
    fi
}

in_container() {
    "${COMPOSE[@]}" exec -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" ros2 "$@"
}

cmd="${1:-shell}"
shift || true

case "$cmd" in
    build)
        "${COMPOSE[@]}" build "$@"
        ;;
    up)
        prepare_host
        "${COMPOSE[@]}" up -d "$@"
        "${COMPOSE[@]}" logs --no-log-prefix ros2 | tail -n 5
        ;;
    shell)
        prepare_host
        in_container bash
        ;;
    run)
        prepare_host
        in_container bash -c "source /etc/ros_env.sh && $*"
        ;;
    down)
        "${COMPOSE[@]}" down "$@"
        ;;
    status)
        "${COMPOSE[@]}" ps
        ;;
    *)
        sed -n '2,12p' "$0"
        exit 1
        ;;
esac
