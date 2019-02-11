#!/bin/bash
echo "Installing nerve-tools package"
dpkg -i /work/dist/nerve-tools_*.deb

# Set -e here because the previous install should fail lacking dependencies
# and then we can fix it here
set -e
apt-get -y install -f

echo "Testing that pyyaml uses optimized cyaml parsers if present"
/opt/venvs/nerve-tools/bin/python -c 'import yaml; assert yaml.__with_libyaml__'

git clone https://github.com/mattmb/nerve.git /nerve
cd /nerve
bundle install
bundle binstubs nerve --path /usr/bin

cd /work
echo "Full integration test"
py.test -s /itest.py
