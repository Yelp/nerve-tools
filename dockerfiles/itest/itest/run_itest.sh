#!/bin/bash
set -vx
set -e

echo "installing paasta-tools (dependency of nerve-tools.)"
. /etc/lsb-release
PAASTA_VERSION=0.145.0
PAASTA_DEB_NAME=paasta-tools_${PAASTA_VERSION}.${DISTRIB_CODENAME}1_amd64.deb
wget "https://github.com/Yelp/paasta/releases/download/v${PAASTA_VERSION}/${PAASTA_DEB_NAME}"

# We use || true here because any missing dependencies will cause dpkg -i to return an error.
# We fix the missing dependencies later.
dpkg -i "./${PAASTA_DEB_NAME}" || true

echo "Installing nerve-tools package"
dpkg -i /work/dist/nerve-tools_*.deb || true

echo "Fixing missing dependencies"
apt-get -y install -f

echo "Testing that pyyaml uses optimized cyaml parsers if present"
/opt/venvs/nerve-tools/bin/python -c 'import yaml; assert yaml.__with_libyaml__'

echo "Full integration test"
py.test-3 -vvv /itest.py
