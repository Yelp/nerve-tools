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
            'test-type', 'test-location'
        )
    assert zk_topology == ['foo:42']
    m.assert_called_with(
        '/nail/etc/zookeeper_discovery/test-type/test-location.yaml'
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
            'weight': CPUS,
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
            'weight': CPUS,
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

        actual_config = configure_nerve.generate_subconfiguration(
            service_name='test_service',
            advertise=['region'],
            extra_advertise=[
                ('habitat:my_habitat', 'region:another_region'),
                ('habitat:your_habitat', 'region:another_region'),  # Ignored
            ],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/1234/status',
            healthcheck_headers={},
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
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
            _, _, mock_generate_subconfiguration):

        actual_config = configure_nerve.generate_configuration([(
            'test_service',
            {
                'port': 1234,
                'healthcheck_timeout_s': 2.0,
                'advertise': ['region'],
                'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
            }
        )], 'test')

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            advertise=['region'],
            extra_advertise=[('habitat:my_habitat', 'region:another_region')],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/1234/status',
            healthcheck_headers={},
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
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
            _, _, mock_generate_subconfiguration):

        actual_config = configure_nerve.generate_configuration([(
            'test_service',
            {
                'port': 1234,
                'routes': [('remote_location', 'local_location')],
                'healthcheck_timeout_s': 2.0,
                'healthcheck_port': 7890,
                'advertise': ['region'],
                'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
            }
        )], 'test')

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            advertise=['region'],
            extra_advertise=[('habitat:my_habitat', 'region:another_region')],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/http/test_service/7890/status',
            healthcheck_headers={},
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
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host'),
        mock.patch('nerve_tools.configure_nerve.generate_subconfiguration',
                   return_value={'foo': 17})) as (
            _, _, mock_generate_subconfiguration):

        actual_config = configure_nerve.generate_configuration([(
            'test_service',
            {
                'port': 1234,
                'routes': [('remote_location', 'local_location')],
                'healthcheck_timeout_s': 2.0,
                'healthcheck_mode': 'tcp',
                'healthcheck_port': 7890,
                'advertise': ['region'],
                'extra_advertise': [('habitat:my_habitat', 'region:another_region')],
            }
        )], 'test')

        mock_generate_subconfiguration.assert_called_once_with(
            service_name='test_service',
            advertise=['region'],
            extra_advertise=[('habitat:my_habitat', 'region:another_region')],
            port=1234,
            ip_address='ip_address',
            healthcheck_timeout_s=2.0,
            hacheck_uri='/tcp/test_service/7890/status',
            healthcheck_headers={},
        )

    assert expected_config == actual_config


def test_generate_configuration_empty():
    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address'),
        mock.patch('nerve_tools.configure_nerve.get_hostname',
                   return_value='my_host')):

        configuration = configure_nerve.generate_configuration([], "")
        assert configuration == {'instance_id': 'my_host', 'services': {}, 'heartbeat_path': ''}


@contextlib.contextmanager
def setup_mocks_for_main():
    mock_tmp_file = mock.MagicMock()
    mock_sys = mock.MagicMock()
    mock_file_cmp = mock.Mock()
    mock_copy = mock.Mock()
    mock_subprocess_call = mock.Mock()
    mock_subprocess_check_call = mock.Mock()
    mock_sleep = mock.Mock()
    mock_file_not_modified = mock.Mock(return_value=False)

    with contextlib.nested(
            mock.patch('sys.argv', return_value=[]),
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
            mock.patch('time.sleep', mock_sleep),
            mock.patch('nerve_tools.configure_nerve.file_not_modified_since', mock_file_not_modified)):
        mocks = (
            mock_sys, mock_tmp_file, mock_file_cmp, mock_copy,
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
            mock_sys, mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs differ
        mock_file_cmp.return_value = False
        configure_nerve.main()

        mock_copy.assert_called_with(mock_tmp_file.__enter__().name, '/etc/nerve/nerve.conf.json')
        mock_subprocess_call.assert_any_call(['service', 'nerve-backup', 'start'])
        mock_subprocess_call.assert_any_call(['service', 'nerve-backup', 'stop'])
        mock_subprocess_check_call.assert_any_call(['service', 'nerve', 'stop'])
        mock_subprocess_check_call.assert_any_call(['service', 'nerve', 'start'])
        mock_sleep.assert_called_with(configure_nerve.NERVE_REGISTRATION_DELAY_S)


def test_nerve_not_restarted_when_configs_files_are_identical():
    with setup_mocks_for_main() as (
            mock_sys, mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True
        configure_nerve.main()

        mock_copy.assert_called_with(mock_tmp_file.__enter__().name, '/etc/nerve/nerve.conf.json')
        assert not mock_subprocess_check_call.called
        assert not mock_subprocess_call.called
        assert not mock_sleep.called


def test_nerve_restarted_when_heartbeat_file_stale():
    with setup_mocks_for_main() as (
            mock_sys, mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True
        mock_file_not_modified.return_value = True
        configure_nerve.main()

        mock_subprocess_call.assert_any_call(['service', 'nerve-backup', 'start'])
        mock_subprocess_call.assert_any_call(['service', 'nerve-backup', 'stop'])
        mock_subprocess_check_call.assert_any_call(['service', 'nerve', 'stop'])
        mock_subprocess_check_call.assert_any_call(['service', 'nerve', 'start'])
        mock_sleep.assert_called_with(configure_nerve.NERVE_REGISTRATION_DELAY_S)


def test_nerve_not_restarted_when_heartbeat_file_valid():
    with setup_mocks_for_main() as (
            mock_sys, mock_tmp_file, mock_file_cmp, mock_copy,
            mock_subprocess_call, mock_subprocess_check_call, mock_sleep, mock_file_not_modified):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True
        configure_nerve.main()

        assert not mock_subprocess_check_call.called
        assert not mock_subprocess_call.called
        assert not mock_sleep.called
