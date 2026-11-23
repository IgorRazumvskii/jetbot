from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, EmitEvent, ExecuteProcess, IncludeLaunchDescription,
    RegisterEventHandler, TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare("scout_bag_slam")
    clock = {"use_sim_time": True}
    playback = ExecuteProcess(cmd=[
        "ros2", "bag", "play", LaunchConfiguration("bag"),
        "--clock", "30", "--rate", LaunchConfiguration("rate"),
        "--delay", "2", "--disable-keyboard-controls",
        "--topics", "/odom", "/rslidar_points", "/camera/color/image_raw/compressed",
    ], output="screen")
    return LaunchDescription([
        DeclareLaunchArgument("bag", description="Path to a Scout rosbag directory"),
        DeclareLaunchArgument("rate", default_value="1.0"),
        DeclareLaunchArgument("exit_on_finish", default_value="false"),
        DeclareLaunchArgument("scan_config", default_value=PathJoinSubstitution([
            share, "config", "scan.yaml",
        ])),
        DeclareLaunchArgument("slam_config", default_value=PathJoinSubstitution([
            share, "config", "slam.yaml",
        ])),
        Node(
            package="scout_bag_slam", executable="replay_bridge", parameters=[clock],
        ),
        Node(
            package="tf2_ros", executable="static_transform_publisher",
            arguments=["--z", "0.507", "--frame-id", "base_footprint", "--child-frame-id", "rslidar"],
        ),
        Node(
            package="pointcloud_to_laserscan", executable="pointcloud_to_laserscan_node",
            name="cloud_slice", parameters=[LaunchConfiguration("scan_config"), clock],
            remappings=[("cloud_in", "/rslidar_points"), ("scan", "/scan")],
        ),
        RegisterEventHandler(OnStateTransition(
            goal_state="active", entities=[playback], handle_once=True,
        )),
        RegisterEventHandler(
            OnProcessExit(target_action=playback, on_exit=[
                TimerAction(period=1.25, actions=[EmitEvent(event=Shutdown())]),
            ]),
            condition=IfCondition(LaunchConfiguration("exit_on_finish")),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare("slam_toolbox"), "launch", "online_async_launch.py",
            ])),
            launch_arguments={
                "slam_params_file": LaunchConfiguration("slam_config"), "use_sim_time": "true",
            }.items(),
        ),
    ])
