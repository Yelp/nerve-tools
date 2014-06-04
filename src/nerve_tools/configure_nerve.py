#!/usr/bin/env python

"""Update the nerve configuration file and restart nerve if anything has
changed."""

import contextlib
import filecmp
import json
import os
import os.path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections import namedtuple

import kazoo.client
import yaml

sys.path.append('/nail/sys/srv-deploy/lib/')
from service_configuration_lib import read_services_configuration


HABITAT_PATH = '/nail/etc/habitat'

NERVE_CONFIG_PATH = '/etc/nerve/nerve.conf.json'
NERVE_RESTART_COMMAND = ['service', 'nerve', 'restart']
NERVE_RESTART_DELAY_S = 1

ZK_TOPOLOGY_PATTERN = '/nail/srv/configs/zookeeper_topology-%s.yaml'
ZK_LOCK_CONNECT_TIMEOUT_S = 10.0
ZK_LOCK_TIMEOUT_S = 60.0
ZK_LOCK_PATH = "/configure_nerve"

STATE_DIR = '/var/spool/healthcheck_state'


def get_habitat():
    with open(HABITAT_PATH) as fp:
        return fp.readline().strip()


def get_hostname():
    return socket.gethostname()


def get_fqdn():
    return socket.getfqdn()


def get_ip_address():
    return socket.gethostbyname(get_hostname())


def get_zookeeper_topology(habitat):
    zk_topology_path = ZK_TOPOLOGY_PATTERN % habitat
    with open(zk_topology_path) as fp:
        zk_topology = yaml.load(fp)
    return ['%s:%d' % (entry[0], entry[1]) for entry in zk_topology]


def service_runs_here(service_name, service_info, fqdn):
    return any([
        # Services in our own datacenters
        fqdn in service_info.get('runs_on', []),
        # AWS services
        os.path.exists('/nail/srv/%s' % service_name),
    ])


def service_is_enabled(service_name):
    """If either of the following local healthcheck state files contains 'down'
    then the service should not be enabled:

      * 'STATE_DIR/<service_name>'
      * 'STATE_DIR/all'

    This provides a facility to gracefully drain traffic from the service before
    shutting it down.

    NOTES:
      * These are the same files that are read by our legacy healthcheck system.
      * Unlike our legacy healthcheck system, we default to assuming that a
        service should be enabled unless it is explicitly disabled.  This allows
        AWS services to be completely agnostic of this facility.

    Returns: true iff the service should be enabled
    """

    def is_enabled(name):
        statefile = os.path.join(STATE_DIR, name)
        try:
            with open(statefile) as fh:
                state = fh.readline().strip()
            if state == 'down':
                return False
            return True
        except:
            # If the file doesn't exist, then assume enabled
            return True

    return all([is_enabled(name) for name in [service_name, 'all']])


def invert_dictionary(d):
    """Invert a dictionary of type key -> [value].

    For example, given the dictionary {1: ['x', 'y'], 2: ['x']}
    return {'x': [1, 2], 'y': [1]}.
    """

    inv_d = {}
    for k, vs in d.iteritems():
        for v in vs:
            inv_d.setdefault(v, []).append(k)
    return inv_d


def get_habitats_to_register_in(habitat, routes):
    """A route dictionary configures cross-habitat communcation between client
    and services.  For example, consider the following route dictionary:

      [{'source': 'sfo1',
        'destinations': ['uswest1aprod', 'uswest1bprod']},
       {'source': 'sfo2',
        'destinations': ['uswest1aprod', 'uswest1bprod']},
       {'source': 'iad1',
        'destinations': ['useast1aprod', 'useast1bprod', 'useast1cprod']}
      ]

    This says that a client in the 'sfo1' habitat should transparently talk to
    service instances in both the 'uswest1aprod' and 'uswest1bprod' habitats,
    in addition to any service instances in 'sfo1'.

    OK, but how does this work?  Well, a client can only reach a service instance if
    that instance is registered in the client's habitat.  So we just need to invert
    the relation to find out where we should be registering.

    For example, if we are a service instance in the 'uswest1aprod' habitat, then
    we need to register in both the 'sfo1' and 'sfo2' habitats, in addition to the
    'uswest1aprod' habitat.

    Returns: a set of habitat names
    """

    routes_dict = {}
    for route in routes:
        routes_dict.setdefault(route['source'], []).extend(route['destinations'])

    habitats_to_register_in = set([habitat])
    habitats_to_register_in.update(invert_dictionary(routes_dict).get(habitat, []))
    return habitats_to_register_in


# All information needed to create a nerve configuration item
NerveItem = namedtuple('NerveItem',
                       ['service_name', 'port', 'habitat_to_register_in',
                        'healthcheck_uri', 'ip_address', 'zookeeper_topology'])


