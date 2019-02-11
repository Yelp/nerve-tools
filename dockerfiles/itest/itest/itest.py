import json
import multiprocessing
import os
import signal
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
        'name': 'service_one.main',
        'paths': ['/nerve/region:sjc-dev/service_one.main', '/smartstack/global/service_one.main'],
        'host': 'serviceone_1',
        'port': 1025,
    },
    {
        'name': 'scribe.main',
        'paths': ['/nerve/region:sjc-dev/scribe.main','/smartstack/global/scribe.main'],
        'host': 'scribe_1',
        'port': 1464,
    },
]
ZK = kazoo.client.KazooClient(hosts=ZOOKEEPER_CONNECT_STRING, timeout=60)
ZK.start()


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
            time.sleep(2)

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


def _check_zk_for_services(zk, expected_services, all_services=SERVICES):
    # Give nerve a few ticks to register things
    time.sleep(120)
    with open('/work/nerve.log', 'r') as nl:
        print "NERVE LOG"
        print nl.read()

    for service in all_services:
        for path in service['paths']:
            children = zk.get_children(path)
            print path
            if children:
                print zk.get('%s/%s' % (path, children[0]))
            if service['name'] not in expected_services:
                assert len(children) == 0
            else:
                assert 1 <= len(children) <= 2

def test_sighup_handling(setup):

    try:
        with open('/nail/etc/services/scribe/port', 'w') as fd:
            fd.write(str(SERVICES[-1]['port']))
        subprocess.check_call([
            'configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100',
            '--nerve-executable-path', '/usr/bin/nerve',
            '--reload-with-sighup', '--nerve-registration-delay-s', '0'
        ])

        # Remove scribe.main
        os.remove('/nail/etc/services/scribe/port')

        # SIGHUP nerve
        subprocess.check_call([
            'configure_nerve', '-f', HEARTBEAT_PATH, '-s', '100',
            '--nerve-executable-path', '/usr/bin/nerve',
            '--reload-with-sighup', '--nerve-registration-delay-s', '0'
        ])

        expected_services = [service['name'] for service in SERVICES[:-1]]
        _check_zk_for_services(ZK, expected_services)
        # Assert that we're still running with the right nerve
        assert os.kill(setup, 0) is None

    finally:
        ZK.stop()
        with open('/nail/etc/services/scribe/port', 'w') as fd:
            fd.write(str(SERVICES[-1]['port']))
