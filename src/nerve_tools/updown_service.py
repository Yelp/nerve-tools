# Utility to change local service mesh service state

import os
import socket
import subprocess
import sys
import time
import yaml
from pathlib import Path

import argparse
import requests
from requests.exceptions import RequestException

from paasta_tools.marathon_tools import load_service_namespace_config
from service_configuration_lib import read_service_configuration


# Maximum amount of time to run before returning
DEFAULT_TIMEOUT_S = 300

# Even though a service has entered the expected state in our local HAProxy
# instance, there may still be a short delay before all remote HAProxy instances
# also pick up this change.  So we add an additional delay before returning.
# This also allows service instances to finish serving any existing requests
# before we shut them down.
DEFAULT_WAIT_TIME_S = 5

ENVOY_POLL_INTERVAL_S = 1


def service_name(
    service: str,
) -> str:
    try:
        name, instance = service.split('.')
        try:
            instance_port = instance.split(':')
            if len(instance_port) == 2:
                int(instance_port[1])
        except ValueError:
            raise argparse.ArgumentTypeError('Port is not a number')
    except ValueError:
        msg = 'Namespace missing from service name'
        raise argparse.ArgumentTypeError(msg)
    return service


def get_args() -> argparse.Namespace:
    description = "Control SmartStack service state in load balancers"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-t", "--timeout", type=int,
                        help="Maximum time to wait for <state> \
                        (default: updown_timeout_s if set, otherwise {0})".format(DEFAULT_TIMEOUT_S))
    parser.add_argument("-w", "--wait-time", default=DEFAULT_WAIT_TIME_S, type=int,
                        help="Additional number of seconds to wait for convergence (default: %(default)s)")
    parser.add_argument("-x", "--wait-only", action="store_true",
                        help="Wait for the specified state without reconfiguring hacheck")
    parser.add_argument("--envoy-eds-dir", help="if set, check for mesh convergence by looking at envoy")
    parser.add_argument(
        "service", type=service_name,
        help=(
            "Service name, including namespace and optionally port: "
            "service_name.service_instance[:port] e.g. 'service_one.main' or "
            "'service_one.main:30021'"
        )
    )
    parser.add_argument("state", choices=['up', 'down'], help="desired state")
    args = parser.parse_args()
    if ':' in args.service:
        service, port = args.service.split(':')
        args.service, args.port = service, int(port)
    else:
        args.service, args.port = args.service, None
    return args


def reconfigure_hacheck(
    service: str,
    state: str,
    port: int,
) -> None:
    if state == 'down':
        hacheck_command = '/usr/bin/hadown'
    else:
        hacheck_command = '/usr/bin/haup'

    command = [hacheck_command, service]
    if port is not None:
        command.extend(['-P', str(port)])

    try:
        subprocess.check_call(command)
    except Exception:
        print("Error running %s" % hacheck_command, file=sys.stderr)


def get_my_ip_address() -> str:
    return socket.gethostbyname(socket.getfqdn())

def check_envoy_state(
    service: str,
    expected_state: str,
    envoy_eds_dir: str,
) -> bool:
    """If the expected_state is 'up', then return 'true' iff the local service
    instance is 'up' in Envoy.

    If the expected_state is 'down', then return 'true' iff the local service
    instance is NOT available in the local Envoy EDS config
    """
    raw_endpoint_file = Path(envoy_eds_dir) / service / f"{service}.yaml"
    if not raw_endpoint_file.exists():
        # not much we can do if this file doesn't exist
        return False


    # we only have egress clusters and will always have one entry in the resources list
    # (even if there's no endpoints) so we can just unconditionally reach in and grab
    # the endpoint list without doing any further checks
    endpoints = []
    for entry in yaml.safe_load(raw_endpoint_file.read_text())["resources"][0]["endpoints"]:
        if entry.get("lb_endpoints"):
            endpoints.extend(entry["lb_endpoints"])

    host = get_my_ip_address()

    if len(endpoints) == 0:
        msg = 'No backends present in the service mesh, have you added any?'
        print(msg, file=sys.stderr)
        sys.exit(1)

    entries = [
        # yup, this is very aesthetic...
        endpoint
        for endpoint in endpoints
        if host in endpoint['endpoint']['address']['socket_address']['address']
    ]

    if len(entries) == 0:
        # We did not find our host
        return expected_state == 'down'
    else:
        # there's no concept of states - you're either up (present as an endpoint)
        # or you're down (not present as an endpoint)
        # TODO: take into account outlier ejection?
        return expected_state == 'up'


