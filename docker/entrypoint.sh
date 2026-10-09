#!/bin/bash
# Entrypoint контейнера: подключить GPU (если проброшена) и выполнить команду.
# Контейнер работает от пользователя ros, а настройка GPU требует root — для неё
# в образе есть беспарольный sudo.
sudo -n /usr/local/bin/setup_host_gpu.sh || echo "[gpu] настройка NVIDIA не удалась, будет программный рендеринг"

source /opt/ros/humble/setup.bash
exec "$@"
