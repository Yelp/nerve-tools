#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='nerve-tools',
    version='0.15.2',
    provides=['nerve_tools'],
    author='John Billings',
    author_email='billings@yelp.com',
    description='Nerve-related tools for use on Yelp machines',
    packages=find_packages(exclude=['tests']),
    setup_requires=['setuptools'],
    include_package_data=True,
    install_requires=[
        'argparse>=1.2.1',
        'environment_tools>=1.1.0,<1.2.0',
        'kazoo>=2.2.0',
        'PyYAML>=3.11',
        'paasta-tools==0.75.0',
        'protobuf==2.6.1',
        'requests>=2.6.2',
        'service-configuration-lib==0.12.0',
        'setuptools<34',
    ],
    entry_points={
        'console_scripts': [
            'clean_nerve=nerve_tools.clean_nerve:main',
            'configure_nerve=nerve_tools.configure_nerve:main',
            'updown_service=nerve_tools.updown_service:main',
        ],
    },
)
