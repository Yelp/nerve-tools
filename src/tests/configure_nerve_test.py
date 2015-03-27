import contextlib
import os

import mock

from nerve_tools import configure_nerve


def test_get_locations_to_register_in():
    routes = [
        ('sfo1', 'uswest1aprod'),
        ('sfo1', 'uswest1bprod'),
        ('sfo2', 'uswest1aprod'),
        ('sfo2', 'uswest1bprod'),
    ]

    expected_locations = set(['uswest1aprod', 'sfo1', 'sfo2'])
    actual_locations = configure_nerve.get_locations_to_register_in('uswest1aprod', routes)
    assert expected_locations == actual_locations


def test_get_locations_to_register_in_duplicates_are_ok():
    routes = [
        ('sfo1', 'uswest1aprod'),
        ('sfo1', 'uswest1aprod'),
    ]

    actual_locations = configure_nerve.get_locations_to_register_in('uswest1aprod', routes)
    assert actual_locations == set(['uswest1aprod', 'sfo1'])


def test_get_locations_to_register_in_default():
    expected_locations = set(['sfo1'])
    actual_locations = configure_nerve.get_locations_to_register_in('sfo1', [])
    assert expected_locations == actual_locations


def test_get_named_zookeeper_topology():
    m = mock.mock_open()
    with contextlib.nested(
            mock.patch('nerve_tools.configure_nerve.open', m, create=True),
            mock.patch('yaml.load', return_value=[['foo', 42]])):
        zk_topology = configure_nerve.get_named_zookeeper_topology(
            'test-type', 'test-location'
        )
    assert zk_topology == ['foo:42']
    m.assert_called_with(
        '/nail/etc/zookeeper_discovery/test-type/test-location.yaml'
    )


def test_local_cluster_location():
    mock_readlink = mock.MagicMock()
    mock_readlink.return_value = os.path.join(
        configure_nerve.ZK_TOPOLOGY_DIR, 'test-type', 'test-location'
    )
    with mock.patch('nerve_tools.configure_nerve.os.readlink', mock_readlink):
        location = configure_nerve.get_local_cluster_location('test-type')
        assert location == 'test-location'


def test_generate_configuration_old():
    expected_config = {
        'test_service.local_location.1234': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/nerve/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/1234/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666}],
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234
        },
        'test_service.remote_location.1234': {
            'zk_hosts': ['2.3.4.5', '3.4.5.6'],
            'zk_path': '/nerve/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/1234/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666}],
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234
        }
    }

    def get_named_zookeeper_topology(cluster_type, cluster_location):
        return {
            ('generic', 'local_location'): ['1.2.3.4', '2.3.4.5'],
            ('generic', 'remote_location'): ['2.3.4.5', '3.4.5.6'],
        }[(cluster_type, cluster_location)]

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.get_named_zookeeper_topology',
                   side_effect=get_named_zookeeper_topology)):

        actual_config = configure_nerve.generate_configuration_old(
            service_name='test_service',
            my_location='local_location',
            routes=[('remote_location', 'local_location')],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/1234/status')

    assert actual_config == expected_config


def test_generate_configuration_new():
    expected_config = {
        'test_service.my_region.1234.new': {
            'zk_hosts': ['1.2.3.4', '2.3.4.5'],
            'zk_path': '/nerve/region:my_region/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/1234/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666}],
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234
        },
        'test_service.another_region.1234.new': {
            'zk_hosts': ['3.4.5.6', '4.5.6.7'],
            'zk_path': '/nerve/region:another_region/test_service',
            'checks': [{
                'rise': 1,
                'uri': '/http/test_service/1234/status',
                'host': '127.0.0.1',
                'timeout': 2.0,
                'fall': 2,
                'type': 'http',
                'port': 6666}],
            'host': 'ip_address',
            'check_interval': 3.0,
            'port': 1234
        }
    }

    def get_current_location(typ):
        return {
            'superregion': 'my_superregion',
            'habitat': 'my_habitat',
            'region': 'my_region',
        }[typ]

    def convert_location_type(src_typ, src_loc, dst_typ):
        return {
            ('my_superregion', 'superregion', 'region'): ['my_region'],
            ('my_region', 'region', 'superregion'): ['my_superregion'],
            ('another_region', 'region', 'region'): ['another_region'],
            ('another_region', 'region', 'superregion'): ['another_superregion'],
        }[(src_typ, src_loc, dst_typ)]

    def get_named_zookeeper_topology(cluster_type, cluster_location):
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

        actual_config = configure_nerve.generate_configuration_new(
            service_name='test_service',
            advertise=['region'],
            extra_advertise=[
                ('habitat:my_habitat', 'region:another_region'),
                ('habitat:your_habitat', 'region:another_region'),  # Ignored
            ],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/1234/status')

    assert expected_config == actual_config


def test_generate_configuration():
    expected_config = {
        'instance_id': 'my_host',
        'services': {
            'foo': 17,
            'bar': 42,
        }
    }

    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.get_local_cluster_location',
                   return_value='local_location'),
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_configuration_old',
                   return_value={'foo': 17}),
        mock.patch('nerve_tools.configure_nerve.generate_configuration_new',
                   return_value={'bar': 42})) as (
            _, _, _, mock_generate_configuration_old, mock_generate_configuration_new):

        actual_config = configure_nerve.generate_configuration([(
            'test_service',
            {
                'port': 1234,
                'routes': [('remote_location', 'local_location')],
                'healthcheck_timeout_s': 2.0,
                'advertise': ['region'],
                'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
            }
        )])

        mock_generate_configuration_old.assert_called_once_with(
            service_name='test_service',
            my_location='local_location',
            routes=[('remote_location', 'local_location')],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/1234/status'
        )

        mock_generate_configuration_new.assert_called_once_with(
            service_name='test_service',
            advertise=['region'],
            extra_advertise=[('habitat:my_habitat', 'region:another_region')],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/1234/status'
        )

    assert expected_config == actual_config