def convert_service_info_to_nerve_items(service_name, service_info, fqdn):
    """Convert a (key, value) pair from a call to read_services_configuration()
    into a list of one or more NerveItems."""

    if not service_runs_here(service_name, service_info, fqdn):
        return []

    if not service_is_enabled(service_name):
        return []

    port = service_info.get('port')
    if port is None:
        return []
    port = int(port)

    smartstack_info = service_info.get('smartstack')
    if smartstack_info is None:
        return []

    healthcheck_uri = smartstack_info.get('healthcheck_uri', '/status')

    routes = smartstack_info.get('routes', [])
    my_habitat = get_habitat()
    habitats_to_register_in = get_habitats_to_register_in(my_habitat, routes)

    # Create a separate nerve configuration item for each habitat that we need
    # to register in.
    nerve_items = []
    for habitat in habitats_to_register_in:
        try:
            zookeeper_topology = get_zookeeper_topology(habitat)
        except:
            continue

        ip_address = get_ip_address()
        nerve_item = NerveItem(service_name, port, habitat, healthcheck_uri,
                               ip_address, zookeeper_topology)
        nerve_items.append(nerve_item)

    return nerve_items


def generate_configuration(nerve_items):
    """Create a nerve configuration dictionary from a set of nerve items."""

    nerve_config = {
        'instance_id': get_hostname(),
        'services': {},
    }

    for nerve_item in nerve_items:
        key = '%s_%s' % (nerve_item.service_name, nerve_item.habitat_to_register_in)
        nerve_config['services'][key] = {
            'port': nerve_item.port,
            'host': nerve_item.ip_address,
            'zk_hosts': nerve_item.zookeeper_topology,
            'zk_path': '/nerve/%s' % nerve_item.service_name,
            # Perform a healthcheck every ten seconds
            'check_interval': 10,
            # Hit the service on its healthcheck URI
            'checks': [{
                'type': 'http',
                'host': 'localhost',
                'port': nerve_item.port,
                'uri': nerve_item.healthcheck_uri,
                'timeout': 1.0,
                'rise': 1,
                'fall': 2,
            }]
        }

    return nerve_config


@contextlib.contextmanager
def zookeeper_lock():
    """Context manager to get a lock for current habitat."""

    my_habitat = get_habitat()
    zk_topology = get_zookeeper_topology(my_habitat)
    zk_hosts = ','.join(zk_topology)
    zk = kazoo.client.KazooClient(hosts=zk_hosts, timeout=ZK_LOCK_CONNECT_TIMEOUT_S)
    zk.start()

    lock = zk.Lock(ZK_LOCK_PATH)
    try:
        lock.acquire(timeout=ZK_LOCK_TIMEOUT_S)
        yield
    finally:
        lock.release()
        zk.stop()


def main():
    fqdn = get_fqdn()
    with tempfile.NamedTemporaryFile() as tmp_file:
        nerve_items = []
        for service_name, service_info in read_services_configuration().iteritems():
            new_nerve_items = convert_service_info_to_nerve_items(
                service_name, service_info, fqdn)
            nerve_items.extend(new_nerve_items)
        new_config = generate_configuration(nerve_items)

        new_config_path = tmp_file.name
        with open(new_config_path, 'w') as fp:
            json.dump(new_config, fp, sort_keys=True, indent=4, separators=(',', ': '))

        # Match the permissions that puppet expects
        os.chmod(new_config_path, 0644)

        should_restart = not filecmp.cmp(new_config_path, NERVE_CONFIG_PATH)

        if should_restart:

            # Globally serialize nerve restarts using a Zookeeper lock.  This
            # is to prevent all nerve instances from simultaneously restarting,
            # which would cause all registered service instances to disappear.
            with zookeeper_lock():

                # Only copy the config file into place once we've acquired the
                # lock.  This is so that if we fail at the lock acquisition step
                # then we will still correctly detect that nerve should be
                # restarted the next time that this script runs.
                shutil.copy(new_config_path, NERVE_CONFIG_PATH)

                # Now restart nerve.  We add '/sbin' to the path to ensure that
                # 'service nerve restart' can find '/sbin/restart'.
                env = os.environ.copy()
                env['PATH'] += os.pathsep + '/sbin'
                subprocess.check_call(NERVE_RESTART_COMMAND, env=env)

                # Give this nerve instance time to register its services before
                # yielding the lock for the restart of the next nerve instance.
                time.sleep(NERVE_RESTART_DELAY_S)
        else:
            # Always swap new config file into place, even if we're not going to
            # restart nerve.  Our monitoring system checks the NERVE_CONFIG_PATH
            # file age to ensure that this script is functioning correctly.
            shutil.copy(new_config_path, NERVE_CONFIG_PATH)


if __name__ == '__main__':
    main()
