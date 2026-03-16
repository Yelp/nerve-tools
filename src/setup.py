#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from setuptools import find_packages
from setuptools import setup


HERE = Path(__file__).parent


def get_install_requires():
    return [
        line.strip()
        for line in (HERE / 'requirements.txt').read_text().splitlines()
        if line.strip() and not line.startswith('#')
    ]


setup(
    name='nerve-tools',
    version='2.2.3',
    provides=['nerve_tools'],
    author='Yelp',
    author_email='compute-infra@yelp.com',
    description='Nerve-related tools for use on Yelp machines',
    packages=find_packages(exclude=['tests']),
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
