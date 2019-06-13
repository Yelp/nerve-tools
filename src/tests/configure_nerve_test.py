import copy
import mock
import pytest
import sys
import multiprocessing
from nerve_tools import configure_nerve
from contextlib import contextmanager


try:
    CPUS = max(multiprocessing.cpu_count(), 10)
except NotImplementedError:
    CPUS = 10


def test_get_named_zookeeper_topology():
    m = mock.mock_open()
    with mock.patch(
        'nerve_tools.configure_nerve.open',
        m, create=True
    ), mock.patch(
        'yaml.load', return_value=[['foo', 42]]
    ):
        zk_topology = configure_nerve.get_named_zookeeper_topology(
            'test-type', 'test-location', '/fake/path/'
        )
    assert zk_topology == ['foo:42']
    m.assert_called_with(
        '/fake/path/test-type/test-location.yaml'
    )


def get_labels_by_service_and_port(service, port, labels_dir):
    if (service, port) == ('test_service', 1234):
        return {'label1': 'value1', 'label2': 'value2'}
    else:
        return {}


def get_current_location(typ):
    return {
        'ecosystem': 'my_ecosystem',
        'superregion': 'my_superregion',
        'habitat': 'my_habitat',
        'region': 'my_region',
    }[typ]


def convert_location_type(src_loc, src_typ, dst_typ):
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
        'test_service.my_superregion.region:my_region.ip_address.1234.new': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/nerve/region:my_region/test_service',
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
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234,
            'weight': mock.sentinel.weight,
        },
        'test_service.my_superregion.superregion:my_superregion.ip_address.1234.new': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/nerve/superregion:my_superregion/test_service',
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
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234,
            'weight': mock.sentinel.weight,
        },
        'test_service.another_superregion.region:another_region.ip_address.1234.new': {
            'zk_hosts': ['3.4.5.6', '4.5.6.7'],
            'zk_path': '/nerve/region:another_region/test_service',
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
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234,
            'weight': mock.sentinel.weight,
        },
        'test_service.my_superregion:ip_address.1234.v2.new': {
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
            'host': 'ip_address',
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
        'test_service.another_superregion:ip_address.1234.v2.new': {
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
            'host': 'ip_address',
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
def expected_sub_config_with_envoy_listeners(expected_sub_config):
    expected_sub_config.update({
        'test_service.my_superregion:ip_address.1234.envoy': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/envoy/global/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/35000/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'open_timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666,
                'headers': {'Host': 'test_service'},
            }],
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 35000,
            'weight': mock.sentinel.weight,
            'labels': {
                'label1': 'value1',
                'label2': 'value2',
                'deploy_group': 'prod.canary',
                'paasta_instance': 'canary',
            },
        },
        'test_service.another_superregion:ip_address.1234.envoy': {
            'zk_hosts': ['3.4.5.6', '4.5.6.7'],
            'zk_path': '/envoy/global/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/35000/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'open_timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666,
                'headers': {'Host': 'test_service'},
            }],
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 35000,
            'weight': mock.sentinel.weight,
            'labels': {
                'label1': 'value1',
                'label2': 'value2',
                'deploy_group': 'prod.canary',
                'paasta_instance': 'canary',
            },
        },
    })
    return expected_sub_config


def test_get_envoy_listeners():
    expected_envoy_listeners = {
        'test_service.main.1234': 54321,
    }
    mock_envoy_admin_listeners_return_value = {
        'listener_statuses': [
            {
                'name': 'test_service.main.1234.ingress_listener',
                'local_address': {
                    'socket_address': {
                        'address': '0.0.0.0',
                        'port_value': 54321,
                    },
                },
            },
        ],
    }
    with mock.patch(
        'nerve_tools.configure_nerve._get_envoy_listeners_from_admin',
        return_value=mock_envoy_admin_listeners_return_value,
    ):
        assert configure_nerve.get_envoy_listeners(123) == \
            expected_envoy_listeners


