from mock import patch

from nerve_tools.envoy import get_envoy_ingress_listeners


def test_get_envoy_ingress_listeners_success():
    expected_envoy_listeners = {
        ('test_service.main', '10.45.13.4', 1234): 54321,
    }
    mock_envoy_admin_listeners_return_value = {
        'listener_statuses': [
            {
                'name': 'test_service.main.10.45.13.4.1234.ingress_listener',
                'local_address': {
                    'socket_address': {
                        'address': '0.0.0.0',
                        'port_value': 54321,
                    },
                },
            },
        ],
    }
    with patch(
        'nerve_tools.envoy._get_envoy_listeners_from_admin',
        return_value=mock_envoy_admin_listeners_return_value,
    ):
        assert get_envoy_ingress_listeners(123) == expected_envoy_listeners


def test_get_envoy_ingress_listeners_failure():
    with patch(
        'nerve_tools.envoy.requests.get',
        side_effect=Exception,
    ):
        assert get_envoy_ingress_listeners(123) == {}
