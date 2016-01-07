#!/bin/bash
set -e

echo "Installing nerve-tools package"
dpkg -i /work/dist/nerve-tools_*.deb

echo "Testing that pyyaml uses optimized cyaml parsers if present"
/usr/share/python/nerve-tools/bin/python -c 'import yaml; assert yaml.__with_libyaml__'

echo "Full integration test"
py.test /itest.py
