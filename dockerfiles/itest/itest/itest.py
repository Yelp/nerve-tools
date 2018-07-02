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


@pytest.yield_fixture(scope='module')
def setup():
    # Forward healthchecks to the services
    socat_procs = []
    for service in SERVICES:
        host = service['host']
        port = service['port']
        socat_procs.append(subprocess.Popen(
            ('socat TCP4-LISTEN:%d,fork TCP4:%s:%d' % (port, host, port)).split()))

    hacheck_process = subprocess.Popen('/usr/bin/hacheck -p 6666'.split())

    try:
        subprocess.check_call(
            ['configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100', '--nerve-registration-delay-s', '0']
        )

        # Normally configure_nerve would start up nerve using 'service nerve start'.
        # However, this silently fails because we don't have an init process in our
        # Docker container.  So instead we manually start up nerve ourselves.
        with open('/work/nerve.log', 'w') as fd:
            nerve_process = subprocess.Popen(
                'nerve --config /etc/nerve/nerve.conf.json'.split(),
                env={"PATH": "/opt/rbenv/bin:" + os.environ['PATH']},
                stdout=fd, stderr=fd)

            with open('/var/run/nerve.pid', 'w') as pid_fd:
                pid_fd.write(str(nerve_process.pid))

            # Give nerve a moment to register the service in Zookeeper
            time.sleep(10)

            try:
                yield nerve_process.pid
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

        'scribe.main.westcoast-dev.region:sjc-dev.1464.new',
        'mysql_read.main.westcoast-dev.region:sjc-dev.1464.new',

        # V2 configs
        'service_three.main.westcoast-dev:1024.v2.new',
        'service_three.main.westcoast-prod:1024.v2.new',
        'service_one.main.westcoast-dev:1025.v2.new',
        'scribe.main.westcoast-dev:1464.v2.new',
        'mysql_read.main.westcoast-dev:1464.v2.new',
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
                    "Host": "www.test.com",
                },
                "expect": "OK",
            },
        ],
        "host": MY_IP_ADDRESS,
        "port": 1024,
        "weight": CPUS,
        "zk_hosts": [ZOOKEEPER_CONNECT_STRING],
        "zk_path": "/nerve/region:sjc-dev/service_three.main",
    }

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_service_entry = \
        nerve_config['services'].get('service_three.main.westcoast-dev.region:sjc-dev.1024.new')

    assert expected_service_entry == actual_service_entry


def test_v2_nerve_service_config(setup):
    # Check a single v2 nerve service entry
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
                    "Host": "www.test.com",
                },
                "expect": "OK",
            },
        ],
        "host": MY_IP_ADDRESS,
        "port": 1024,
        "weight": CPUS,
        "zk_hosts": [ZOOKEEPER_CONNECT_STRING],
        "zk_path": "/smartstack/global/service_three.main",
        'labels': {
            'region:sjc-dev': '',
        },
    }

    with open('/etc/nerve/nerve.conf.json') as fd:
        nerve_config = json.load(fd)
    actual_service_entry = \
            nerve_config['services'].get('service_three.main.westcoast-dev:1024.v2.new')

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
    subprocess.check_call(
        ['configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100', '--nerve-registration-delay-s', '0']
    )
    proc = subprocess.Popen(['ps aux | grep "[b]in/nerve" | wc -l'], stdout=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    assert int(out) == 1


def _check_zk_for_services(zk, expected_services, all_services=SERVICES):
    # Give nerve a few ticks to register things
    time.sleep(5)

    for service in all_services:
        children = zk.get_children(service['path'])
        if service['name'] not in expected_services:
            assert len(children) == 0
        else:
            assert 1 <= len(children) <= 2

            payload = zk.get('%s/%s' % (service['path'], children[0]))[0]
            data = json.loads(payload)
            del data['weight']
            assert data == {
                'host': MY_IP_ADDRESS,
                'port': service['port'],
                'name': 'itesthost.itestdomain',
            }


def test_sighup_handling(setup):
    zk = kazoo.client.KazooClient(hosts=ZOOKEEPER_CONNECT_STRING, timeout=60)
    zk.start()

    try:
        expected_services = [service['name'] for service in SERVICES]
        _check_zk_for_services(zk, expected_services)

        # Remove scribe from SmartStack
        os.remove('/nail/etc/services/scribe/port')

        # SIGHUP nerve
        subprocess.check_call([
            'configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100',
            '--nerve-executable-path', '/usr/bin/nerve',
            '--reload-with-sighup', '--nerve-registration-delay-s', '0'
        ])

        expected_services = [service['name'] for service in SERVICES[:-1]]
        _check_zk_for_services(zk, expected_services)

        # Add scribe back to SmartStack
        with open('/nail/etc/services/scribe/port', 'w') as fd:
            fd.write(str(SERVICES[-1]['port']))

        # SIGHUP nerve
        subprocess.check_call([
            'configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100',
            '--nerve-executable-path', '/usr/bin/nerve',
            '--reload-with-sighup', '--nerve-registration-delay-s', '0'
        ])
        expected_services = [service['name'] for service in SERVICES]
        _check_zk_for_services(zk, expected_services)

        # Change scribe's port to another different but valid port
        service_copy = json.loads(json.dumps(SERVICES))
        service_copy[-1]['port'] = 1025

        with open('/nail/etc/services/scribe/port', 'w') as fd:
            fd.write(str(service_copy[-1]['port']))

        # SIGHUP nerve
        subprocess.check_call([
            'configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100',
            '--nerve-executable-path', '/usr/bin/nerve',
            '--reload-with-sighup', '--nerve-registration-delay-s', '0'
        ])
        expected_services = [service['name'] for service in service_copy]
        _check_zk_for_services(zk, expected_services, service_copy)

        # Assert that we're still running with the right nerve
        assert os.kill(setup, 0) is None

    finally:
        zk.stop()
        with open('/nail/etc/services/scribe/port', 'w') as fd:
            fd.write(str(SERVICES[-1]['port']))
