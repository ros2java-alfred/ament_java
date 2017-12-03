from setuptools import find_packages
from setuptools import setup

setup(
    name='ament_build_type_gradle',
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    install_requires=['ament-package', 'osrf_pycommon'],
    author='Esteve Fernandez',
    author_email='esteve@apache.org',
    maintainer='Esteve Fernandez',
    maintainer_email='esteve@apache.org',
    keywords=['ROS'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ],
    description='Gradle tool support for ament.',
    license='Apache License, Version 2.0',
    tests_require=['pytest'],
    entry_points={
        'ament.build_types': [
            'ament_gradle = ament_build_type_gradle:AmentGradleBuildType',
        ],
    }
)
