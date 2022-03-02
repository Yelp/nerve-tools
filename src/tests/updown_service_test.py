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
