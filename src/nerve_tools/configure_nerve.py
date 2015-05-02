#!/usr/bin/env python

"""Update the nerve configuration file and restart nerve if anything has
changed."""

from __future__ import absolute_import, division, print_function

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

import yaml

from environment_tools.type_utils import compare_types
from environment_tools.type_utils import convert_location_type
from environment_tools.type_utils import get_current_location
from paasta_tools.marathon_tools import get_services_running_here_for_nerve


NERVE_CONFIG_PATH = '/etc/nerve/nerve.conf.json'
NERVE_BACKUP_COMMAND = ['service', 'nerve-backup']
NERVE_COMMAND = ['service', 'nerve']
NERVE_REGISTRATION_DELAY_S = 30

# CEP 355 Zookeepers
ZK_DEFAULT_CLUSTER_TYPE = 'generic'
ZK_DEFAULT_CLUSTER_LOCATION = 'local'
ZK_TOPOLOGY_DIR = '/nail/etc/zookeeper_discovery'

STATE_DIR = '/var/spool/healthcheck_state'

HACHECK_PORT = 6666


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


def generate_configuration_old(service_name, my_location, routes, port,
                               ip_address, healthcheck_timeout_s, hacheck_uri):
    locations_to_register_in = get_locations_to_register_in(my_location, routes)

    # Create a separate service entry for each location that we need to register in.
    config = {}
    for location in locations_to_register_in:
        try:
            zookeeper_topology = get_named_zookeeper_topology(
                cluster_type='generic',
                cluster_location=location
            )
        except:
            continue

        key = '%s.%s.%d' % (service_name, location, port)
        config[key] = {
            'port': port,
            'host': ip_address,
            'zk_hosts': zookeeper_topology,
            'zk_path': '/nerve/%s' % service_name,
            'check_interval': healthcheck_timeout_s + 1.0,
            # Hit the localhost hacheck instance
            'checks': [
                {
                    'type': 'http',
                    'host': '127.0.0.1',
                    'port': HACHECK_PORT,
                    'uri': hacheck_uri,
                    'timeout': healthcheck_timeout_s,
                    'rise': 1,
                    'fall': 2,
                }
            ]
        }

    return config


# New registration (SRV-1559)
def generate_configuration_new(service_name, advertise, extra_advertise, port,
                               ip_address, healthcheck_timeout_s, hacheck_uri):
    config = {}

    # Register at the specified location types in the current superregion
    locations_to_register_in = set()
    for advertise_typ in advertise:
        locations_to_register_in.add((get_current_location(advertise_typ), advertise_typ))

    # Also register in any other locations specified in extra advertisements
    for (src, dst) in extra_advertise:
        src_typ, src_loc = src.split(':')
        dst_typ, dst_loc = dst.split(':')
        if get_current_location(src_typ) != src_loc:
            # We do not match the source
            continue
        # Convert the destination into the 'advertise' type(s)
        for advertise_typ in advertise:
            # Prevent upcasts, otherwise the service may be made available to
            # more hosts than intended.
            if compare_types(dst_typ, advertise_typ) > 0:
                continue
            for loc in convert_location_type(dst_loc, dst_typ, advertise_typ):
                locations_to_register_in.add((loc, advertise_typ))

    # Create a separate service entry for each location that we need to register in.
    for loc, typ in locations_to_register_in:
        superregions = convert_location_type(loc, typ, 'superregion')
        for superregion in superregions:
            try:
                zookeeper_topology = get_named_zookeeper_topology(
                    cluster_type='infrastructure',
                    cluster_location=superregion
                )
            except:
                continue

            key = '%s.%s.%d.new' % (service_name, loc, port)
            config[key] = {
                'port': port,
                'host': ip_address,
                'zk_hosts': zookeeper_topology,
                'zk_path': '/nerve/%s:%s/%s' % (typ, loc, service_name),
                'check_interval': healthcheck_timeout_s + 1.0,
                # Hit the localhost hacheck instance
                'checks': [
                    {
                        'type': 'http',
                        'host': '127.0.0.1',
                        'port': HACHECK_PORT,
                        'uri': hacheck_uri,
                        'timeout': healthcheck_timeout_s,
                        'rise': 1,
                        'fall': 2,
                    }
                ]
            }

    return config


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
        port = service_info.get('port')
        if port is None:
            continue

        mode = service_info.get('mode', 'http')
        healthcheck_timeout_s = service_info.get('healthcheck_timeout_s', 1.0)
        healthcheck_port = service_info.get('healthcheck_port', port)

        # hacheck will simply ignore this for a TCP mode service
        healthcheck_uri = service_info.get('healthcheck_uri', '/status')
        hacheck_uri = '/%s/%s/%s/%s' % (
            mode, service_name, healthcheck_port, healthcheck_uri.lstrip('/'))
        routes = service_info.get('routes', [])
        advertise = service_info.get('advertise', ['region'])
        extra_advertise = service_info.get('extra_advertise', [])

        nerve_config['services'].update(
            generate_configuration_old(
                service_name=service_name,
                my_location=my_location,
                routes=routes,
                port=port,
                ip_address=ip_address,
                healthcheck_timeout_s=healthcheck_timeout_s,
                hacheck_uri=hacheck_uri
            )
        )

        nerve_config['services'].update(
            generate_configuration_new(
                service_name=service_name,
                advertise=advertise,
                extra_advertise=extra_advertise,
                port=port,
                ip_address=ip_address,
                healthcheck_timeout_s=healthcheck_timeout_s,
                hacheck_uri=hacheck_uri,
            )
        )

    return nerve_config


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
            shutil.copy(new_config_path, NERVE_CONFIG_PATH)

            # Try to do a graceful restart by starting up the backup nerve
            # prior to restarting the main nerve. Then once the main nerve
            # is restarted, stop the backup nerve.
            try:
                subprocess.call(NERVE_BACKUP_COMMAND + ['start'])
                time.sleep(NERVE_REGISTRATION_DELAY_S)

                subprocess.check_call(NERVE_COMMAND + ['restart'])
                time.sleep(NERVE_REGISTRATION_DELAY_S)
            finally:
                # Always try to stop the backup process
                subprocess.call(NERVE_BACKUP_COMMAND + ['stop'])

        else:
            # Always swap new config file into place, even if we're not going to
            # restart nerve.  Our monitoring system checks the NERVE_CONFIG_PATH
            # file age to ensure that this script is functioning correctly.
            shutil.copy(new_config_path, NERVE_CONFIG_PATH)


if __name__ == '__main__':
    main()