def check_local_healthcheck(
    service_name: str,
) -> bool:
    """Makes a local HTTP healthcheck call to the service and returns True if
    it gets a 2XX response, else returns False.

    :param service_name: a string like 'service_one.main'
    :return: Whether healthcheck call was successful for a http service.
    Returns false for a tcp service.
    :rtype: boolean
    """
    srv_name, namespace = service_name.split('.')
    srv_config = read_service_configuration(srv_name)
    smartstack_config = srv_config.get('smartstack', {})
    namespace_config = smartstack_config.get(namespace, {})

    healthcheck_uri = namespace_config.get('healthcheck_uri', '/status')
    healthcheck_port = namespace_config.get('healthcheck_port',
                                            srv_config.get('port'))
    healthcheck_mode = namespace_config.get('mode', 'http')

    # TODO: Add support for TCP healthcheck using hacheck - Ref. RB: 109478
    if healthcheck_mode == 'http' and healthcheck_port:
        try:
            url = "http://{host}:{port}{uri}".format(
                host="127.0.0.1", port=healthcheck_port, uri=healthcheck_uri)
            requests.get(url).raise_for_status()
            return True
        except RequestException as e:
            print("Calling {0}, got - {1}".format(url, str(e)), file=sys.stderr)

    return False

def wait_for_envoy_state(
    service: str,
    expected_state: str,
    timeout: int,
    wait_time: int,
    envoy_eds_dir: str,
) -> int:
    """Wait for the specified service to enter the given state in Envoy."""
    # This isn't precise, but it's easy to test :)
    iterations = int(timeout / ENVOY_POLL_INTERVAL_S)
    n = 0

    for n in range(iterations):
        # If we are asking to up a service on a machine that has the "all"
        # service downed, return a success providing that the service itself
        # is healthy
        if expected_state == 'up':
            try:
                with open(os.devnull, 'w') as devnull:
                    subprocess.check_call(
                        ['/usr/bin/hastatus', 'all'], stdout=devnull
                    )
            except Exception:
                if check_local_healthcheck(service):
                    return 0

        if check_envoy_state(service, expected_state, envoy_eds_dir):
            print('{0}Service entered state \'{1}\''.format(
                '\n' if n > 0 else '', expected_state))
            print('Sleeping for an additional {0}s'.format(wait_time))
            time.sleep(wait_time)
            return 0

        sys.stdout.write('.')
        sys.stdout.flush()

        time.sleep(ENVOY_POLL_INTERVAL_S)
    else:
        print('{0}Service failed to enter state \'{1}\''.format(
            '\n' if n > 0 else '', expected_state))
        if expected_state == 'up':
            print('*** Please manually check your service\'s healthcheck endpoint. ***')
            print('*** If your service is healthy, then please talk to #paasta. ***')
        return 1


def _should_manage_service(
    service_name: str,
) -> bool:
    srv_name, namespace = service_name.split('.')
    service_config = load_service_namespace_config(srv_name, namespace)
    classic_config = read_service_configuration(srv_name)

    # None is a valid value of proxy_port indicating a discovery only service
    should_manage = service_config.get('proxy_port', -1) != -1
    blacklisted = classic_config.get('no_updown_service')

    return (should_manage and not blacklisted)


def _get_timeout_s(
    service_name: str,
    timeout: int,
) -> int:
    if timeout is not None:
        return timeout

    srv_name, namespace = service_name.split('.')
    namespace_configuration = load_service_namespace_config(srv_name, namespace)
    timeout_s = namespace_configuration.get('updown_timeout_s', DEFAULT_TIMEOUT_S)
    return timeout_s


def main() -> None:
    args = get_args()
    should_check = _should_manage_service(args.service)
    timeout_s = _get_timeout_s(args.service, args.timeout)

    if not should_check:
        print('{0} is not available in the service mesh, doing nothing'.format(
            args.service
        ))
        sys.exit(0)

    if not args.wait_only:
        reconfigure_hacheck(args.service, args.state, args.port)

    result = 0
    if args.envoy_eds_dir:
        result = wait_for_envoy_state(
            service=args.service,
            expected_state=args.state,
            timeout=timeout_s,
            wait_time=args.wait_time,
            envoy_eds_dir=args.envoy_eds_dir,
        )
    sys.exit(result)


if __name__ == '__main__':
    main()
