import copy
import mock
from mock import call
from mock import patch
from mock import mock_open
from mock import MagicMock
from mock import Mock
import pytest
import sys
import multiprocessing
from contextlib import contextmanager

from typing import List

from nerve_tools import configure_nerve
from nerve_tools.configure_nerve import generate_configuration
from nerve_tools.configure_nerve import generate_subconfiguration


try:
    CPUS = max(multiprocessing.cpu_count(), 10)
except NotImplementedError:
    CPUS = 10


def test_get_named_zookeeper_topology():
    m = mock_open()
    with patch(
        'nerve_tools.configure_nerve.open',
        m, create=True
    ), patch(
        'yaml.load', return_value=[['foo', 42]]
    ):
        zk_topology = configure_nerve.get_named_zookeeper_topology(
            'test-type', 'test-location', '/fake/path/'
        )
    assert zk_topology == ['foo:42']
    m.assert_called_with(
        '/fake/path/test-type/test-location.yaml'
    )


def get_labels_by_service_and_port(service: str, port: int, labels_dir):
    if (service, port) == ('test_service', 1234):
        return {'label1': 'value1', 'label2': 'value2'}
    else:
        return {}


def get_current_location(typ: str) -> str:
    return {
        'ecosystem': 'my_ecosystem',
        'superregion': 'my_superregion',
        'habitat': 'my_habitat',
        'region': 'my_region',
    }[typ]


def convert_location_type(src_loc: str, src_typ: str, dst_typ: str) -> List[str]:
    if src_typ == dst_typ:
        return [src_loc]
    return {
        ('my_superregion', 'superregion', 'superregion'): ['my_superregion'],
        ('another_superregion', 'superregion', 'region'): ['another_region'],
        ('my_region', 'region', 'superregion'): ['my_superregion'],
        ('another_region', 'region', 'region'): ['another_region'],
        ('another_region', 'region', 'superregion'): ['another_superregion'],
    }[(src_loc, src_typ, dst_typ)]


def get_named_zookeeper_topology(cluster_type, cluster_location, zk_topology_dir):
    return {
        ('infrastructure', 'my_superregion'): ['1.2.3.4', '2.3.4.5'],
        ('infrastructure', 'another_superregion'): ['3.4.5.6', '4.5.6.7']
    }[(cluster_type, cluster_location)]


@pytest.fixture
def expected_sub_config():
    expected_config = {
        'test_service.my_superregion:10.0.0.1.1234.v2.new': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/smartstack/global/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/1234/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'open_timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666,
                'headers': {},
            }],
            'host': '10.0.0.1',
            'check_interval': 3.0,
            'port': 1234,
            'weight': mock.sentinel.weight,
            'labels': {
                'label1': 'value1',
                'label2': 'value2',
                'superregion:my_superregion': '',
                'region:my_region': '',
                'deploy_group': 'prod.canary',
                'paasta_instance': 'canary',
            },
        },
        'test_service.another_superregion:10.0.0.1.1234.v2.new': {
            'zk_hosts': ['3.4.5.6', '4.5.6.7'],
            'zk_path': '/smartstack/global/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/1234/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'open_timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666,
                'headers': {},
            }],
            'host': '10.0.0.1',
            'check_interval': 3.0,
            'port': 1234,
            'weight': mock.sentinel.weight,
            'labels': {
                'label1': 'value1',
                'label2': 'value2',
                'region:another_region': '',
                'deploy_group': 'prod.canary',
                'paasta_instance': 'canary',
            },
        },
    }
    return expected_config


