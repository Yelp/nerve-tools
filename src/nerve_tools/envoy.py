import copy
import logging
import re
from typing import cast
from typing import Mapping
from typing import Iterable
from typing import Optional
from typing import Dict

import requests

from nerve_tools.config import CheckDict
from nerve_tools.config import ListenerConfig
from nerve_tools.config import ServiceInfo
from nerve_tools.config import SubSubConfiguration
from nerve_tools.util import get_ip_address


INGRESS_LISTENER_REGEX = re.compile(r'^\S+\.\S+\.(?P<port>\d+)\.ingress_listener$')


def _get_envoy_listeners_from_admin(admin_port: int) -> Mapping[str, Iterable[ListenerConfig]]:
    try:
        return requests.get(f'http://localhost:{admin_port}/listeners?format=json').json()
    except Exception as e:
        logging.warning(f'Unable to get envoy listeners: {e}')
        return {}


def get_envoy_ingress_listeners(admin_port: int) -> Mapping[int, int]:
    """Compile a mapping of "service's local listening port" -> "the corresponding Envoy
    ingress port".

    This will be used to determine the Envoy ingress port for a given service's actual port.
    """
    envoy_listeners: Dict[int, int] = {}
    envoy_listeners_config = _get_envoy_listeners_from_admin(admin_port)

    for listener in envoy_listeners_config.get('listener_statuses', []):
        result = INGRESS_LISTENER_REGEX.match(listener['name'])
        if result:
            local_host_port = result.group('port')
            try:
                envoy_listeners[int(local_host_port)] = \
                    int(listener['local_address']['socket_address']['port_value'])
            except KeyError:
                # If there is no socket_address and port_value, skip this listener
                pass
    return envoy_listeners


def _get_envoy_service_info(
    service_name: str,
    service_info: ServiceInfo,
    envoy_ingress_listeners: Mapping[int, int],
) -> Optional[ServiceInfo]:
    envoy_service_info: Optional[ServiceInfo] = None
    local_host_port = service_info['port']
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
    if local_host_port in envoy_ingress_listeners:
        service_info_copy = copy.deepcopy(service_info)
        envoy_ingress_port = envoy_ingress_listeners[local_host_port]
        healthcheck_headers: Dict[str, str] = {}
        healthcheck_headers.update(service_info_copy.get('extra_healthcheck_headers', {}))
        healthcheck_headers['Host'] = service_name
        service_info_copy.update({
            'host': get_ip_address(),
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
    ip_address: str,
    zookeeper_topology: Iterable[str],
    labels: Dict[str, str],
    weight: int,
    deploy_group: Optional[str],
    paasta_instance: Optional[str],
) -> SubSubConfiguration:

    # The service is full mesh enabled if we've gotten this far.
    # Generate proper configs for:
    # 1. Mesos: envoy_ingress_port -> local mesos docker port -> service
    # 2. Kubernetes: envoy_ingress_port -> pod ip:port -> service

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
        'host': get_ip_address(),
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
        host=envoy_service_info.get('service_ip', ip_address),
        zk_hosts=zookeeper_topology,
        zk_path=f'/envoy/global/{service_name}',
        check_interval=healthcheck_timeout_s + 1.0,
        checks=[
            checks_dict,
        ],
        labels=labels,
        weight=weight,
    )
