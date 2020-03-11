#!/usr/bin/env python

"""Update the nerve configuration file and restart nerve if anything has
changed."""


import argparse
import filecmp
from glob import glob
import json
import multiprocessing
import os
import os.path
import shutil
import signal
import subprocess
import time
import sys
import yaml
from yaml import CSafeLoader
from typing import cast
from typing import Dict
from typing import Iterable
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Sequence
from typing import Tuple


from environment_tools.type_utils import compare_types
from environment_tools.type_utils import convert_location_type
from environment_tools.type_utils import get_current_location
from paasta_tools.long_running_service_tools import ServiceNamespaceConfig
from paasta_tools.marathon_tools import get_marathon_services_running_here_for_nerve
from paasta_tools.marathon_tools import get_puppet_services_running_here_for_nerve
from paasta_tools.native_mesos_scheduler import get_paasta_native_services_running_here_for_nerve
from paasta_tools.kubernetes_tools import get_kubernetes_services_running_here_for_nerve
from paasta_tools.utils import DEFAULT_SOA_DIR

from nerve_tools.config import CheckDict
from nerve_tools.config import NerveConfig
from nerve_tools.config import ServiceInfo
from nerve_tools.config import SubConfiguration
from nerve_tools.envoy import get_envoy_ingress_listeners
from nerve_tools.envoy import get_envoy_service_info
from nerve_tools.envoy import generate_envoy_subsubconfiguration
from nerve_tools.util import get_hostname
from nerve_tools.util import get_host_ip


# Used to determine the weight
try:
    CPUS = max(multiprocessing.cpu_count(), 10)
except NotImplementedError:
    CPUS = 10

DEFAULT_LABEL_DIR = '/etc/nerve/labels.d/'


def get_named_zookeeper_topology(
    cluster_type: str,
    cluster_location: str,
    zk_topology_dir: str,
) -> Iterable[str]:
    """Use CEP 355 discovery to find zookeeper topologies"""
    zk_topology_path = os.path.join(
        zk_topology_dir, cluster_type, cluster_location + '.yaml'
    )
    with open(zk_topology_path) as fp:
        zk_topology = yaml.load(fp, Loader=CSafeLoader)
    return ['%s:%d' % (entry[0], entry[1]) for entry in zk_topology]


def get_labels_by_service_and_port(
    service_name: str,
    port: int,
    labels_dir: str = DEFAULT_LABEL_DIR,
) -> MutableMapping[str, str]:
    custom_labels: Dict[str, str] = {}
    try:
        path = os.path.join(labels_dir, service_name + str(port) + '*')
        for label_file in glob(path):
            with open(label_file) as f:
                custom_labels.update(yaml.load(f, Loader=CSafeLoader))
    except Exception:
        pass
    return custom_labels