@pytest.fixture
def expected_sub_config_with_envoy_ingress_listeners(expected_sub_config):

    # Convert smartstack mesos services to smartstack k8s services
    for k, v in expected_sub_config.items():
        expected_sub_config[k]['host'] = '10.4.5.6'

    new_expected_sub_config = {}
    for k, v in expected_sub_config.items():
        new_expected_sub_config[k.replace('10.0.0.1', '10.4.5.6')] = expected_sub_config[k]

    # Add in full mesh envoy configs for the same service
    new_expected_sub_config.update({
        'test_service.my_superregion:10.4.5.6.1234': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/envoy/global/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/https/test_service/35000/status',
                'host': '10.0.0.1',
                'timeout': 2.0,
                'open_timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666,
                'headers': {'Host': 'test_service'},
            }],
            'host': '10.0.0.1',
            'check_interval': 3.0,
            'port': 35000,
            'weight': mock.sentinel.weight,
            'labels': {
                'label1': 'value1',
                'label2': 'value2',
                'superregion:my_superregion': '',
                'region:my_region': '',
                'deploy_group': 'prod.canary',
                'paasta_instance': 'canary',
            },
        },
        'test_service.another_superregion:10.4.5.6.1234': {
            'zk_hosts': ['3.4.5.6', '4.5.6.7'],
            'zk_path': '/envoy/global/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/https/test_service/35000/status',
                'host': '10.0.0.1',
                'timeout': 2.0,
                'open_timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666,
                'headers': {'Host': 'test_service'},
            }],
            'host': '10.0.0.1',
            'check_interval': 3.0,
            'port': 35000,
            'weight': mock.sentinel.weight,
            'labels': {
                'label1': 'value1',
                'label2': 'value2',
                'region:another_region': '',
                'deploy_group': 'prod.canary',
                'paasta_instance': 'canary',
            },
        },
    })
    return new_expected_sub_config