def test_generate_configuration_empty():
    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.get_local_cluster_location',
                   return_value='my_location')):

        configuration = configure_nerve.generate_configuration([])
        assert configuration == {'instance_id': 'my_host', 'services': {}}


@contextlib.contextmanager
def setup_mocks_for_main():
    mock_tmp_file = mock.MagicMock()
    mock_file_cmp = mock.Mock()
    mock_copy = mock.Mock()
    mock_subprocess_call = mock.Mock()
    mock_subprocess_check_call = mock.Mock()
    mock_sleep = mock.Mock()

    with contextlib.nested(
            mock.patch('tempfile.NamedTemporaryFile', return_value=mock_tmp_file),
            mock.patch('nerve_tools.configure_nerve.get_services_running_here_for_nerve'),
            mock.patch('nerve_tools.configure_nerve.generate_configuration'),
            mock.patch('nerve_tools.configure_nerve.open', create=True),
            mock.patch('json.dump'),
            mock.patch('os.chmod'),
            mock.patch('filecmp.cmp', mock_file_cmp),
            mock.patch('shutil.copy', mock_copy),
            mock.patch('subprocess.call', mock_subprocess_call),
            mock.patch('subprocess.check_call', mock_subprocess_check_call),
            mock.patch('time.sleep', mock_sleep)):
        mocks = (
            mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep
        )
        yield mocks


def test_nerve_restarted_when_config_files_differ():
    with setup_mocks_for_main() as (
            mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep):

        # New and existing nerve configs differ
        mock_file_cmp.return_value = False

        configure_nerve.main()

        mock_copy.assert_called_with(mock_tmp_file.__enter__().name, '/etc/nerve/nerve.conf.json')
        mock_subprocess_call.assert_any_call(['service', 'nerve-backup', 'start'])
        mock_subprocess_call.assert_any_call(['service', 'nerve-backup', 'stop'])
        mock_subprocess_check_call.assert_called_with(['service', 'nerve', 'restart'])
        mock_sleep.assert_called_with(configure_nerve.NERVE_REGISTRATION_DELAY_S)


def test_nerve_not_restarted_when_configs_files_are_identical():
    with setup_mocks_for_main() as (
            mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True

        configure_nerve.main()

        mock_copy.assert_called_with(mock_tmp_file.__enter__().name, '/etc/nerve/nerve.conf.json')
        assert not mock_subprocess_check_call.called
        assert not mock_subprocess_call.called
        assert not mock_sleep.called
