from setuptools import find_packages, setup

package_name = 'etd_ros2_bridge'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', [f'resource/{package_name}']),
        (f'share/{package_name}', ['package.xml']),
        (f'share/{package_name}/action', ['action/ExecuteSkill.action']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ETD Lab',
    maintainer_email='etd@example.com',
    description='ETD Skill Runtime ROS 2 bridge — action server and client',
    license='MIT',
    entry_points={
        'console_scripts': [
            'skill_action_server = etd_ros2_bridge.skill_action_server:main',
            'skill_action_client = etd_ros2_bridge.skill_action_client:main',
        ],
    },
)