def test_unsuccessful_get_envoy_listeners():
    with mock.patch(
        'nerve_tools.configure_nerve.requests.get',
        side_effect=Exception,
    ):
        assert configure_nerve.get_envoy_listeners(123) == {}


def test_generate_subconfiguration(expected_sub_config):
    with mock.patch(
        'nerve_tools.configure_nerve.get_current_location',
        side_effect=get_current_location
    ), mock.patch(
        'nerve_tools.configure_nerve.convert_location_type',
        side_effect=convert_location_type
    ), mock.patch(
        'nerve_tools.configure_nerve.get_named_zookeeper_topology',
        side_effect=get_named_zookeeper_topology
    ), mock.patch(
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
            ip_address='ip_address',
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
    with mock.patch(
        'nerve_tools.configure_nerve.get_current_location',
        side_effect=get_current_location
    ), mock.patch(
        'nerve_tools.configure_nerve.convert_location_type',
        side_effect=convert_location_type
    ), mock.patch(
        'nerve_tools.configure_nerve.get_named_zookeeper_topology',
        side_effect=get_named_zookeeper_topology
    ), mock.patch(
        'nerve_tools.configure_nerve.get_labels_by_service_and_port',
        side_effect=get_labels_by_service_and_port
    ):

        for k, v in expected_sub_config.items():
            expected_sub_config[k]['host'] = '10.4.5.6'
            for check in expected_sub_config[k]['checks']:
                check['host'] = '10.1.2.3'
        new_expected_sub_config = {}
        for k, v in expected_sub_config.items():
            new_expected_sub_config[k.replace('ip_address', '10.4.5.6')] = expected_sub_config[k]

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
            ip_address='ip_address',
            hacheck_port=6666,
            weight=mock.sentinel.weight,
            zk_topology_dir='/fake/path',
            zk_location_type='superregion',
            zk_cluster_type='infrastructure',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert new_expected_sub_config == actual_config


def test_generate_subconfiguration_with_envoy_listeners(expected_sub_config_with_envoy_listeners):
    with mock.patch(
        'nerve_tools.configure_nerve.get_current_location',
        side_effect=get_current_location
    ), mock.patch(
        'nerve_tools.configure_nerve.convert_location_type',
        side_effect=convert_location_type
    ), mock.patch(
        'nerve_tools.configure_nerve.get_named_zookeeper_topology',
        side_effect=get_named_zookeeper_topology
    ), mock.patch(
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
        mock_envoy_service_info = copy.deepcopy(mock_service_info)
        mock_envoy_service_info.update({
            'port': 35000,
            'healthcheck_port': 35000,
            'extra_healthcheck_headers': {'Host': 'test_service'},
        })

        actual_config = configure_nerve.generate_subconfiguration(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
            hacheck_port=6666,
            weight=mock.sentinel.weight,
            zk_topology_dir='/fake/path',
            zk_location_type='superregion',
            zk_cluster_type='infrastructure',
            labels_dir='/dev/null',
            envoy_service_info=mock_envoy_service_info,
        )

    assert expected_sub_config_with_envoy_listeners == actual_config


def test_generate_configuration_paasta_service():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with mock.patch(
        'nerve_tools.configure_nerve.get_ip_address',
        return_value='ip_address'
    ), mock.patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), mock.patch(
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
            envoy_listeners={},
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
            hacheck_port=6666,
            weight=10,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_service_info=None,
        )

    assert expected_config == actual_config


def test_generate_configuration_paasta_service_with_envoy_listeners():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with mock.patch(
        'nerve_tools.configure_nerve.get_ip_address',
        return_value='ip_address'
    ), mock.patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), mock.patch(
        'nerve_tools.configure_nerve.generate_subconfiguration',
        return_value={'foo': 17}
    ) as mock_generate_subconfiguration:

        mock_service_info = {
            'port': 1234,
            'healthcheck_timeout_s': 2.0,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        envoy_listeners = {'test_service.1234': 35001}
        mock_envoy_service_info = copy.deepcopy(mock_service_info)
        mock_envoy_service_info.update({
            'port': 35001,
            'healthcheck_port': 35001,
            'extra_healthcheck_headers': {'Host': 'test_service'},
        })

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
            envoy_listeners=envoy_listeners,
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
            hacheck_port=6666,
            weight=10,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            labels_dir='/dev/null',
            envoy_service_info=mock_envoy_service_info,
        )

    assert expected_config == actual_config


