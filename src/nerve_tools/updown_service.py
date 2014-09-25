# Utility to change local SmartStack service state

import csv
import os
import socket
import subprocess
import sys
import time
import urllib2

import argparse


# Maximum amount of time to run before returning
DEFAULT_TIMEOUT_S = 300

# Even though a service has entered the expected state in our local HAProxy
# instance, there may still be a short delay before all remote HAProxy instances
# also pick up this change.  So we add an additional delay before returning.
DEFAULT_WAIT_TIME_S = 1

STATE_DIR = '/var/spool/healthcheck_state'

CONFIGURE_NERVE = '/usr/bin/configure_nerve'

HAPROXY_STATUS_URL = 'http://169.254.255.254:3212/;csv'
HAPROXY_QUERY_TIMEOUT_S = 1
HAPROXY_POLL_INTERVAL_S = 1


def service_name(service):
    if not len(service.split('.')) == 2:
        msg = "Namespace missing from service name"
        raise argparse.ArgumentTypeError(msg)
    return service


def get_args():
    description = "Control service state in load balancers"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-t", "--timeout", default=DEFAULT_TIMEOUT_S, type=int,
                        help="maximum time to wait for <state> (default: %default)")
    parser.add_argument("-w", "--wait-time", default=DEFAULT_WAIT_TIME_S, type=int,
                        help="additional time to wait for convergence (default: %default)")
    parser.add_argument("service", type=service_name,
                        help="service name, including namespace e.g. 'geocoder.main'")
    parser.add_argument("state", choices=['up', 'down'], help="desired state")
    args = parser.parse_args()
    return args


def write_local_state_file(service, state):
    state_file = os.path.join(STATE_DIR, service)
    with open(state_file, 'w') as fd:
        fd.write(state)


def reconfigure_nerve():
    """Restart nerve to pick up any changes in the STATE_DIR.

    Nerve bypasses the healthcheck service and instead directly healthchecks
    services; changes to service state files are only detected upon
    reconfiguration of nerve.  A cron job reconfigures nerve every minute,
    but we'd like to detect state changes more quickly, so here we eagerly
    reconfigure nerve.
    """
    subprocess.check_call([CONFIGURE_NERVE])


def get_my_ip_address():
    return socket.gethostbyname(socket.getfqdn())


def check_haproxy_state(service, expected_state):
    """If the expected_state is 'up', then return 'true' iff the local service
    instance is 'up' in HAProxy.

    If the expected_state is 'down', then return 'true' iff the local service
    instance is NOT 'up' in HAProxy (could be 'down', 'maint' or missing).

    Note that this requires synapse to be running on localhost.
    """

    try:
        fd = urllib2.urlopen(HAPROXY_STATUS_URL, timeout=HAPROXY_QUERY_TIMEOUT_S)
    except:
        # Allow for transient errors when querying HAProxy
        return False

    my_ip_address = get_my_ip_address()
    reader = csv.DictReader(fd, delimiter=',')
    for line in reader:
        if line['# pxname'] != service:
            continue
        if not '%s:' % my_ip_address in line['svname']:
            continue

        # We found our service.  Let's check whether it has the correct state
        actual_state = line['status'].lower()

        expected_up = expected_state == 'up'
        actual_up = actual_state.startswith('up')

        return (expected_up and actual_up) or (not expected_up and not actual_up)

    # We did not find our service.
    return expected_state != 'up'


def wait_for_haproxy_state(service, expected_state, timeout, wait_time):
    """Wait for the specified service to enter the given state in HAProxy."""

    # This isn't precise, but it's easy to test :)
    iterations = timeout / HAPROXY_POLL_INTERVAL_S

    for n in xrange(iterations):
        if check_haproxy_state(service, expected_state):
            print '{0}Service entered state \'{1}\''.format(
                '\n' if n > 0 else '', expected_state)
            print 'Sleeping for an additional {0}s'.format(wait_time)
            time.sleep(wait_time)
            return 0

        sys.stdout.write('.')
        sys.stdout.flush()

        time.sleep(HAPROXY_POLL_INTERVAL_S)
    else:
        print '{0}Service failed to enter state \'{1}\''.format(
            '\n' if n > 0 else '', expected_state)
        return 1


def main():
    args = get_args()
    write_local_state_file(args.service, args.state)
    reconfigure_nerve()
    result = wait_for_haproxy_state(
        args.service, args.state, args.timeout, args.wait_time)
    sys.exit(result)


if __name__ == '__main__':
    main()
