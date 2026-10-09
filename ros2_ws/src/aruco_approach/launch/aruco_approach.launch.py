"""ДЗ 1: движение к ArUco-маркеру + twist_mux (+ teleop по желанию).

    ros2 launch aruco_approach aruco_approach.launch.py               # реальный робот
    ros2 launch aruco_approach aruco_approach.launch.py mode:=sim     # Gazebo
    ... teleop:=true          открыть teleop_twist_keyboard в отдельном окне xterm
    ... view:=true            открыть отладочное изображение (rqt_image_view)
    ... stop_distance:=0.4 max_linear_speed:=0.1 max_angular_speed:=0.8 marker_size:=0.15

Цепочка команд:
  teleop_twist_keyboard -> /cmd_vel_teleop -> twist_nonzero_filter -> /cmd_vel_teleop_active -+
                                                                                              +-> twist_mux -> /cmd_vel
  aruco_approach -------------------------------------------------------> /cmd_vel_nav -------+
Если teleop запускается вручную в другом терминале:
  ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/cmd_vel_teleop
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

REQUIRED_PARAMS = ('stop_distance', 'max_linear_speed', 'max_angular_speed', 'marker_size')


def launch_setup(context):
    pkg = get_package_share_directory('aruco_approach')
    arg = lambda name: LaunchConfiguration(name).perform(context)  # noqa: E731

    mode = arg('mode')
    if mode not in ('real', 'sim'):
        raise RuntimeError(f"mode должен быть 'real' или 'sim', получено '{mode}'")
    use_sim_time = mode == 'sim'
    params_file = arg('params_file') or os.path.join(pkg, 'config', f'approach_{mode}.yaml')

    overrides = {'use_sim_time': use_sim_time}
    for name in REQUIRED_PARAMS:
        if arg(name):
            overrides[name] = float(arg(name))

    actions = [
        Node(
            package='aruco_approach',
            executable='aruco_approach',
            name='aruco_approach',
            parameters=[params_file, overrides],
            output='screen',
        ),
        Node(
            package='aruco_approach',
            executable='twist_nonzero_filter',
            name='teleop_nonzero_filter',
            parameters=[{'use_sim_time': use_sim_time}],
            remappings=[('cmd_vel_in', '/cmd_vel_teleop'),
                        ('cmd_vel_out', '/cmd_vel_teleop_active')],
        ),
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            parameters=[os.path.join(pkg, 'config', 'twist_mux.yaml'),
                        {'use_sim_time': use_sim_time}],
            remappings=[('/cmd_vel_out', arg('cmd_vel_out'))],
            output='screen',
        ),
    ]

    if arg('teleop') == 'true':
        actions.append(Node(
            package='teleop_twist_keyboard',
            executable='teleop_twist_keyboard',
            name='teleop',
            prefix='xterm -fa Monospace -fs 12 -geometry 70x24 -title teleop -e',
            parameters=[params_file],
            remappings=[('cmd_vel', '/cmd_vel_teleop')],
        ))
    if arg('view') == 'true':
        actions.append(Node(
            package='rqt_image_view',
            executable='rqt_image_view',
            name='debug_view',
            arguments=['/aruco_approach/debug_image'],
        ))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='real', description='real | sim'),
        DeclareLaunchArgument('params_file', default_value='',
                              description='yaml с параметрами (по умолчанию config/approach_<mode>.yaml)'),
        DeclareLaunchArgument('cmd_vel_out', default_value='/cmd_vel',
                              description='выход twist_mux — топик, который слушает робот'),
        DeclareLaunchArgument('teleop', default_value='false'),
        DeclareLaunchArgument('view', default_value='false'),
        *[DeclareLaunchArgument(name, default_value='', description='переопределить параметр узла')
          for name in REQUIRED_PARAMS],
        OpaqueFunction(function=launch_setup),
    ])
