import json
import os
import socket
import subprocess
import time

import kazoo.client
import pytest


# Must be kept consistent with entries in zookeeper_discovery directory
ZOOKEEPER_HOST = 'zookeeper_1'
ZOOKEEPER_PORT = 2181
ZOOKEEPER_CONNECT_STRING = "%s:%d" % (ZOOKEEPER_HOST, 2181)

LOCATION_SUGGEST_HOST = 'locationsuggest_1'
LOCATION_SUGGEST_PORT = 1024

GEOCODER_HOST = 'geocoder_1'
GEOCODER_PORT = 1025

TCP_HOST = 'tcp_1'
TCP_PORT = 1464

MY_IP_ADDRESS = socket.gethostbyname(socket.gethostname())


@pytest.yield_fixture(scope="module")
def setup():
    # Install nerve-tools
    subprocess.check_call('dpkg -i /work/dist/nerve-tools_*.deb', shell=True)

    # Forward localhost healthchecks to the services
    location_suggest_socat_process = subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (LOCATION_SUGGEST_PORT, LOCATION_SUGGEST_HOST, LOCATION_SUGGEST_PORT)).split())
    geocoder_socat_process = subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (GEOCODER_PORT, GEOCODER_HOST, GEOCODER_PORT)).split())
    tcp_socat_process = subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (TCP_PORT, TCP_HOST, TCP_PORT)).split())

    hacheck_process = subprocess.Popen('/usr/bin/hacheck -p 6666'.split())

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
        tcp_socat_process.kill()
        tcp_socat_process.wait()
        hacheck_process.kill()
        hacheck_process.wait()


def test_clean_nerve(setup):
    subprocess.check_call('clean_nerve')


def test_nerve_services(setup):
    expected_services = [
        # HTTP service with cross-location registration
        'location_suggest.main.another_location.1024',
        'location_suggest.main.my_location.1024',
        'location_suggest.main.sf-devc.1024.new',
        'location_suggest.main.uswest1-devb.1024.new',

        # TCP service
        'geocoder.main.my_location.1025',
        'geocoder.main.sf-devc.1025.new',

        # TCP service
        'scribe.main.my_location.1464',
        'scribe.main.sf-devc.1464.new',

        'mysql_read.main.my_location.1464',
        'mysql_read.main.sf-devc.1464.new',
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
                "uri": "/http/location_suggest.main/%d/status" % LOCATION_SUGGEST_PORT
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
