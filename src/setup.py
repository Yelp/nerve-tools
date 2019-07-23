#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pkg_resources import yield_lines
from setuptools import setup, find_packages


def get_install_requires():
    with open('requirements.txt', 'r') as f:
        minimal_reqs = list(yield_lines(f.read()))

    return minimal_reqs


setup(
    name='nerve-tools',
    version='0.16.1',
    provides=['nerve_tools'],
    author='John Billings',
    author_email='billings@yelp.com',
    description='Nerve-related tools for use on Yelp machines',
    packages=find_packages(exclude=['tests']),
    setup_requires=['setuptools'],
    include_package_data=True,
    install_requires=get_install_requires(),
    entry_points={
        'console_scripts': [
            'clean_nerve=nerve_tools.clean_nerve:main',
            'configure_nerve=nerve_tools.configure_nerve:main',
            'updown_service=nerve_tools.updown_service:main',
        ],
    },
)