def test_generate_subconfiguration(expected_sub_config):
    with patch(
        'nerve_tools.configure_nerve.get_current_location',
        side_effect=get_current_location
    ), patch(
        'nerve_tools.configure_nerve.convert_location_type',
        side_effect=convert_location_type
    ), patch(
        'nerve_tools.configure_nerve.get_named_zookeeper_topology',
        side_effect=get_named_zookeeper_topology
    ), patch(
        'nerve_tools.configure_nerve.get_labels_by_service_and_port',
        side_effect=get_labels_by_service_and_port
    ):

        mock_service_info = {
            'port': 1234,
            'routes': [('remote_location', 'local_location')],
            'healthcheck_timeout_s': 2.0,
            'healthcheck_mode': 'http',
            'healthcheck_port': 1234,
            'advertise': ['region', 'superregion'],
            'extra_advertise': [
                ('habitat:my_habitat', 'region:another_region'),
                ('habitat:your_habitat', 'region:another_region'),  # Ignored
            ],
            'deploy_group': 'prod.canary',
            'paasta_instance': 'canary',
        }

        actual_config = configure_nerve.generate_subconfiguration(
            service_name='test_service',
            service_info=mock_service_info,
            host_ip='10.0.0.1',
            hacheck_port=6666,
            weight=mock.sentinel.weight,
            zk_topology_dir='/fake/path',
            zk_location_type='superregion',
            zk_cluster_type='infrastructure',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert expected_sub_config == actual_config


def test_generate_subconfiguration_k8s(expected_sub_config):
    with patch(
        'nerve_tools.configure_nerve.get_current_location',
        side_effect=get_current_location
    ), patch(
        'nerve_tools.configure_nerve.convert_location_type',
        side_effect=convert_location_type
    ), patch(
        'nerve_tools.configure_nerve.get_named_zookeeper_topology',
        side_effect=get_named_zookeeper_topology
    ), patch(
        'nerve_tools.configure_nerve.get_labels_by_service_and_port',
        side_effect=get_labels_by_service_and_port
    ):

        for k, v in expected_sub_config.items():
            expected_sub_config[k]['host'] = '10.4.5.6'
            for check in expected_sub_config[k]['checks']:
                check['host'] = '10.1.2.3'
        new_expected_sub_config = {}
        for k, v in expected_sub_config.items():
            new_expected_sub_config[k.replace('10.0.0.1', '10.4.5.6')] = expected_sub_config[k]

        mock_service_info = {
            'port': 1234,
            'routes': [('remote_location', 'local_location')],
            'healthcheck_timeout_s': 2.0,
            'healthcheck_mode': 'http',
            'healthcheck_port': 1234,
            'hacheck_ip': '10.1.2.3',
            'service_ip': '10.4.5.6',
            'advertise': ['region', 'superregion'],
            'extra_advertise': [
                ('habitat:my_habitat', 'region:another_region'),
                ('habitat:your_habitat', 'region:another_region'),  # Ignored
            ],
            'deploy_group': 'prod.canary',
            'paasta_instance': 'canary',
        }

        actual_config = configure_nerve.generate_subconfiguration(
            service_name='test_service',
            service_info=mock_service_info,
            host_ip='10.4.5.6',
            hacheck_port=6666,
            weight=mock.sentinel.weight,
            zk_topology_dir='/fake/path',
            zk_location_type='superregion',
            zk_cluster_type='infrastructure',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert new_expected_sub_config == actual_config


def test_generate_subconfiguration_with_envoy_ingress_listeners(
    expected_sub_config_with_envoy_ingress_listeners
):
    with patch(
        'nerve_tools.configure_nerve.get_current_location',
        side_effect=get_current_location
    ), patch(
        'nerve_tools.configure_nerve.convert_location_type',
        side_effect=convert_location_type
    ), patch(
        'nerve_tools.configure_nerve.get_named_zookeeper_topology',
        side_effect=get_named_zookeeper_topology
    ), patch(
        'nerve_tools.configure_nerve.get_labels_by_service_and_port',
        side_effect=get_labels_by_service_and_port
    ), patch(
        'nerve_tools.configure_nerve.get_host_ip',
        return_value='10.0.0.1',
    ), patch(
        'nerve_tools.envoy.get_host_ip',
        return_value='10.0.0.1',
    ):
        mock_service_info = {
            'port': 1234,
            'routes': [('remote_location', 'local_location')],
            'healthcheck_timeout_s': 2.0,
            'healthcheck_mode': 'http',
            'healthcheck_port': 1234,
            'advertise': ['region', 'superregion'],
            'extra_advertise': [
                ('habitat:my_habitat', 'region:another_region'),
                ('habitat:your_habitat', 'region:another_region'),  # Ignored
            ],
            'deploy_group': 'prod.canary',
            'paasta_instance': 'canary',
            'service_ip': '10.4.5.6',
        }
        mock_envoy_service_info = copy.deepcopy(mock_service_info)
        mock_envoy_service_info.update({
            'port': 35000,
            'healthcheck_port': 35000,
            'extra_healthcheck_headers': {'Host': 'test_service'},
        })

        actual_config = generate_subconfiguration(
            service_name='test_service',
            service_info=mock_service_info,
            host_ip='10.0.0.1',
            hacheck_port=6666,
            weight=mock.sentinel.weight,
            zk_topology_dir='/fake/path',
            zk_location_type='superregion',
            zk_cluster_type='infrastructure',
            labels_dir='/dev/null',
            envoy_service_info=mock_envoy_service_info,
        )

    assert expected_sub_config_with_envoy_ingress_listeners == actual_config


def test_generate_configuration_paasta_service():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with patch(
        'nerve_tools.configure_nerve.get_host_ip',
        return_value='ip_address'
    ), patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), patch(
        'nerve_tools.configure_nerve.generate_subconfiguration',
        return_value={'foo': 17}
    ) as mock_generate_subconfiguration:

        mock_service_info = {
            'port': 1234,
            'healthcheck_timeout_s': 2.0,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        actual_config = configure_nerve.generate_configuration(
            paasta_services=[(
                'test_service',
                mock_service_info,
            )],
            puppet_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_ingress_listeners={},
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            host_ip='ip_address',
            hacheck_port=6666,
            weight=10,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert expected_config == actual_config


def test_generate_configuration_paasta_service_with_envoy_ingress_listeners():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with patch(
        'nerve_tools.configure_nerve.get_host_ip',
        return_value='ip_address',
    ), patch(
        'nerve_tools.envoy.get_host_ip',
        return_value='ip_address',
    ), patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host',
    ), patch(
        'nerve_tools.configure_nerve.generate_subconfiguration',
        return_value={'foo': 17}
    ) as mock_generate_subconfiguration:

        mock_service_info = {
            'port': 1234,
            'healthcheck_timeout_s': 2.0,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        envoy_ingress_listeners = {1234: 35001}
        mock_envoy_service_main_info = copy.deepcopy(mock_service_info)
        mock_envoy_service_main_info.update({
            'host': 'ip_address',
            'port': 35001,
            'healthcheck_port': 35001,
            'extra_healthcheck_headers': {'Host': 'test_service.main'},
        })
        mock_envoy_service_alt_info = copy.deepcopy(mock_service_info)
        mock_envoy_service_alt_info.update({
            'host': 'ip_address',
            'port': 35001,
            'healthcheck_port': 35001,
            'extra_healthcheck_headers': {'Host': 'test_service.alt'},
        })

        actual_config = generate_configuration(
            paasta_services=[
                (
                    'test_service.main',
                    mock_service_info,
                ),
                (
                    'test_service.alt',
                    mock_service_info,
                )
            ],
            puppet_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_ingress_listeners=envoy_ingress_listeners,
        )

        mock_generate_subconfiguration.assert_has_calls([
            call(
                service_name='test_service.main',
                service_info=mock_service_info,
                host_ip='ip_address',
                hacheck_port=6666,
                weight=10,
                zk_topology_dir='/fake/path',
                zk_location_type='fake_zk_location_type',
                zk_cluster_type='fake_cluster_type',
                labels_dir='/dev/null',
                envoy_service_info=mock_envoy_service_main_info,
            ),
            call(
                service_name='test_service.alt',
                service_info=mock_service_info,
                host_ip='ip_address',
                hacheck_port=6666,
                weight=10,
                zk_topology_dir='/fake/path',
                zk_location_type='fake_zk_location_type',
                zk_cluster_type='fake_cluster_type',
                labels_dir='/dev/null',
                envoy_service_info=mock_envoy_service_alt_info,
            )
        ])

    assert expected_config == actual_config


def test_generate_configuration_healthcheck_port():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with patch(
        'nerve_tools.configure_nerve.get_host_ip',
        return_value='ip_address'
    ), patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), patch(
        'nerve_tools.configure_nerve.generate_subconfiguration',
        return_value={'foo': 17}
    ) as mock_generate_subconfiguration:

        mock_service_info = {
            'port': 1234,
            'routes': [('remote_location', 'local_location')],
            'healthcheck_timeout_s': 2.0,
            'healthcheck_port': 7890,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        actual_config = configure_nerve.generate_configuration(
            paasta_services=[(
                'test_service',
                mock_service_info,
            )],
            puppet_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_ingress_listeners={},
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            host_ip='ip_address',
            hacheck_port=6666,
            weight=10,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert expected_config == actual_config


def test_generate_configuration_healthcheck_mode():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with patch(
        'nerve_tools.configure_nerve.get_host_ip',
        return_value='ip_address'
    ), patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), patch(
        'nerve_tools.configure_nerve.generate_subconfiguration',
        return_value={'foo': 17}
    ) as mock_generate_subconfiguration:

        mock_service_info = {
            'port': 1234,
            'routes': [('remote_location', 'local_location')],
            'healthcheck_timeout_s': 2.0,
            'healthcheck_mode': 'tcp',
            'healthcheck_port': 7890,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        actual_config = configure_nerve.generate_configuration(
            paasta_services=[(
                'test_service',
                mock_service_info,
            )],
            puppet_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_ingress_listeners={},
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            host_ip='ip_address',
            hacheck_port=6666,
            weight=10,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert expected_config == actual_config


def test_generate_configuration_empty():
    with patch(
        'nerve_tools.configure_nerve.get_host_ip',
        return_value='ip_address'
    ), patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ):

        configuration = configure_nerve.generate_configuration(
            paasta_services=[],
            puppet_services=[],
            heartbeat_path="",
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_ingress_listeners={},
        )
        assert configuration == {'instance_id': 'my_host', 'services': {}, 'heartbeat_path': ''}


@contextmanager
def setup_mocks_for_main():
    mock_sys = MagicMock()
    mock_file_cmp = Mock()
    mock_move = Mock()
    mock_subprocess_call = Mock()
    mock_subprocess_check_call = Mock()
    mock_sleep = Mock()
    mock_file_not_modified = Mock(return_value=False)

    with patch.object(
        sys, 'argv', ['configure-nerve']
    ) as mock_sys, patch(
        'nerve_tools.configure_nerve.get_marathon_services_running_here_for_nerve'
    ), patch(
        'nerve_tools.configure_nerve.get_paasta_native_services_running_here_for_nerve'
    ), patch(
        'nerve_tools.configure_nerve.generate_configuration'
    ), patch(
        'nerve_tools.configure_nerve.open', create=True
    ), patch(
        'json.dump'
    ), patch(
        'os.chmod'
    ), patch(
        'filecmp.cmp'
    ) as mock_file_cmp, patch(
        'shutil.move'
    ) as mock_move, patch(
        'subprocess.call'
    ) as mock_subprocess_call, patch(
        'subprocess.check_call'
    ) as mock_subprocess_check_call, patch(
        'time.sleep'
    ) as mock_sleep, patch(
        'nerve_tools.configure_nerve.file_not_modified_since', return_value=False
    ) as mock_file_not_modified:
        mocks = (
            mock_sys, mock_file_cmp, mock_move,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified
        )
        yield mocks


def test_file_not_modified_since():
    fake_threshold = 10
    fake_path = '/somepath'
    with patch(
        'time.time'
    ) as mock_time, patch(
        'os.path.isfile', return_value=True
    ), patch(
        'os.path.getmtime',
    ) as mock_getmtime:

        mock_time.return_value = 10.0
        mock_getmtime.return_value = mock_time.return_value + fake_threshold + 1
        print(configure_nerve.file_not_modified_since(fake_path, fake_threshold))


def test_nerve_restarted_when_config_files_differ():
    with setup_mocks_for_main() as (
            mock_sys, mock_file_cmp, mock_move,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs differ
        mock_file_cmp.return_value = False
        configure_nerve.main()

        expected_move = call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_calls = (
            call(['service', 'nerve-backup', 'start']),
            call(['service', 'nerve-backup', 'stop']),
        )
        expected_subprocess_check_calls = (
            call(['service', 'nerve', 'start']),
            call(['service', 'nerve', 'stop']),
            call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
        )

        actual_subprocess_calls = mock_subprocess_call.call_args_list
        actual_subprocess_check_calls = mock_subprocess_check_call.call_args_list

        assert len(expected_subprocess_calls) == len(actual_subprocess_calls)
        assert len(expected_subprocess_check_calls) == len(actual_subprocess_check_calls)
        assert all(
            [i in actual_subprocess_calls for i in expected_subprocess_calls]
        )
        assert all(
            [i in actual_subprocess_check_calls for i in expected_subprocess_check_calls]
        )

        mock_sleep.assert_called_with(30)


def test_nerve_not_restarted_when_configs_files_are_identical():
    with setup_mocks_for_main() as (
            mock_sys, mock_file_cmp, mock_move,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True
        configure_nerve.main()

        expected_move = call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_check_calls = [
            call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
        ]

        actual_subprocess_calls = mock_subprocess_call.call_args_list
        actual_subprocess_check_calls = mock_subprocess_check_call.call_args_list

        assert len(actual_subprocess_calls) == 0
        assert expected_subprocess_check_calls == actual_subprocess_check_calls
        assert not mock_sleep.called


def test_nerve_restarted_when_heartbeat_file_stale():
    with setup_mocks_for_main() as (
            mock_sys, mock_file_cmp, mock_move,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True
        mock_file_not_modified.return_value = True
        configure_nerve.main()

        expected_move = call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_calls = (
            call(['service', 'nerve-backup', 'start']),
            call(['service', 'nerve-backup', 'stop']),
        )
        expected_subprocess_check_calls = (
            call(['service', 'nerve', 'start']),
            call(['service', 'nerve', 'stop']),
            call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
        )

        actual_subprocess_calls = mock_subprocess_call.call_args_list
        actual_subprocess_check_calls = mock_subprocess_check_call.call_args_list

        assert len(expected_subprocess_calls) == len(actual_subprocess_calls)
        assert len(expected_subprocess_check_calls) == len(actual_subprocess_check_calls)
        assert all(
            [i in actual_subprocess_calls for i in expected_subprocess_calls]
        )
        assert all(
            [i in actual_subprocess_check_calls for i in expected_subprocess_check_calls]
        )

        mock_sleep.assert_called_with(30)


def test_nerve_not_restarted_when_heartbeat_file_valid():
    with setup_mocks_for_main() as (
            mock_sys, mock_file_cmp, mock_move,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True
        configure_nerve.main()

        expected_move = call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_check_calls = [
            call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
        ]

        actual_subprocess_calls = mock_subprocess_call.call_args_list
        actual_subprocess_check_calls = mock_subprocess_check_call.call_args_list

        assert len(actual_subprocess_calls) == 0
        assert expected_subprocess_check_calls == actual_subprocess_check_calls
        assert not mock_sleep.called
