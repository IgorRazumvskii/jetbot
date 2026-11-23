import os
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription
from launch.actions import ExecuteProcess

def generate_launch_description():
    urdf = os.path.join(
        get_package_share_directory('jetbot_ros_gazebo'),
        'models/jetbot/model_high_resolution.sdf')
    with open(urdf, 'r') as infp:
        robot_desc = infp.read()
    # Create the bridge arguments in the same format as your ros2 run command
    bridge_args = [
        '/model/jetbot/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist',
        '/model/jetbot/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry',
        '/model/jetbot/pose@geometry_msgs/msg/Pose@gz.msgs.Pose',
        '/world/world_demo/model/jetbot/link/camera_link/sensor/color/camera_info@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo',
        '/world/world_demo/model/jetbot/link/camera_link/sensor/color/image@sensor_msgs/msg/Image@gz.msgs.Image',
        '/world/world_demo/model/jetbot/link/lidar_link/sensor/scan_front/scan@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan',
        '/world/world_demo/model/jetbot/link/lidar_link/sensor/scan_front/scan/points@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked',
        '/clock@rosgraph_msgs/msg/Clock@gz.msgs.Clock',
        '/joint_state@sensor_msgs/msg/JointState@gz.msgs.Model'
    ]
    
    return LaunchDescription([
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='jetbot_bridge',
            output='screen',
            arguments=bridge_args
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'use_sim_time': True, 'robot_description': robot_desc}],
            arguments=[urdf]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='tf_base_footprint_to_base_link',
            arguments=["0", "0", "0", "0.7071", "0", "0", "-0.7071", "base_footprint", "base_link"]
        ),
        Node(
            package='jetbot_ros_gazebo',
            executable='publish_tf_from_odom',
            name='tf_from_odom',
            output='screen'
        )
    ])