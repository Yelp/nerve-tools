#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='nerve-tools',
    version='0.5.2',
    provides=['nerve_tools'],
    author='John Billings',
    author_email='billings@yelp.com',
    description='Nerve-related tools for use on Yelp machines',
    packages=find_packages(exclude=['tests']),
    setup_requires=['setuptools'],
    include_package_data=True,
    install_requires=[
        'argparse==1.2.1',
        'kazoo==1.3.1',
        'PyYAML==3.10',
        'service-deployment-tools==0.4.3',
    ],
    entry_points={
        'console_scripts': [
            'configure_nerve=nerve_tools.configure_nerve:main',
            'updown_service=nerve_tools.updown_service:main',
        ],
    },
)
