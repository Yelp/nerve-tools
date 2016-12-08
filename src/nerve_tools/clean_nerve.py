#!/usr/bin/env python

# We're finding orphaned nerve service instance nodes in ZK.  These nodes
# contain no data and have no ephemeral owner.  The cause is currently unclear.
# This script will remove those nodes.  See SRV-1418 for more information.

import glob
import logging
import os

import argparse
import kazoo.client
import kazoo.exceptions
import yaml
from yaml import CLoader


# CEP 355 Zookeepers
ZK_DEFAULT_CLUSTER_TYPE = 'infrastructure'
ZK_TOPOLOGY_DIR = '/nail/etc/zookeeper_discovery'

LOG_FORMAT = '%(levelname)s %(message)s'
log = logging.getLogger()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--simulate', action='store_true',
                        help='Simluate only; do not actually delete any nodes.')
    parser.add_argument('-t', '--cluster-type', default=ZK_DEFAULT_CLUSTER_TYPE,
                        help='Cluster type (default: %(default)s).')
    return parser.parse_args()


def get_zk_cluster_locations(cluster_type):
    for path in glob.glob('%s/%s/*.yaml' % (ZK_TOPOLOGY_DIR, cluster_type)):
        if os.path.islink(path):
            # Ignore the 'local.yaml' symlink
            continue
        yield os.path.basename(path).replace('.yaml', '')


def get_zk_topology(cluster_type, cluster_location):
    zk_topology_path = os.path.join(
        ZK_TOPOLOGY_DIR, cluster_type, cluster_location + '.yaml'
    )
    with open(zk_topology_path) as fp:
        zk_topology = yaml.load(fp, Loader=CLoader)
    return ['%s:%d' % (entry[0], entry[1]) for entry in zk_topology]


def clean(simulate, zk):
    removed_count = 0
    services = []

    services = zk.get_children('/smartstack/global')
    for service in services:
        instances = zk.get_children('/smartstack/global/%s' % service)
        for instance in instances:
            path = '/smartstack/global/%s/%s' % (service, instance)
            try:
                data, stat = zk.get(path)
            except kazoo.exceptions.NoNodeError:
                continue

            if len(data) != 0:
                continue
            if stat.ephemeralOwner != 0:
                continue
            if stat.numChildren != 0:
                continue

            log.info('Removing %s' % path)
            removed_count += 1
            if not simulate:
                zk.delete(path)

    return removed_count


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.getLogger('kazoo').setLevel(logging.ERROR)

    args = parse_args()
    if args.simulate:
        log.info('Running in simulation mode')

    for cluster_location in get_zk_cluster_locations(args.cluster_type):
        log.info('Processing %s' % cluster_location)

        zk_topology = get_zk_topology(args.cluster_type, cluster_location)
        zk_hosts = ','.join(zk_topology)
        zk = kazoo.client.KazooClient(hosts=zk_hosts)

        try:
            zk.start()
        except:
            log.warn('Could not connect to zookeeper cluster for %s' % cluster_location)
            continue

        try:
            removed_count = clean(args.simulate, zk)
            log.info('Removed %d nodes' % removed_count)
        finally:
            zk.stop()


if __name__ == '__main__':
    main()