def generate_subconfiguration(
    service_name: str,
    service_info: ServiceInfo,
    host_ip: str,
    hacheck_port: int,
    weight: int,
    zk_topology_dir: str,
    zk_location_type: str,
    zk_cluster_type: str,
    labels_dir: str,
    envoy_service_info: Optional[ServiceInfo],
) -> SubConfiguration:

    service_port = service_info['port']
    # if this is a k8s pod the dict will have the pod IP and we have
    # an hacheck sidecar in the pod that caches checks otherwise it is
    # a marathon/puppet etc service and we use the system hacheck
    hacheck_ip = service_info.get('hacheck_ip', '127.0.0.1')
    # ditto for the IP of the service, in k8s this is the pod IP,
    # otherwise we use the hosts IP
    service_ip = service_info.get('service_ip', host_ip)

    mode = service_info.get('mode', 'http')
    healthcheck_timeout_s = service_info.get('healthcheck_timeout_s', 1.0)
    healthcheck_port = service_info.get('healthcheck_port', service_port)

    # hacheck will simply ignore the healthcheck_uri for TCP mode checks
    healthcheck_uri = service_info.get('healthcheck_uri', '/status')
    healthcheck_mode = service_info.get('healthcheck_mode', mode)
    custom_labels = get_labels_by_service_and_port(service_name, service_port, labels_dir=labels_dir)
    hacheck_uri = '/%s/%s/%s/%s' % (
        healthcheck_mode, service_name, healthcheck_port, healthcheck_uri.lstrip('/'))
    advertise = service_info.get('advertise', ['region'])
    extra_advertise = service_info.get('extra_advertise', [])
    healthcheck_headers = service_info.get('extra_healthcheck_headers', {})
    healthcheck_body_expect = service_info.get('healthcheck_body_expect')

    deploy_group = service_info.get('deploy_group')
    paasta_instance = service_info.get('paasta_instance')

    subconfig: SubConfiguration = {}

    if not advertise or not service_port:
        return subconfig

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

        valid_advertise_types = [
            advertise_typ
            for advertise_typ in advertise
            # Prevent upcasts, otherwise the service may be made available to
            # more hosts than intended.
            if compare_types(dst_typ, advertise_typ) <= 0
        ]
        # Convert the destination into the 'advertise' type(s)
        for advertise_typ in valid_advertise_types:
            for loc in convert_location_type(dst_loc, dst_typ, advertise_typ):
                locations_to_register_in.add((loc, advertise_typ))

    # Create a separate service entry for each location that we need to register in.
    for loc, typ in locations_to_register_in:
        zk_locations = convert_location_type(loc, typ, zk_location_type)
        for zk_location in zk_locations:
            try:
                zookeeper_topology = get_named_zookeeper_topology(
                    cluster_type=zk_cluster_type,
                    cluster_location=zk_location,
                    zk_topology_dir=zk_topology_dir,
                )
            except Exception:
                continue

            checks_dict: CheckDict = {
                'type': 'http',
                'host': hacheck_ip,
                'port': hacheck_port,
                'uri': hacheck_uri,
                'timeout': healthcheck_timeout_s,
                'open_timeout': healthcheck_timeout_s,
                'rise': 1,
                'fall': 2,
                'headers': healthcheck_headers,
            }
            if healthcheck_body_expect:
                checks_dict['expect'] = healthcheck_body_expect

            key = '%s.%s:%s.%d.v2.new' % (
                service_name, zk_location, service_ip, service_port,
            )

            if key not in subconfig:
                subconfig[key] = {
                    'port': service_port,
                    'host': service_ip,
                    'zk_hosts': zookeeper_topology,
                    'zk_path': '/smartstack/global/%s' % service_name,
                    'check_interval': healthcheck_timeout_s + 1.0,
                    # Hit the localhost hacheck instance
                    'checks': [
                        checks_dict,
                    ],
                    'labels': {},
                    'weight': weight,
                }

            subconfig[key]['labels'].update(custom_labels)
            # Set a label that maps the location to an empty string. This
            # allows synapse to find all servers being advertised to it by
            # checking discover_typ:discover_loc == ''
            subconfig[key]['labels']['%s:%s' % (typ, loc)] = ''

            # Having the deploy group and paasta instance will enable Envoy
            # routing via these values for canary instance routing
            if deploy_group:
                subconfig[key]['labels']['deploy_group'] = deploy_group
            if paasta_instance:
                subconfig[key]['labels']['paasta_instance'] = paasta_instance

            if envoy_service_info:
                envoy_key = f'{service_name}.{zk_location}:{service_ip}.{service_port}'
                subconfig[envoy_key] = generate_envoy_subsubconfiguration(
                    envoy_service_info,
                    healthcheck_mode,
                    service_name,
                    hacheck_port,
                    service_ip,
                    zookeeper_topology,
                    subconfig[key]['labels'],
                    weight,
                    deploy_group,
                    paasta_instance,
                )

    return subconfig


