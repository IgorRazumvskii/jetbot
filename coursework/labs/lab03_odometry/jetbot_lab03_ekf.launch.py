"""Run the lab EKF and its RF2O input adapter on JetBot."""

from pathlib import Path
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    package = Path(get_package_share_directory("robot_localization"))
    return LaunchDescription([
        ExecuteProcess(
            cmd=[sys.executable, str(package / "launch" / "rf2o_ekf_input.py")],
            name="rf2o_ekf_input",
            output="screen",
        ),
        Node(
            package="robot_localization",
            executable="ekf_node",
            name="jetbot_lab03_ekf",
            output="screen",
            parameters=[str(package / "params" / "ekf_jetbot.yaml")],
        ),
    ])