def test_generate_configuration_healthcheck_port():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with mock.patch(
        'nerve_tools.configure_nerve.get_ip_address',
        return_value='ip_address'
    ), mock.patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), mock.patch(
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
            envoy_listeners={},
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
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

    with mock.patch(
        'nerve_tools.configure_nerve.get_ip_address',
        return_value='ip_address'
    ), mock.patch(
        'nerve_tools.configure_nerve.get_hostname',
        return_value='my_host'
    ), mock.patch(
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
            envoy_listeners={},
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
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
    with mock.patch(
        'nerve_tools.configure_nerve.get_ip_address',
        return_value='ip_address'
    ), mock.patch(
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
            envoy_listeners={},
        )
        assert configuration == {'instance_id': 'my_host', 'services': {}, 'heartbeat_path': ''}


@contextmanager
def setup_mocks_for_main():
    mock_sys = mock.MagicMock()
    mock_file_cmp = mock.Mock()
    mock_move = mock.Mock()
    mock_subprocess_call = mock.Mock()
    mock_subprocess_check_call = mock.Mock()
    mock_sleep = mock.Mock()
    mock_file_not_modified = mock.Mock(return_value=False)

    with mock.patch.object(
        sys, 'argv', ['configure-nerve']
    ) as mock_sys, mock.patch(
        'nerve_tools.configure_nerve.get_marathon_services_running_here_for_nerve'
    ), mock.patch(
        'nerve_tools.configure_nerve.get_paasta_native_services_running_here_for_nerve'
    ), mock.patch(
        'nerve_tools.configure_nerve.generate_configuration'
    ), mock.patch(
        'nerve_tools.configure_nerve.open', create=True
    ), mock.patch(
        'json.dump'
    ), mock.patch(
        'os.chmod'
    ), mock.patch(
        'filecmp.cmp'
    ) as mock_file_cmp, mock.patch(
        'shutil.move'
    ) as mock_move, mock.patch(
        'subprocess.call'
    ) as mock_subprocess_call, mock.patch(
        'subprocess.check_call'
    ) as mock_subprocess_check_call, mock.patch(
        'time.sleep'
    ) as mock_sleep, mock.patch(
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
    with mock.patch(
        'time.time'
    ) as mock_time, mock.patch(
        'os.path.isfile', return_value=True
    ), mock.patch(
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

        expected_move = mock.call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_calls = (
            mock.call(['service', 'nerve-backup', 'start']),
            mock.call(['service', 'nerve-backup', 'stop']),
        )
        expected_subprocess_check_calls = (
            mock.call(['service', 'nerve', 'start']),
            mock.call(['service', 'nerve', 'stop']),
            mock.call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
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

        expected_move = mock.call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_check_calls = [
            mock.call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
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

        expected_move = mock.call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_calls = (
            mock.call(['service', 'nerve-backup', 'start']),
            mock.call(['service', 'nerve-backup', 'stop']),
        )
        expected_subprocess_check_calls = (
            mock.call(['service', 'nerve', 'start']),
            mock.call(['service', 'nerve', 'stop']),
            mock.call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
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

        expected_move = mock.call('/etc/nerve/nerve.conf.json.tmp', '/etc/nerve/nerve.conf.json')
        assert mock_move.call_args_list == [expected_move]

        expected_subprocess_check_calls = [
            mock.call(['/usr/bin/nerve', '-c', '/etc/nerve/nerve.conf.json.tmp', '-k'])
        ]

        actual_subprocess_calls = mock_subprocess_call.call_args_list
        actual_subprocess_check_calls = mock_subprocess_check_call.call_args_list

        assert len(actual_subprocess_calls) == 0
        assert expected_subprocess_check_calls == actual_subprocess_check_calls
        assert not mock_sleep.called