def generate_configuration(
    paasta_services: Iterable[Tuple[str, ServiceNamespaceConfig]],
    puppet_services: Iterable[Tuple[str, ServiceNamespaceConfig]],
    heartbeat_path: str,
    hacheck_port: int,
    weight: int,
    zk_topology_dir: str,
    zk_location_type: str,
    zk_cluster_type: str,
    labels_dir: str,
    envoy_ingress_listeners: Mapping[Tuple[str, str, int], int],
) -> NerveConfig:
    nerve_config: NerveConfig = {
        'instance_id': get_hostname(),
        'services': {},
        'heartbeat_path': heartbeat_path
    }

    host_ip = get_host_ip()

    def update_subconfiguration_for_here(
        service_name: str,
        service_info: ServiceInfo,
        service_weight: int,
        envoy_service_info: Optional[ServiceInfo],
    ) -> None:
        nerve_config['services'].update(
            generate_subconfiguration(
                service_name=service_name,
                service_info=service_info,
                weight=service_weight,
                host_ip=host_ip,
                hacheck_port=hacheck_port,
                zk_topology_dir=zk_topology_dir,
                zk_location_type=zk_location_type,
                zk_cluster_type=zk_cluster_type,
                labels_dir=labels_dir,
                envoy_service_info=envoy_service_info,
            )
        )

    for (service_name, service_info) in puppet_services:
        update_subconfiguration_for_here(
            service_name=service_name,
            service_info=cast(ServiceInfo, service_info),
            service_weight=weight,
            envoy_service_info=get_envoy_service_info(
                service_name=service_name,
                service_info=cast(ServiceInfo, service_info),
                envoy_ingress_listeners=envoy_ingress_listeners,
            ),
        )

    for (service_name, service_info) in paasta_services:
        update_subconfiguration_for_here(
            service_name=service_name,
            service_info=cast(ServiceInfo, service_info),
            service_weight=10,
            envoy_service_info=get_envoy_service_info(
                service_name=service_name,
                service_info=cast(ServiceInfo, service_info),
                envoy_ingress_listeners=envoy_ingress_listeners,
            ),
        )

    return nerve_config


def file_not_modified_since(
    path: str,
    threshold: int,
) -> bool:
    """Returns true if a file has not been modified within some number of seconds

    :param path: a file path
    :param threshold: number of seconds
    :return: true if the file has not been modified within specified number of seconds, false otherwise
    """
    if os.path.isfile(path):
        return os.path.getmtime(path) < time.time() - threshold
    else:
        return False


def parse_args(
    args: Sequence[str],
) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--heartbeat-path', default="/var/run/nerve/heartbeat",
                        help='path to nerve heartbeat file to monitor')
    parser.add_argument('-s', '--heartbeat-threshold', type=int, default=60,
                        help='if heartbeat file is not updated within this many seconds then nerve is restarted')
    parser.add_argument('--nerve-config-path', type=str, default='/etc/nerve/nerve.conf.json')
    parser.add_argument('--reload-with-sighup', action='store_true')
    parser.add_argument('--nerve-pid-path', type=str, default='/var/run/nerve.pid')
    parser.add_argument('--nerve-executable-path', type=str, default='/usr/bin/nerve')
    parser.add_argument('--nerve-backup-command', type=json.loads, default='["service", "nerve-backup"]')
    parser.add_argument('--nerve-command', type=json.loads, default='["service", "nerve"]')
    parser.add_argument('--nerve-registration-delay-s', type=int, default=30)
    parser.add_argument('--zk-topology-dir', type=str, default='/nail/etc/zookeeper_discovery')
    parser.add_argument('--zk-location-type', type=str, default='superregion',
                        help="What location type do the zookeepers live at?")
    parser.add_argument('--zk-cluster-type', type=str, default='infrastructure')
    parser.add_argument('--hacheck-port', type=int, default=6666)
    parser.add_argument('--weight', type=int, default=CPUS,
                        help='weight to advertise each service at. Defaults to # of CPUs')
    parser.add_argument('--labels-dir', type=str, default=DEFAULT_LABEL_DIR,
                        help='Directory containing custom labels for nerve services.')
    parser.add_argument('--envoy-admin-port', type=int, default=9901,
                        help='Port for envoy admin to get configured envoy listeners.')

    return parser.parse_args(args)


