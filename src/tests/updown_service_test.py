import os

import mock
import pytest
from requests.exceptions import RequestException

from nerve_tools import updown_service


def test_get_args_pass():
    tests = [
        [['updown_service', 'myservice.name', 'up'], 'up', None, 300, False, None],
        [['updown_service', 'myservice.name', 'down'], 'down', None, 300, False, None],
        [['updown_service', 'myservice.name', 'down', '-t', '42'], 'down', 42, 42, False, None],
        [['updown_service', 'myservice.name', 'down', '-x'], 'down', None, 300, True, None],
        [['updown_service', 'myservice.name:1234', 'down', '-x'], 'down', None, 300, True, 1234],
    ]

    for test in tests:
        (
            argv, expected_state, expected_args_timeout,
            expected_timeout, expected_wait_only, expected_port
        ) = test

        with mock.patch('sys.argv', argv):
            args = updown_service.get_args()
            timeout = updown_service._get_timeout_s(args.service, args.timeout)

        assert args.service == 'myservice.name'
        assert args.state == expected_state
        assert args.timeout == expected_args_timeout
        assert timeout == expected_timeout
        assert args.wait_only == expected_wait_only
        assert args.port == expected_port


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

        with open(mock_stats_path, 'rb') as fd:
            with mock.patch(
                'urllib.request.urlopen', return_value=fd
            ), mock.patch(
                'nerve_tools.updown_service.get_my_ip_address',
                return_value=my_ip_address
            ):
                actual_result = updown_service.check_haproxy_state(
                    'service_three.main', expected_state)

        assert actual_result == expected_result, test


def test_wait_for_haproxy_with_healthcheck_pass_returns_zero():
    mock_stats_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'haproxy_stats.csv')
    with open(mock_stats_path, 'rb') as fd:
        with mock.patch(
            'urllib.request.urlopen', return_value=fd
        ), mock.patch(
            'subprocess.check_call', side_effect=Exception()
        ), mock.patch(
            'nerve_tools.updown_service.check_local_healthcheck',
            return_value=True
        ):
            assert 0 == updown_service.wait_for_haproxy_state(
                'service_three.main', 'up', 10, 1)


def test_wait_for_haproxy_with_healthcheck_fail_returns_one():
    mock_stats_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'haproxy_stats.csv')

    with mock.patch(
        'urllib.request.urlopen',
        side_effect=lambda _, timeout: open(mock_stats_path, 'rb')
    ), mock.patch(
        'time.sleep'
    ), mock.patch(
        'subprocess.check_call',
        side_effect=Exception()
    ), mock.patch(
        'nerve_tools.updown_service.check_local_healthcheck',
        return_value=False
    ):
        assert 1 == updown_service.wait_for_haproxy_state(
            'service_three.main', 'up', 10, 1)


def test_check_local_healthcheck_returns_true_on_success():
    with mock.patch(
        'nerve_tools.updown_service.read_service_configuration',
        return_value={'port': 1010}
    ), mock.patch(
        'requests.get',
        return_value=mock.Mock()
    ) as mock_http:
        assert updown_service.check_local_healthcheck(
            'service_three.main')
        mock_http.assert_called_once_with('http://127.0.0.1:1010/status')


def test_check_local_healthcheck_returns_false_on_failure():
    mock_get = mock.Mock(
        raise_for_status=mock.Mock(side_effect=RequestException()))
    with mock.patch(
        'nerve_tools.updown_service.read_service_configuration',
        return_value={'port': 1010}
    ), mock.patch(
        'requests.get',
        return_value=mock_get
    ) as mock_http:
        assert not updown_service.check_local_healthcheck(
            'service_three.main')
        mock_http.assert_called_once_with('http://127.0.0.1:1010/status')


