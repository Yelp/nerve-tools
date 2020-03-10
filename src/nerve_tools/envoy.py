import copy
import logging
import re
from typing import cast
from typing import Mapping
from typing import Iterable
from typing import Optional
from typing import Dict
from typing import Tuple

import requests

from nerve_tools.config import CheckDict
from nerve_tools.config import ListenerConfig
from nerve_tools.config import ServiceInfo
from nerve_tools.config import SubSubConfiguration
from nerve_tools.util import get_host_ip


INGRESS_LISTENER_REGEX = re.compile(
    r'^(?P<service_name>\S+\.\S+)\.(?P<service_ip>\d+\.\d+\.\d+\.\d+)\.(?P<service_port>\d+)\.ingress_listener$'
)

MESOS_SERVICE_IP = '0.0.0.0'


def _get_envoy_listeners_from_admin(admin_port: int) -> Mapping[str, Iterable[ListenerConfig]]:
    try:
        return requests.get(f'http://localhost:{admin_port}/listeners?format=json').json()
    except Exception as e:
        logging.warning(f'Unable to get envoy listeners: {e}')
        return {}


def get_envoy_ingress_listeners(admin_port: int) -> Mapping[Tuple[str, str, int], int]:
    """Compile a mapping of (service, ip, port) -> envoy ingress port for service

    This will be used to determine the Envoy ingress port for a given service's actual port.
    """
    envoy_listeners: Dict[
        Tuple[
            str,  # service name
            str,  # service ip
            int   # service port
        ],
        int,      # ingress envoy port for service
    ] = {}

    envoy_listeners_config = _get_envoy_listeners_from_admin(admin_port)

    for listener in envoy_listeners_config.get('listener_statuses', []):
        result = INGRESS_LISTENER_REGEX.match(listener['name'])
        if result:
            service_name = result.group('service_name')
            service_ip = result.group('service_ip')
            service_port = int(result.group('service_port'))
            try:
                envoy_listeners[(service_name, service_ip, service_port)] = \
                    int(listener['local_address']['socket_address']['port_value'])
            except KeyError:
                # If there is no socket_address and port_value, skip this listener
                pass
    return envoy_listeners


def get_envoy_service_info(
    service_name: str,
    service_info: ServiceInfo,
    envoy_ingress_listeners: Mapping[Tuple[str, str, int], int],
) -> Optional[ServiceInfo]:
    envoy_service_info: Optional[ServiceInfo] = None

    # Previously, mesos managed services running on this host had unique ports so
    # mesos port -> envoy ingress port mapping was pretty straight forward. With
    # Kubernetes services, the port is not guaranteed to be unique to this host
    # because of the pod abstraction which introduces a pod ip address. Thus, to
    # maintain a valid mapping, a composite key (service_name, servie_ip, service_port) is used
    # to map to the service's envoy ingress port.
    key = (service_name, service_info.get('service_ip', MESOS_SERVICE_IP), service_info['port'])

    # If this service's local host port is being routed to from an Envoy ingress port,
    # then output nerve configs so that this service will be healthchecked through
    # the Envoy ingress port. This requires setting the healthcheck Host header too
    # because Envoy uses the Host header for request routing.
    #
    # WARNING: Configuring nerve to have services healthchecked through Envoy may
    # result in race conditions. The Envoy control plane will set up ingress ports
    # based on a snapshot of currently running services on the local host, but the
    # snapshot may change after the Envoy control plane does its work and before
    # configure_nerve.py is run. This may result in a difference between what is
    # actually running locally and the ingress ports that were set up. The worst
    # case scenario is that nerve will start healthchecking services that aren't
    # set up for routing in Envoy. In this case, healthchecks will fail, the service
    # will not be registered in ZooKeeper, and the system will eventually be consistent.
    if key in envoy_ingress_listeners:
        service_info_copy = copy.deepcopy(service_info)
        envoy_ingress_port = envoy_ingress_listeners[key]
        healthcheck_headers: Dict[str, str] = {}
        healthcheck_headers.update(service_info_copy.get('extra_healthcheck_headers', {}))
        healthcheck_headers['Host'] = service_name
        service_info_copy.update({
            'host': get_host_ip(),
            'port': envoy_ingress_port,
            'healthcheck_port': envoy_ingress_port,
            'extra_healthcheck_headers': healthcheck_headers,
        })
        envoy_service_info = cast(Optional[ServiceInfo], service_info_copy)
    return envoy_service_info


def generate_envoy_subsubconfiguration(
    envoy_service_info: ServiceInfo,
    healthcheck_mode: str,
    service_name: str,
    hacheck_port: int,
    service_ip: str,
    zookeeper_topology: Iterable[str],
    labels: Dict[str, str],
    weight: int,
    deploy_group: Optional[str],
    paasta_instance: Optional[str],
) -> SubSubConfiguration:

    # hacheck healthchecks through envoy
    healthcheck_port = envoy_service_info['port']
    healthcheck_uri = envoy_service_info.get('healthcheck_uri', '/status')

    # healthchecks via envoy for `http` services should be made via `https`.
    healthcheck_mode = 'https' if healthcheck_mode == 'http' else healthcheck_mode

    envoy_hacheck_uri = \
        f"/{healthcheck_mode}/{service_name}/{healthcheck_port}/{healthcheck_uri.lstrip('/')}"

    healthcheck_timeout_s = envoy_service_info.get('healthcheck_timeout_s', 1.0)

    checks_dict: CheckDict = {
        'type': 'http',
        'host': get_host_ip(),
        'port': hacheck_port,
        'uri': envoy_hacheck_uri,
        'timeout': healthcheck_timeout_s,
        'open_timeout': healthcheck_timeout_s,
        'rise': 1,
        'fall': 2,
        'headers': envoy_service_info['extra_healthcheck_headers'],
    }

    return SubSubConfiguration(
        port=envoy_service_info['port'],
        host=get_host_ip(),
        zk_hosts=zookeeper_topology,
        zk_path=f'/envoy/global/{service_name}',
        check_interval=healthcheck_timeout_s + 1.0,
        checks=[
            checks_dict,
        ],
        labels=labels,
        weight=weight,
    )
