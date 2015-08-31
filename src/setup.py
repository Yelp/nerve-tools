#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='nerve-tools',
    version='0.8.26',
    provides=['nerve_tools'],
    author='John Billings',
    author_email='billings@yelp.com',
    description='Nerve-related tools for use on Yelp machines',
    packages=find_packages(exclude=['tests']),
    setup_requires=['setuptools'],
    include_package_data=True,
    install_requires=[
        'argparse>=1.2.1',
        'environment_tools>=1.0.5,<1.1.0',
        'kazoo>=2.0.0',
        'PyYAML>=3.11',
        'paasta-tools==0.12.62',
        'requests>=2.7.0',
        'service-configuration-lib==0.9.2',
    ],
    entry_points={
        'console_scripts': [
            'clean_nerve=nerve_tools.clean_nerve:main',
            'configure_nerve=nerve_tools.configure_nerve:main',
            'updown_service=nerve_tools.updown_service:main',
        ],
    },
)
