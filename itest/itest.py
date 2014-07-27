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

SERVICE_HOST = 'service_1'
SERVICE_PORT = 1024

MY_IP_ADDRESS = socket.gethostbyname(socket.gethostname())


@pytest.fixture(scope="module")
def setup():
    # Install nerve
    subprocess.check_call('dpkg -i /work/dist/nerve-tools_*.deb', shell=True)

    # Fill in Zookeeper host address
    with open('/nail/srv/configs/zookeeper_topology-my_habitat.yaml', 'w') as fd:
        fd.write("[['%s', %d]]" % (ZOOKEEPER_HOST, ZOOKEEPER_PORT))

    # Forward yocalhost healthchecks to the service
    subprocess.check_call(
        'ifconfig lo:0 169.254.255.254 netmask 255.255.255.255 up'.split())
    subprocess.Popen(
        ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d'
         % (SERVICE_PORT, SERVICE_HOST, SERVICE_PORT)).split())


def test(setup):
    expected = {
        "instance_id": "itesthost",
        "services": {
            "location_suggest.main.another_habitat": {
                "check_interval": 10,
                "checks": [
                    {
                        "fall": 2,
                        "host": "169.254.255.254",
                        "port": SERVICE_PORT,
                        "rise": 1,
                        "timeout": 1.0,
                        "type": "http",
                        "uri": "/status"
                    }
                ],
                "host": MY_IP_ADDRESS,
                "port": SERVICE_PORT,
                "zk_hosts": [
                    '127.0.0.1:2181'
                ],
                "zk_path": "/nerve/location_suggest.main"
            },
            "location_suggest.another_habitat": {
                "check_interval": 10,
                "checks": [
                    {
                        "fall": 2,
                        "host": "169.254.255.254",
                        "port": SERVICE_PORT,
                        "rise": 1,
                        "timeout": 1.0,
                        "type": "http",
                        "uri": "/status"
                    }
                ],
                "host": MY_IP_ADDRESS,
                "port": SERVICE_PORT,
                "zk_hosts": [
                    '127.0.0.1:2181'
                ],
                "zk_path": "/nerve/location_suggest"
            },
            "location_suggest.main.my_habitat": {
                "check_interval": 10,
                "checks": [
                    {
                        "fall": 2,
                        "host": "169.254.255.254",
                        "port": SERVICE_PORT,
                        "rise": 1,
                        "timeout": 1.0,
                        "type": "http",
                        "uri": "/status"
                    }
                ],
                "host": MY_IP_ADDRESS,
                "port": SERVICE_PORT,
                "zk_hosts": [
                    ZOOKEEPER_CONNECT_STRING
                ],
                "zk_path": "/nerve/location_suggest.main"
            },
            "location_suggest.my_habitat": {
                "check_interval": 10,
                "checks": [
                    {
                        "fall": 2,
                        "host": "169.254.255.254",
                        "port": SERVICE_PORT,
                        "rise": 1,
                        "timeout": 1.0,
                        "type": "http",
                        "uri": "/status"
                    }
                ],
                "host": MY_IP_ADDRESS,
                "port": SERVICE_PORT,
                "zk_hosts": [
                    ZOOKEEPER_CONNECT_STRING
                ],
                "zk_path": "/nerve/location_suggest"
            }
        }
    }

    subprocess.check_call(['configure_nerve'])

    # Check that configure_nerve wrote out the right config
    with open('/etc/nerve/nerve.conf.json') as fd:
        actual = json.load(fd)

    assert expected == actual

    # Normally configure_nerve would start up nerve using 'service nerve start'.
    # However, this silently fails because we don't have an init process in our
    # Docker container.  So instead we manually start up nerve ourselves.
    subprocess.Popen('nerve --config /etc/nerve/nerve.conf.json'.split(),
                     env={"PATH": "/opt/rbenv/bin:" + os.environ['PATH']})

    # Give nerve a moment to register the service in Zookeeper...
    time.sleep(1)

    # ... and then check that the service has been successfully registered in
    # Zookeeper
    zk = kazoo.client.KazooClient(hosts=ZOOKEEPER_CONNECT_STRING)
    zk.start()

    payload_0 = zk.get('/nerve/location_suggest/itesthost_0000000000')[0]
    data_0 = json.loads(payload_0)
    assert data_0['host'] == MY_IP_ADDRESS
    assert data_0['port'] == SERVICE_PORT
    assert data_0['name'] == 'itesthost'

    payload_1 = zk.get('/nerve/location_suggest.main/itesthost_0000000000')[0]
    data_1 = json.loads(payload_1)
    assert data_1['host'] == MY_IP_ADDRESS
    assert data_1['port'] == SERVICE_PORT
    assert data_1['name'] == 'itesthost'