def test_unknown_service():
    mock_stats_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'haproxy_stats.csv')

    with open(mock_stats_path, 'rb') as fd:
        with mock.patch(
            'urllib.request.urlopen',
            return_value=fd
        ), mock.patch(
            'nerve_tools.updown_service.get_my_ip_address',
            return_value='127.0.0.1'
        ), mock.patch(
            'sys.exit'
        ) as mock_exit:
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

        with mock.patch(
            'time.sleep'
        ) as mock_sleep, mock.patch(
            'subprocess.check_call'
        ), mock.patch(
            'nerve_tools.updown_service.check_haproxy_state',
            side_effect=mock_check_haproxy_state,
        ):
            actual_result = updown_service.wait_for_haproxy_state(
                'service_three.main', 'down', 10, 1)

        assert expected_result == actual_result
        assert mock_sleep.call_count == expected_mock_sleep_call_count


def test_wait_for_haproxy_state_handles_timeout_0():
    actual_result = updown_service.wait_for_haproxy_state(
        service='service_three.main',
        expected_state='down',
        timeout=0,
        wait_time=1)
    assert actual_result == 1


def test_should_manage_service():
    mconfig_path = 'nerve_tools.updown_service.load_service_namespace_config'
    mconfig = mock.Mock(return_value={'proxy_port': 3})
    mconfig_discovery_only = mock.Mock(return_value={'proxy_port': None})

    sconfig_path = 'nerve_tools.updown_service.read_service_configuration'
    with mock.patch(
        mconfig_path, new=mconfig
    ), mock.patch(
        sconfig_path, return_value={}
    ):
        assert updown_service._should_manage_service('test.main')

    with mock.patch(
        mconfig_path, new=mconfig_discovery_only
    ), mock.patch(
        sconfig_path, return_value={}
    ):
        assert updown_service._should_manage_service('test.main')

    with mock.patch(
        mconfig_path, new=mconfig
    ), mock.patch(
        sconfig_path, return_value={'no_updown_service': True}
    ):
        assert not updown_service._should_manage_service('test.main')

    mconfig.return_value = {}
    with mock.patch(
        mconfig_path, new=mconfig
    ), mock.patch(
        sconfig_path, return_value={}
    ):
        assert not updown_service._should_manage_service('test.main')


def test_timeout_s():
    arg_timeout_s = 30
    new_timeout_s = 50
    mconfig_path = 'nerve_tools.updown_service.load_service_namespace_config'

    mconfig = mock.Mock(return_value={})
    with mock.patch(mconfig_path, new=mconfig):
        assert updown_service._get_timeout_s('test.main', arg_timeout_s) == arg_timeout_s

    mconfig = mock.Mock(return_value={})
    with mock.patch(mconfig_path, new=mconfig):
        assert updown_service._get_timeout_s('test.main', None) == updown_service.DEFAULT_TIMEOUT_S

    mconfig = mock.Mock(return_value={'updown_timeout_s': new_timeout_s})
    with mock.patch(mconfig_path, new=mconfig):
        assert updown_service._get_timeout_s('test.main', arg_timeout_s) == arg_timeout_s

    mconfig = mock.Mock(return_value={'updown_timeout_s': new_timeout_s})
    with mock.patch(mconfig_path, new=mconfig):
        assert updown_service._get_timeout_s('test.main', None) == new_timeout_s


def test_reconfigure_hacheck():
    with mock.patch('subprocess.check_call') as check_call:
        updown_service.reconfigure_hacheck('test.main', 'down', None)
        updown_service.reconfigure_hacheck('test.main', 'down', 1234)
        updown_service.reconfigure_hacheck('test.main', 'up', None)
        updown_service.reconfigure_hacheck('test.main', 'up', 1337)

        expected_calls = [
            mock.call(['/usr/bin/hadown', 'test.main']),
            mock.call(['/usr/bin/hadown', 'test.main', '-P', '1234']),
            mock.call(['/usr/bin/haup', 'test.main']),
            mock.call(['/usr/bin/haup', 'test.main', '-P', '1337']),
        ]
        assert check_call.call_args_list == expected_calls
