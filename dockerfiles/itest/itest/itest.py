import json
import multiprocessing
import os
import socket
import subprocess
import time

import kazoo.client
import pytest

HEARTBEAT_PATH = "/var/run/nerve_tools_itest_heartbeat_path"
MY_IP_ADDRESS = socket.gethostbyname(socket.gethostname())
try:
    CPUS = max(multiprocessing.cpu_count(), 10)
except NotImplementedError:
    CPUS = 10

# Must be kept consistent with entries in zookeeper_discovery directory
ZOOKEEPER_CONNECT_STRING = "zookeeper_1:2181"

# Authoritative data for tests
SERVICES = [
    {
        'name': 'service_three.main',
        'path': '/nerve/region:sjc-dev/service_three.main',
        'host': 'servicethree_1',
        'port': 1024,
    },
    {
        'name': 'service_three.main',
        'path': '/nerve/region:uswest1-prod/service_three.main',
        'host': 'servicethree_1',
        'port': 1024,
    },
    {
        'name': 'service_one.main',
        'path': '/nerve/region:sjc-dev/service_one.main',
        'host': 'serviceone_1',
        'port': 1025,
    },
    {
        'name': 'scribe.main',
        'path': '/nerve/region:sjc-dev/scribe.main',
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
        subprocess.check_call(['configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100'])

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
        'service_three.main.westcoast-dev.region:sjc-dev.1024.new',
        'service_three.main.westcoast-prod.region:uswest1-prod.1024.new',

        # TCP service
        'service_one.main.westcoast-dev.region:sjc-dev.1025.new',

        # Puppet-configured services
        'scribe.main.westcoast-dev.region:sjc-dev.1464.new',
        'mysql_read.main.westcoast-dev.region:sjc-dev.1464.new',
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
                "open_timeout": 1.0,
                "type": "http",
                "uri": "/http/service_three.main/1024/status",
                "headers": {
                    "Host": "www.test.com"
                },
            }
        ],
        "host": MY_IP_ADDRESS,
        "port": 1024,
        "weight": CPUS,
        "zk_hosts": [ZOOKEEPER_CONNECT_STRING],
        "zk_path": "/nerve/region:sjc-dev/service_three.main"
    }

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_service_entry = \
        nerve_config['services'].get('service_three.main.westcoast-dev.region:sjc-dev.1024.new')

    assert expected_service_entry == actual_service_entry


def test_updown_up_when_hadown_all(setup):
    subprocess.check_call('/usr/bin/hadown all'.split())
    subprocess.check_call('updown_service service_three.main up'.split())
    subprocess.check_call('/usr/bin/haup all'.split())


def test_nerve_restarted_if_stale_heartbeat(setup):
    assert os.path.isfile(HEARTBEAT_PATH)
    # Modify heartbeat file timestamp to be in the past
    os.utime(HEARTBEAT_PATH, (0, 0))

    # Run configure_nerve and check if nerve was restarted
    subprocess.check_call(['configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100'])
    proc = subprocess.Popen(['ps aux | grep "[b]in/nerve" | wc -l'], stdout=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    assert int(out) == 1


def test_zookeeper_entry(setup):
    zk = kazoo.client.KazooClient(hosts=ZOOKEEPER_CONNECT_STRING, timeout=60)
    zk.start()

    try:
        for service in SERVICES:
            children = zk.get_children(service['path'])
            assert len(children) == 1

            payload = zk.get('%s/%s' % (service['path'], children[0]))[0]
            data = json.loads(payload)
            del data['weight']
            assert data == {
                'host': MY_IP_ADDRESS,
                'port': service['port'],
                'name': 'itesthost.itestdomain'
            }
    finally:
        zk.stop()
