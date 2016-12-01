import contextlib

import mock
import multiprocessing
from nerve_tools import configure_nerve

try:
    CPUS = max(multiprocessing.cpu_count(), 10)
except NotImplementedError:
    CPUS = 10


def test_get_named_zookeeper_topology():
    m = mock.mock_open()
    with contextlib.nested(
            mock.patch('nerve_tools.configure_nerve.open', m, create=True),
            mock.patch('yaml.load', return_value=[['foo', 42]])):
        zk_topology = configure_nerve.get_named_zookeeper_topology(
            'test-type', 'test-location', '/fake/path/'
        )
    assert zk_topology == ['foo:42']
    m.assert_called_with(
        '/fake/path/test-type/test-location.yaml'
    )


def test_generate_subconfiguration():
    expected_config = {
        'test_service.my_superregion.region:my_region.1234.new': {
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
            'labels': {
                'habitat': 'my_habitat',
                'region': 'my_region',
                'superregion': 'my_superregion',
                'ecosystem': 'my_ecosystem',
            },
        },
        'test_service.my_superregion.superregion:my_superregion.1234.new': {
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
            'labels': {
                'habitat': 'my_habitat',
                'region': 'my_region',
                'superregion': 'my_superregion',
                'ecosystem': 'my_ecosystem',
            },
        },
        'test_service.another_superregion.region:another_region.1234.new': {
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
            'labels': {
                'habitat': 'my_habitat',
                'region': 'my_region',
                'superregion': 'my_superregion',
                'ecosystem': 'my_ecosystem',
            },
        },
        'test_service.my_superregion:my_region.1234.v2.new': {
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
                'habitat': 'my_habitat',
                'region': 'my_region',
                'superregion': 'my_superregion',
                'ecosystem': 'my_ecosystem',
            },
        },
        'test_service.another_superregion:another_region.1234.v2.new': {
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
                'habitat': 'my_habitat',
                'region': 'my_region',
                'superregion': 'my_superregion',
                'ecosystem': 'my_ecosystem',
                'remote_region': 'another_region',
            },
        },
    }

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

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.get_current_location',
                   side_effect=get_current_location),
        mock.patch('nerve_tools.configure_nerve.convert_location_type',
                   side_effect=convert_location_type),
        mock.patch('nerve_tools.configure_nerve.get_named_zookeeper_topology',
                   side_effect=get_named_zookeeper_topology)):

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
            location_depth_mapping={
                'habitat': 3,
                'region': 2,
                'superregion': 1,
                'ecosystem': 0,
            },
        )

    assert expected_config == actual_config


def test_generate_configuration():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.available_location_types',
                   return_value=['ecosystem', 'superregion', 'region', 'habitat']),
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
                        _, _, _, mock_generate_subconfiguration):

        mock_service_info = {
            'port': 1234,
            'healthcheck_timeout_s': 2.0,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        actual_config = configure_nerve.generate_configuration(
            classic_services=[(
                'test_service',
                mock_service_info,
            )],
            paasta_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            location_depth_mapping={
                'habitat': 3,
                'region': 2,
                'superregion': 1,
                'ecosystem': 0,
            },
        )

    assert expected_config == actual_config


def test_generate_configuration_paasta_service():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
        },
        'heartbeat_path': 'test'
    }

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.available_location_types',
                   return_value=['ecosystem', 'superregion', 'region', 'habitat']),
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
                        _, _, _, mock_generate_subconfiguration):

        mock_service_info = {
            'port': 1234,
            'healthcheck_timeout_s': 2.0,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        actual_config = configure_nerve.generate_configuration(
            classic_services=[],
            paasta_services=[(
                'test_service',
                mock_service_info,
            )],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
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
            location_depth_mapping={
                'habitat': 3,
                'region': 2,
                'superregion': 1,
                'ecosystem': 0,
            },
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

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.available_location_types',
                   return_value=['ecosystem', 'superregion', 'region', 'habitat']),
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
            _, _, _, mock_generate_subconfiguration):

        mock_service_info = {
            'port': 1234,
            'routes': [('remote_location', 'local_location')],
            'healthcheck_timeout_s': 2.0,
            'healthcheck_port': 7890,
            'advertise': ['region'],
            'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
        }

        actual_config = configure_nerve.generate_configuration(
            classic_services=[(
                'test_service',
                mock_service_info,
            )],
            paasta_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            location_depth_mapping={
                'habitat': 3,
                'region': 2,
                'superregion': 1,
                'ecosystem': 0,
            },
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

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.available_location_types',
                   return_value=['ecosystem', 'superregion', 'region', 'habitat']),
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
            _, _, _, mock_generate_subconfiguration):

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
            classic_services=[(
                'test_service',
                mock_service_info,
            )],
            paasta_services=[],
            heartbeat_path='test',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
        )

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            service_info=mock_service_info,
            ip_address='ip_address',
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
            location_depth_mapping={
                'habitat': 3,
                'region': 2,
                'superregion': 1,
                'ecosystem': 0,
            },
        )

    assert expected_config == actual_config


def test_generate_configuration_empty():
    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host')):

        configuration = configure_nerve.generate_configuration(
            classic_services=[],
            paasta_services=[],
            heartbeat_path="",
            hacheck_port=6666,
            weight=mock.sentinel.classic_weight,
            zk_topology_dir='/fake/path',
            zk_location_type='fake_zk_location_type',
            zk_cluster_type='fake_cluster_type',
        )
        assert configuration == {'instance_id': 'my_host', 'services': {}, 'heartbeat_path': ''}


@contextlib.contextmanager
def setup_mocks_for_main():
    mock_sys = mock.MagicMock()
    mock_file_cmp = mock.Mock()
    mock_move = mock.Mock()
    mock_subprocess_call = mock.Mock()
    mock_subprocess_check_call = mock.Mock()
    mock_sleep = mock.Mock()
    mock_file_not_modified = mock.Mock(return_value=False)

    with contextlib.nested(
            mock.patch('sys.argv', return_value=[]),
            mock.patch('nerve_tools.configure_nerve.get_classic_services_running_here_for_nerve'),
            mock.patch('nerve_tools.configure_nerve.get_marathon_services_running_here_for_nerve'),
            mock.patch('nerve_tools.configure_nerve.generate_configuration'),
            mock.patch('nerve_tools.configure_nerve.open', create=True),
            mock.patch('json.dump'),
            mock.patch('os.chmod'),
            mock.patch('filecmp.cmp', mock_file_cmp),
            mock.patch('shutil.move', mock_move),
            mock.patch('subprocess.call', mock_subprocess_call),
            mock.patch('subprocess.check_call', mock_subprocess_check_call),
            mock.patch('time.sleep', mock_sleep),
            mock.patch('nerve_tools.configure_nerve.file_not_modified_since', mock_file_not_modified)):
        mocks = (
            mock_sys, mock_file_cmp, mock_move,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified
        )
        yield mocks


def test_file_not_modified_since():
    fake_threshold = 10
    fake_path = '/somepath'
    with contextlib.nested(
        mock.patch('time.time'),
        mock.patch('os.path.isfile', return_value=True),
        mock.patch('os.path.getmtime'),
    ) as (
        mock_time,
        mock_isfile,
        mock_getmtime,
    ):

        mock_time.return_value = 10.0
        mock_getmtime.return_value = mock_time.return_value + fake_threshold + 1
        print configure_nerve.file_not_modified_since(fake_path, fake_threshold)


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
