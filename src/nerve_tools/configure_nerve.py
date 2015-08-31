#!/usr/bin/env python

"""Update the nerve configuration file and restart nerve if anything has
changed."""

from __future__ import absolute_import, division, print_function

import argparse
import filecmp
import json
import multiprocessing
import os
import os.path
import shutil
import socket
import subprocess
import tempfile
import time
import sys
import yaml

from environment_tools.type_utils import compare_types
from environment_tools.type_utils import convert_location_type
from environment_tools.type_utils import get_current_location
from paasta_tools.marathon_tools import get_services_running_here_for_nerve


NERVE_CONFIG_PATH = '/etc/nerve/nerve.conf.json'
NERVE_BACKUP_COMMAND = ['service', 'nerve-backup']
NERVE_COMMAND = ['service', 'nerve']
NERVE_REGISTRATION_DELAY_S = 30

# Used to determine the weight
try:
    CPUS = max(multiprocessing.cpu_count(), 10)
except NotImplementedError:
    CPUS = 10

# CEP 355 Zookeepers
ZK_TOPOLOGY_DIR = '/nail/etc/zookeeper_discovery'

HACHECK_PORT = 6666


def get_hostname():
    return socket.gethostname()


def get_ip_address():
    return socket.gethostbyname(get_hostname())


def get_named_zookeeper_topology(cluster_type, cluster_location):
    """Use CEP 355 discovery to find zookeeper topologies"""
    zk_topology_path = os.path.join(
        ZK_TOPOLOGY_DIR, cluster_type, cluster_location + '.yaml'
    )
    with open(zk_topology_path) as fp:
        zk_topology = yaml.load(fp)
    return ['%s:%d' % (entry[0], entry[1]) for entry in zk_topology]


def generate_subconfiguration(service_name, advertise, extra_advertise, port,
                              ip_address, healthcheck_timeout_s, hacheck_uri, healthcheck_headers):
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

            key = '%s.%s.%s:%s.%d.new' % (
                service_name, superregion, typ, loc, port
            )
            config[key] = {
                'port': port,
                'host': ip_address,
                'weight': CPUS,
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
                        'open_timeout': healthcheck_timeout_s,
                        'rise': 1,
                        'fall': 2,
                        'headers': healthcheck_headers,
                    }
                ]
            }

    return config


def generate_configuration(services, heartbeat_path):
    nerve_config = {
        'instance_id': get_hostname(),
        'services': {},
        'heartbeat_path': heartbeat_path
    }

    ip_address = get_ip_address()

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
        advertise = service_info.get('advertise', ['region'])
        extra_advertise = service_info.get('extra_advertise', [])
        extra_healthcheck_headers = service_info.get('extra_healthcheck_headers', {})

        nerve_config['services'].update(
            generate_subconfiguration(
                service_name=service_name,
                advertise=advertise,
                extra_advertise=extra_advertise,
                port=port,
                ip_address=ip_address,
                healthcheck_timeout_s=healthcheck_timeout_s,
                hacheck_uri=hacheck_uri,
                healthcheck_headers=extra_healthcheck_headers
            )
        )

    return nerve_config


def file_not_modified_since(path, threshold):
    """Returns true if a file has not been modified within some number of seconds

    :param path: a file path
    :param threshold: number of seconds
    :return: true if the file has not been modified within specified number of seconds, false otherwise
    """
    if os.path.isfile(path):
        return os.path.getmtime(path) < time.time() - threshold
    else:
        return False


def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--heartbeat-path', default="/var/run/nerve/heartbeat",
                        help='path to nerve heartbeat file to monitor')
    parser.add_argument('-s', '--heartbeat-threshold', type=int, default=NERVE_REGISTRATION_DELAY_S * 2,
                        help='if heartbeat file is not updated within this many seconds then nerve is restarted')
    return parser.parse_args(args)


def main():
    opts = parse_args(sys.argv[1:])
    new_config = generate_configuration(get_services_running_here_for_nerve(), opts.heartbeat_path)

    with tempfile.NamedTemporaryFile() as tmp_file:
        new_config_path = tmp_file.name
        with open(new_config_path, 'w') as fp:
            json.dump(new_config, fp, sort_keys=True, indent=4, separators=(',', ': '))

        # Match the permissions that puppet expects
        os.chmod(new_config_path, 0644)

        # Restart nerve if the config files differ or if heartbeat file is old
        should_restart = (not filecmp.cmp(new_config_path, NERVE_CONFIG_PATH) or
                          file_not_modified_since(opts.heartbeat_path, opts.heartbeat_threshold))

        if should_restart:
            shutil.copy(new_config_path, NERVE_CONFIG_PATH)

            # Try to do a graceful restart by starting up the backup nerve
            # prior to restarting the main nerve. Then once the main nerve
            # is restarted, stop the backup nerve.
            try:
                subprocess.call(NERVE_BACKUP_COMMAND + ['start'])
                time.sleep(NERVE_REGISTRATION_DELAY_S)

                subprocess.check_call(NERVE_COMMAND + ['stop'])
                subprocess.check_call(NERVE_COMMAND + ['start'])
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
