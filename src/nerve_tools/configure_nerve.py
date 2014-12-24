#!/usr/bin/env python

"""Update the nerve configuration file and restart nerve if anything has
changed."""

from __future__ import absolute_import, division, print_function

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

import kazoo.client
import yaml

from paasta_tools.marathon_tools import get_services_running_here_for_nerve


NERVE_CONFIG_PATH = '/etc/nerve/nerve.conf.json'
NERVE_RESTART_COMMAND = ['service', 'nerve', 'restart']
NERVE_RESTART_DELAY_S = 1

# CEP 355 Zookeepers
ZK_DEFAULT_CLUSTER_TYPE = 'generic'
ZK_DEFAULT_CLUSTER_LOCATION = 'local'
ZK_TOPOLOGY_DIR = '/nail/etc/zookeeper_discovery'

ZK_LOCK_CONNECT_TIMEOUT_S = 10.0
ZK_LOCK_TIMEOUT_S = 60.0
ZK_LOCK_PATH = '/configure_nerve'

STATE_DIR = '/var/spool/healthcheck_state'

# CEP337 address for accessing services
YOCALHOST = '169.254.255.254'


def get_hostname():
    return socket.gethostname()


def get_ip_address():
    return socket.gethostbyname(get_hostname())


def get_local_cluster_location(cluster_type=ZK_DEFAULT_CLUSTER_TYPE):
    """Determines the local cluster location from the local link

    For example, suppose on the filesystem we have the following link:
        <cluster_type>/local.yaml -> <cluster_type>/devc.yaml

    This function would return 'devc'
    """
    local_path = os.readlink(
        os.path.join(ZK_TOPOLOGY_DIR, cluster_type, 'local.yaml')
    )
    dest = os.path.split(local_path)[1]
    return os.path.splitext(dest)[0]


def get_named_zookeeper_topology(cluster_type=ZK_DEFAULT_CLUSTER_TYPE,
                                 cluster_location=ZK_DEFAULT_CLUSTER_LOCATION):
    """Use CEP 355 discovery to find zookeeper topologies"""
    zk_topology_path = os.path.join(
        ZK_TOPOLOGY_DIR, cluster_type, cluster_location + '.yaml'
    )
    with open(zk_topology_path) as fp:
        zk_topology = yaml.load(fp)
    return ['%s:%d' % (entry[0], entry[1]) for entry in zk_topology]


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


def get_locations_to_register_in(current_location, routes):
    """A route list configures cross-location communcation between client
    and services. For example, consider the following list of (src, dst)
    pairs:

      [('sfo1', 'uswest1aprod'),
       ('sfo1', 'uswest1bprod'),
       ('sfo2', 'uswest1aprod'),
       ('sfo2', 'uswest1bprod'),
       ('iad1', 'useast1aprod'),
       ('iad1', 'useast1bprod'),
       ('iad1', 'useast1cprod'),
      ]

    This says that a client in the 'sfo1' location should transparently talk to
    service instances in both the 'uswest1aprod' and 'uswest1bprod' locations,
    in addition to any service instances in 'sfo1'.

    OK, but how does this work?  Well, a client can only reach a service instance if
    that instance is registered in the client's location.  So we just need to invert
    the relation to find out where we should be registering.

    For example, if we are a service instance in the 'uswest1aprod' location, then
    we need to register in both the 'sfo1' and 'sfo2' clusters, in addition to the
    'uswest1aprod' cluster.

    Returns: a set of locations
    """

    # Always register in our own location
    locations_to_register_in = set([current_location])

    # Maybe register in some other locations
    locations_to_register_in.update(
        [src for (src, dst) in routes if dst == current_location])

    return locations_to_register_in


def generate_configuration(services):
    nerve_config = {
        'instance_id': get_hostname(),
        'services': {},
    }

    ip_address = get_ip_address()

    try:
        my_location = get_local_cluster_location()
    except OSError:
        print('No local zookeeper cluster link, failing', file=sys.stderr)
        sys.exit(1)

    for (service_name, service_info) in services:
        if not service_is_enabled(service_name):
            continue

        port = service_info.get('port')
        if port is None:
            continue

        mode = service_info.get('mode', 'http')
        healthcheck_timeout_s = service_info.get('healthcheck_timeout_s', 1.0)

        # Nerve will simply ignore this for a TCP mode service
        healthcheck_uri = service_info.get('healthcheck_uri', '/status')

        routes = service_info.get('routes', [])
        locations_to_register_in = get_locations_to_register_in(
            my_location, routes
        )

        # Create a separate service entry for each location that we need to register in.
        for location in locations_to_register_in:
            try:
                zookeeper_topology = get_named_zookeeper_topology(
                    cluster_location=location
                )
            except:
                continue

            key = '%s.%s.%d' % (service_name, location, port)
            nerve_config['services'][key] = {
                'port': port,
                'host': ip_address,
                'zk_hosts': zookeeper_topology,
                'zk_path': '/nerve/%s' % service_name,
                # Perform a healthcheck every ten seconds
                'check_interval': 10,
                # Hit the service on its healthcheck URI
                'checks': [
                    {
                        'type': mode,
                        'host': YOCALHOST,
                        'port': port,
                        'uri': healthcheck_uri,
                        'timeout': healthcheck_timeout_s,
                        'rise': 1,
                        'fall': 2,
                    }
                ]
            }

    return nerve_config


@contextlib.contextmanager
def zookeeper_lock():
    """Context manager to get a lock for the local location."""

    zk_topology = get_named_zookeeper_topology()
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
    new_config = generate_configuration(get_services_running_here_for_nerve())

    with tempfile.NamedTemporaryFile() as tmp_file:
        new_config_path = tmp_file.name
        with open(new_config_path, 'w') as fp:
            json.dump(new_config, fp, sort_keys=True, indent=4, separators=(',', ': '))

        # Match the permissions that puppet expects
        os.chmod(new_config_path, 0644)

        # Restart nerve iff the config files differ
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

                subprocess.check_call(NERVE_RESTART_COMMAND)

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