def main() -> None:
    opts = parse_args(sys.argv[1:])
    new_config = generate_configuration(
        paasta_services=(
            get_marathon_services_running_here_for_nerve(  # type: ignore
                cluster=None,
                soa_dir=DEFAULT_SOA_DIR,
            ) + get_paasta_native_services_running_here_for_nerve(
                cluster=None,
                soa_dir=DEFAULT_SOA_DIR,
            ) + get_kubernetes_services_running_here_for_nerve(
                cluster=None,
                soa_dir=DEFAULT_SOA_DIR,
            )
        ),
        puppet_services=get_puppet_services_running_here_for_nerve(
            soa_dir=DEFAULT_SOA_DIR,
        ),
        heartbeat_path=opts.heartbeat_path,
        hacheck_port=opts.hacheck_port,
        weight=opts.weight,
        zk_topology_dir=opts.zk_topology_dir,
        zk_location_type=opts.zk_location_type,
        zk_cluster_type=opts.zk_cluster_type,
        labels_dir=opts.labels_dir,
        envoy_ingress_listeners=get_envoy_ingress_listeners(opts.envoy_admin_port),
    )

    # Must use os.rename on files in the same filesystem to ensure that
    # config is swapped atomically, so we need to create the temp file in
    # the same directory as the config file
    new_config_path = '{0}.tmp'.format(opts.nerve_config_path)

    with open(new_config_path, 'w') as fp:
        json.dump(new_config, fp, sort_keys=True, indent=4, separators=(',', ': '))

    # Match the permissions that puppet expects
    os.chmod(new_config_path, 0o644)

    # Restart/reload nerve if the config files differ
    # Always force a restart if the heartbeat file is old
    should_reload = not filecmp.cmp(new_config_path, opts.nerve_config_path)
    should_restart = file_not_modified_since(opts.heartbeat_path, opts.heartbeat_threshold)

    # Always swap new config file into place, even if we're not going to
    # restart nerve. Our monitoring system checks the opts.nerve_config_path
    # file age to ensure that this script is functioning correctly.
    try:
        # Verify the new config is _valid_
        command = [opts.nerve_executable_path]
        command.extend(['-c', new_config_path, '-k'])
        subprocess.check_call(command)

        # Move the config over
        shutil.move(new_config_path, opts.nerve_config_path)
    except subprocess.CalledProcessError:
        # Nerve config is invalid!, bail out **without restarting**
        # so staleness monitoring can trigger and alert us of a problem
        return

    # If we can reload with SIGHUP, use that, otherwise use the normal
    # graceful method
    if should_reload and opts.reload_with_sighup:
        try:
            with open(opts.nerve_pid_path) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGHUP)
        except (OSError, ValueError, IOError):
            # invalid pid file, time to restart
            should_restart = True
        else:
            # Always try to stop the backup process
            subprocess.call(opts.nerve_backup_command + ['stop'])
    else:
        should_restart |= should_reload

    if should_restart:
        # Try to do a graceful restart by starting up the backup nerve
        # prior to restarting the main nerve. Then once the main nerve
        # is restarted, stop the backup nerve.
        try:
            subprocess.call(opts.nerve_backup_command + ['start'])
            time.sleep(opts.nerve_registration_delay_s)

            subprocess.check_call(opts.nerve_command + ['stop'])
            subprocess.check_call(opts.nerve_command + ['start'])
            time.sleep(opts.nerve_registration_delay_s)
        finally:
            # Always try to stop the backup process
            subprocess.call(opts.nerve_backup_command + ['stop'])


if __name__ == '__main__':
    main()
