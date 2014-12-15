import json
import os
import socket
import subprocess
import time

import kazoo.client
import pytest


ZOOKEEPER_HOST = 'zookeeper_1'
ZOOKEEPER_PORT = 2181
ZOOKEEPER_CONNECT_STRING = "%s:%d" % (ZOOKEEPER_HOST, 2181)

LOCATION_SUGGEST_HOST = 'locationsuggest_1'
LOCATION_SUGGEST_PORT = 1024

GEOCODER_HOST = 'geocoder_1'
GEOCODER_PORT = 1025

SCRIBE_HOST = 'scribe_1'
SCRIBE_PORT = 1464

MY_IP_ADDRESS = socket.gethostbyname(socket.gethostname())


@pytest.yield_fixture(scope="module")
def setup():
    # Install nerve-tools
    subprocess.check_call('dpkg -i /work/dist/nerve-tools_*.deb', shell=True)

    # Fill in Zookeeper host address
    zk_dir = '/nail/etc/zookeeper_discovery/generic'
    with open(os.path.join(zk_dir, 'my_location.yaml'), 'w') as fd:
        fd.write("[['%s', %d]]" % (ZOOKEEPER_HOST, ZOOKEEPER_PORT))

    # Forward yocalhost healthchecks to the services
    subprocess.check_call(
        'ifconfig lo:0 169.254.255.254 netmask 255.255.255.255 up'.split())
    location_suggest_socat_process = subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (LOCATION_SUGGEST_PORT, LOCATION_SUGGEST_HOST, LOCATION_SUGGEST_PORT)).split())
    geocoder_socat_process = subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (GEOCODER_PORT, GEOCODER_HOST, GEOCODER_PORT)).split())
    scribe_socat_process = subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (SCRIBE_PORT, SCRIBE_HOST, SCRIBE_PORT)).split())

    try:
        subprocess.check_call(['configure_nerve'])

        # Normally configure_nerve would start up nerve using 'service nerve start'.
        # However, this silently fails because we don't have an init process in our
        # Docker container.  So instead we manually start up nerve ourselves.
        nerve_process = subprocess.Popen(
            'nerve --config /etc/nerve/nerve.conf.json'.split(),
            env={"PATH": "/opt/rbenv/bin:" + os.environ['PATH']})

        # Give nerve a moment to register the service in Zookeeper
        time.sleep(10)

        try:
            yield
        finally:
            nerve_process.kill()
            nerve_process.wait()
    finally:
        location_suggest_socat_process.kill()
        location_suggest_socat_process.wait()
        geocoder_socat_process.kill()
        geocoder_socat_process.wait()
        scribe_socat_process.kill()
        scribe_socat_process.wait()


def test_clean_nerve(setup):
    subprocess.check_call('clean_nerve')


def test_nerve_services(setup):
    expected_services = [
        # HTTP service with cross-location registration
        'location_suggest.main.another_location.1024',
        'location_suggest.main.my_location.1024',

        # TCP service
        'geocoder.main.my_location.1025',

        # TCP service
        'scribe.main.my_location.1464',
    ]

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_services = nerve_config['services'].keys()

    assert set(expected_services) == set(actual_services)


def test_nerve_service_config(setup):
    # Check a single nerve service entry
    expected_service_entry = {
        "check_interval": 10,
        "checks": [
            {
                "fall": 2,
                "host": "169.254.255.254",
                "port": LOCATION_SUGGEST_PORT,
                "rise": 1,
                "timeout": 1.0,
                "type": "http",
                "uri": "/status"
            }
        ],
        "host": MY_IP_ADDRESS,
        "port": LOCATION_SUGGEST_PORT,
        "zk_hosts": [ZOOKEEPER_CONNECT_STRING],
        "zk_path": "/nerve/location_suggest.main"
    }

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_service_entry = \
        nerve_config['services'].get('location_suggest.main.my_location.1024')

    assert expected_service_entry == actual_service_entry


def test_zookeeper_entry(setup):
    zk = kazoo.client.KazooClient(hosts=ZOOKEEPER_CONNECT_STRING)
    zk.start()

    try:
        for (name, port) in [
                ('location_suggest.main', LOCATION_SUGGEST_PORT),
                ('geocoder.main', GEOCODER_PORT)
                ]:

            children = zk.get_children('/nerve/%s' % name)
            assert len(children) == 1

            payload = zk.get('/nerve/%s/%s' % (name, children[0]))[0]
            data = json.loads(payload)
            assert data == {
                'host': MY_IP_ADDRESS,
                'port': port,
                'name': 'itesthost.itestdomain'
            }
    finally:
        zk.stop()
