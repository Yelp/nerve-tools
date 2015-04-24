import json
import os
import socket
import subprocess
import time

import kazoo.client
import pytest

MY_IP_ADDRESS = socket.gethostbyname(socket.gethostname())

# Must be kept consistent with entries in zookeeper_discovery directory
ZOOKEEPER_CONNECT_STRING = "zookeeper_1:2181"

# Authoritative data for tests
SERVICES = [
    {
        'name': 'location_suggest.main',
        'path': '/nerve/region:sf-devc/location_suggest.main',
        'host': 'locationsuggest_1',
        'port': 1024,
    },
    {
        'name': 'location_suggest.main',
        'path': '/nerve/region:uswest1-devb/location_suggest.main',
        'host': 'locationsuggest_1',
        'port': 1024,
    },
    {
        'name': 'geocoder.main',
        'path': '/nerve/region:sf-devc/geocoder.main',
        'host': 'geocoder_1',
        'port': 1025,
    },
    {
        'name': 'scribe.main',
        'path': '/nerve/region:sf-devc/scribe.main',
        'host': 'scribe_1',
        'port': 1464,
    },
]


@pytest.yield_fixture(scope="module")
def setup():
    # Install nerve-tools
    subprocess.check_call('dpkg -i /work/dist/nerve-tools_*.deb', shell=True)

    # Forward healthchecks to the services
    socat_procs = []
    for service in SERVICES:
        host = service['host']
        port = service['port']
        socat_procs.append(subprocess.Popen(
            ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d' % (port, host, port)).split()))

    hacheck_process = subprocess.Popen('/usr/bin/hacheck -p 6666'.split())

    try:
        subprocess.check_call(['configure_nerve'])

        # Normally configure_nerve would start up nerve using 'service nerve start'.
        # However, this silently fails because we don't have an init process in our
        # Docker container.  So instead we manually start up nerve ourselves.
        with open('/work/nerve.log', 'w') as fd:
            nerve_process = subprocess.Popen(
                'nerve --config /etc/nerve/nerve.conf.json'.split(),
                env={"PATH": "/opt/rbenv/bin:" + os.environ['PATH']},
                stdout=fd, stderr=fd)

            # Give nerve a moment to register the service in Zookeeper
            time.sleep(10)

            try:
                yield
            finally:
                nerve_process.kill()
                nerve_process.wait()
    finally:
        for proc in socat_procs:
            proc.kill()
            proc.wait()
        hacheck_process.kill()
        hacheck_process.wait()


def test_clean_nerve(setup):
    subprocess.check_call('clean_nerve')


def test_nerve_services(setup):
    expected_services = [
        # HTTP service with extra advertisements
        'location_suggest.main.norcal-devc.region:sf-devc.1024.new',
        'location_suggest.main.norcal-devb.region:uswest1-devb.1024.new',

        # TCP service
        'geocoder.main.norcal-devc.region:sf-devc.1025.new',

        # Puppet-configured services
        'scribe.main.norcal-devc.region:sf-devc.1464.new',
        'mysql_read.main.norcal-devc.region:sf-devc.1464.new',
    ]

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_services = nerve_config['services'].keys()

    assert set(expected_services) == set(actual_services)


def test_nerve_service_config(setup):
    # Check a single nerve service entry
    expected_service_entry = {
        "check_interval": 2.0,
        "checks": [
            {
                "fall": 2,
                "host": "127.0.0.1",
                "port": 6666,
                "rise": 1,
                "timeout": 1.0,
                "type": "http",
                "uri": "/http/location_suggest.main/1024/status"
            }
        ],
        "host": MY_IP_ADDRESS,
        "port": 1024,
        "zk_hosts": [ZOOKEEPER_CONNECT_STRING],
        "zk_path": "/nerve/region:sf-devc/location_suggest.main"
    }

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_service_entry = \
        nerve_config['services'].get('location_suggest.main.norcal-devc.region:sf-devc.1024.new')

    assert expected_service_entry == actual_service_entry


def test_zookeeper_entry(setup):
    zk = kazoo.client.KazooClient(hosts=ZOOKEEPER_CONNECT_STRING)
    zk.start()

    try:
        for service in SERVICES:
            children = zk.get_children(service['path'])
            assert len(children) == 1

            payload = zk.get('%s/%s' % (service['path'], children[0]))[0]
            data = json.loads(payload)
            assert data == {
                'host': MY_IP_ADDRESS,
                'port': service['port'],
                'name': 'itesthost.itestdomain'
            }
    finally:
        zk.stop()
