# ROS2 Humble + Gazebo Fortress для курса "Интеллектуальная робототехника" (JetBot)
FROM osrf/ros:humble-desktop-full

ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive

# Пакеты для ЛР 2 и ДЗ 1:
#  - teleop_twist_keyboard, twist_mux     — телеуправление и мультиплексор cmd_vel
#  - image_transport_plugins              — просмотр /compressed топиков в rviz/rqt
#  - gstreamer                            — проверка драйвера камеры без железа (videotestsrc)
#  - xterm                                — запуск teleop из launch-файла в отдельном окне
#  - mesa-utils                           — glxinfo для проверки проброса GPU
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-teleop-twist-keyboard \
        ros-humble-twist-mux \
        ros-humble-image-transport-plugins \
        ros-humble-rqt-image-view \
        ros-humble-camera-calibration \
        python3-opencv \
        python3-pip \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        xterm \
        mesa-utils \
        sudo \
        git nano vim less tree bash-completion \
        iputils-ping iproute2 net-tools openssh-client \
    && rm -rf /var/lib/apt/lists/*

# STag-маркеры (маркер курса — STag HD15)
RUN pip3 install --no-cache-dir stag-python==1.1.1

# Пользователь с тем же UID/GID, что и на хосте: файлы в смонтированном
# ros2_ws не становятся root-овыми, а X-сервер пускает его без xhost.
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME} \
    && usermod -aG video,dialout ${USERNAME} \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

COPY entrypoint.sh /entrypoint.sh
COPY setup_host_gpu.sh /usr/local/bin/setup_host_gpu.sh
COPY bashrc_ros.sh /etc/ros_env.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/setup_host_gpu.sh \
    && echo 'source /etc/ros_env.sh' >> /home/${USERNAME}/.bashrc \
    && echo 'source /etc/ros_env.sh' >> /root/.bashrc

ENV ROS_USER=${USERNAME}
WORKDIR /home/${USERNAME}/ros2_ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
