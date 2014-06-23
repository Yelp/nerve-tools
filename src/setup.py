#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='nerve-tools',
    version='0.1.0',
    provides=['nerve_tools'],
    author='John Billings',
    author_email='billings@yelp.com',
    description='Nerve-related tools for use on Yelp machines',
    packages=find_packages(exclude=['tests']),
    setup_requires=['setuptools'],
    include_package_data=True,
    install_requires=[
        'kazoo==1.3.1',
        'PyYAML==3.10',
        'service-configuration-lib==0.2.1',
    ],
    entry_points={
        'console_scripts': [
            'configure_nerve=nerve_tools.configure_nerve:main',
        ],
    },
)
