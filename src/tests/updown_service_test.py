import contextlib
import os

import mock
import pytest

from nerve_tools import updown_service


def test_get_args_pass():
    tests = [
        [['updown_service', 'myservice.name', 'up'], 'up', 300],
        [['updown_service', 'myservice.name', 'down'], 'down', 300],
        [['updown_service', 'myservice.name', 'down', '-t', '42'], 'down', 42],
    ]

    for test in tests:
        argv, expected_state, expected_timeout = test

        with mock.patch('sys.argv', argv):
            args = updown_service.get_args()

        assert args.service == 'myservice.name'
        assert args.state == expected_state
        assert args.timeout == expected_timeout


def test_get_args_fail():
    tests = [
        ['updown_service'],
        ['updown_service', 'myservice.name'],
        ['updown_service', 'myservice', 'up'],
        ['updown_service', 'myservice.name', 'wibble'],
    ]

    for argv in tests:
        with mock.patch('sys.argv', argv):
            with pytest.raises(SystemExit) as excinfo:
                updown_service.get_args()
            assert str(excinfo.value) == '2', argv


def test_check_haproxy_state():
    tests = [
        # Up
        ['10.0.0.1', 'up', True],
        ['10.0.0.1', 'down', False],
        # Down
        ['10.0.0.2', 'up', False],
        ['10.0.0.2', 'down', True],
        # Maintenance
        ['10.0.0.3', 'up', False],
        ['10.0.0.3', 'down', True],
        # Missing
        ['10.0.0.4', 'up', False],
        ['10.0.0.4', 'down', True],
    ]

    mock_stats_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'haproxy_stats.csv')

    for test in tests:
        my_ip_address, expected_state, expected_result = test

        with open(mock_stats_path) as fd:
            with contextlib.nested(
                    mock.patch('urllib2.urlopen', return_value=fd),
                    mock.patch('nerve_tools.updown_service.get_my_ip_address',
                               return_value=my_ip_address)):
                actual_result = updown_service.check_haproxy_state(
                    'location_suggest.main', expected_state)

        assert actual_result == expected_result, test


def test_unknown_service():
    mock_stats_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'haproxy_stats.csv')

    with open(mock_stats_path) as fd:
        with contextlib.nested(
                mock.patch('urllib2.urlopen', return_value=fd),
                mock.patch('nerve_tools.updown_service.get_my_ip_address',
                           return_value='127.0.0.1'),
                mock.patch('sys.exit')) as (_, _, mock_exit):
            updown_service.check_haproxy_state('unknown_service', True)
            mock_exit.assert_called_once_with(1)


def test_wait_for_haproxy_state():
    tests = [
        # Service is immediately in the expected state
        [[True], 0, 1],
        # Service never enters the expected state
        [10 * [False], 1, 10],
        # Service enters the expected state on third poll
        [[False, False, True], 0, 3],
    ]

    for test in tests:
        mock_check_haproxy_state, expected_result, expected_mock_sleep_call_count = test

        with contextlib.nested(
                mock.patch('time.sleep'),
                mock.patch('subprocess.check_call'),
                mock.patch('nerve_tools.updown_service.check_haproxy_state',
                           side_effect=mock_check_haproxy_state)) as (mock_sleep, _, _):
            actual_result = updown_service.wait_for_haproxy_state(
                'location_suggest.main', 'down', 10, 1)

        assert expected_result == actual_result
        assert mock_sleep.call_count == expected_mock_sleep_call_count


def test_should_manage_service():
    mconfig_path = 'nerve_tools.updown_service.load_service_namespace_config'
    mconfig = mock.Mock(return_value={'proxy_port': 3})

    sconfig_path = 'nerve_tools.updown_service.read_service_configuration'
    with contextlib.nested(
            mock.patch(mconfig_path, new=mconfig),
            mock.patch(sconfig_path, return_value={})):
        assert updown_service._should_manage_service('test.main')

    with contextlib.nested(
            mock.patch(mconfig_path, new=mconfig),
            mock.patch(sconfig_path, return_value={'no_updown_service': True})):
        assert not updown_service._should_manage_service('test.main')

    mconfig.return_value = {}
    with contextlib.nested(
            mock.patch(mconfig_path, new=mconfig),
            mock.patch(sconfig_path, return_value={})):
        assert not updown_service._should_manage_service('test.main')
