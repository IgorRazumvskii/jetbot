from glob import glob

from setuptools import setup

name = "scout_bag_slam"

setup(
    name=name,
    version="0.1.0",
    packages=[name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + name]),
        ("share/" + name, ["package.xml"]),
        ("share/" + name + "/launch", glob("launch/*.launch.py")),
        ("share/" + name + "/config", glob("config/*.yaml")),
    ],
    entry_points={"console_scripts": ["replay_bridge = scout_bag_slam.bridge:main"]},
)
