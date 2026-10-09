from glob import glob

from setuptools import find_packages, setup

package_name = 'aruco_approach'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Danil Grigoriev',
    maintainer_email='danilgrigoriev26@gmail.com',
    description='Движение JetBot к ArUco-маркеру',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'aruco_approach = aruco_approach.approach_node:main',
            'twist_nonzero_filter = aruco_approach.twist_nonzero_filter:main',
            'make_marker = aruco_approach.make_marker:main',
            'estimate_focal = aruco_approach.estimate_focal:main',
        ],
    },
)
