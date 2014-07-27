import contextlib

import mock

from nerve_tools import configure_nerve


def test_get_habitats_to_register_in():
    routes = [
        ('sfo1', 'uswest1aprod'),
        ('sfo1', 'uswest1bprod'),
        ('sfo2', 'uswest1aprod'),
        ('sfo2', 'uswest1bprod'),
    ]

    expected_habitats = set(['uswest1aprod', 'sfo1', 'sfo2'])
    actual_habitats = configure_nerve.get_habitats_to_register_in('uswest1aprod', routes)
    assert expected_habitats == actual_habitats


def test_get_habitats_to_register_in_duplicates_are_ok():
    routes = [
        ('sfo1', 'uswest1aprod'),
        ('sfo1', 'uswest1aprod'),
    ]

    actual_habitats = configure_nerve.get_habitats_to_register_in('uswest1aprod', routes)
    assert actual_habitats == set(['uswest1aprod', 'sfo1'])


def test_get_habitats_to_register_in_default():
    expected_habitats = set(['sfo1'])
    actual_habitats = configure_nerve.get_habitats_to_register_in('sfo1', [])
    assert expected_habitats == actual_habitats


def test_service_is_enabled():
    file_contents_to_expected_enablement = {
        ('up', 'up'): True,
        ('up', 'down'): False,
        ('down', 'up'): False,
        ('down', 'down'): False,
    }

    expected_files_read = [
        mock.call('/var/spool/healthcheck_state/my_service'),
        mock.call('/var/spool/healthcheck_state/all'),
    ]

    for item in file_contents_to_expected_enablement.iteritems():
        file_contents, expected_enablement = item

        m = mock.mock_open()
        m.return_value.readline.side_effect = file_contents

        with mock.patch('nerve_tools.configure_nerve.open', m, create=True):
            actual_enablement = configure_nerve.service_is_enabled('my_service')

        assert expected_enablement == actual_enablement
        m.assert_has_calls(expected_files_read, any_order=True)


def test_get_zookeeper_topology():
    m = mock.mock_open()
    with contextlib.nested(
            mock.patch('nerve_tools.configure_nerve.open', m, create=True),
            mock.patch('yaml.load', return_value=[['foo', 42]])):
        zk_topology = configure_nerve.get_zookeeper_topology('my_habitat')
    assert zk_topology == ['foo:42']
    m.assert_called_with('/nail/srv/configs/zookeeper_topology-my_habitat.yaml')


def test_get_habitat():
    m = mock.mock_open()
    m.return_value.readline.return_value = '42'
    with mock.patch('nerve_tools.configure_nerve.open', m, create=True):
        habitat = configure_nerve.get_habitat()
    assert habitat == '42'
    m.assert_called_with('/nail/etc/habitat')


def test_convert_service_info_to_nerve_items():
    with contextlib.nested(
        mock.patch('nerve_tools.configure_nerve.service_is_enabled',
                   lambda service_name: service_name == 'test_service'),
        mock.patch('nerve_tools.configure_nerve.get_habitat',
                   return_value='local_habitat'),
        mock.patch('nerve_tools.configure_nerve.get_zookeeper_topology',
                   return_value=['1.2.3.4', '2.3.4.5']),
        mock.patch('nerve_tools.configure_nerve.get_ip_address',
                   return_value='ip_address')):

        actual_nerve_items = configure_nerve.convert_service_info_to_nerve_items(
            'test_service',
            {
                'port': 1234,
                'routes': [('remote_habitat', 'local_habitat')],
                'healthcheck_timeout_s': 2.0,
            },
            'fqdn')

    expected_nerve_items = [
        configure_nerve.NerveItem(
            'test_service',
            1234,
            'local_habitat',
            '/status',
            'ip_address',
            ['1.2.3.4', '2.3.4.5'],
            2.0
        ),
        configure_nerve.NerveItem(
            'test_service',
            1234,
            'remote_habitat',
            '/status',
            'ip_address',
            ['1.2.3.4', '2.3.4.5'],
            2.0
        )]

    assert actual_nerve_items == expected_nerve_items


def test_generate_configuration():
    with mock.patch('nerve_tools.configure_nerve.get_hostname',
                    return_value='my_host'):
        actual_configuration = configure_nerve.generate_configuration([
            configure_nerve.NerveItem(
                'test_service',
                1234,
                'local_habitat',
                '/status',
                'ip_address',
                ['1.2.3.4', '2.3.4.5'],
                2.0
            ),
            configure_nerve.NerveItem(
                'test_service',
                1234,
                'remote_habitat',
                '/status',
                'ip_address',
                ['1.2.3.4', '2.3.4.5'],
                2.0
            )])

    expected_configuration = {
        'instance_id': 'my_host',
        'services': {
            'test_service.local_habitat': {
                'zk_hosts': ['1.2.3.4', '2.3.4.5'],
                'zk_path': '/nerve/test_service',
                'checks': [{
                    'rise': 1,
                    'uri': '/status',
                    'host': '169.254.255.254',
                    'timeout': 2.0,
                    'fall': 2,
                    'type': 'http',
                    'port': 1234}],
                'host': 'ip_address',
                'check_interval': 10,
                'port': 1234
            },
            'test_service.remote_habitat': {
                'zk_hosts': ['1.2.3.4', '2.3.4.5'],
                'zk_path': '/nerve/test_service',
                'checks': [{
                    'rise': 1,
                    'uri': '/status',
                    'host': '169.254.255.254',
                    'timeout': 2.0,
                    'fall': 2,
                    'type': 'http',
                    'port': 1234}],
                'host': 'ip_address',
                'check_interval': 10,
                'port': 1234
            }
        }
    }

    assert actual_configuration == expected_configuration


def test_generate_configuration_empty():
    with mock.patch('nerve_tools.configure_nerve.get_hostname',
                    return_value='my_host'):
        configuration = configure_nerve.generate_configuration([])
        assert configuration == {'instance_id': 'my_host', 'services': {}}


def test_zookeeper_lock():
    mock_kazoo_client = mock.Mock()
    mock_lock = mock.Mock()
    mock_kazoo_client.Lock.return_value = mock_lock

    with contextlib.nested(
            mock.patch('kazoo.client.KazooClient', return_value=mock_kazoo_client),
            mock.patch('nerve_tools.configure_nerve.get_zookeeper_topology'),
            mock.patch('nerve_tools.configure_nerve.get_habitat')):
        with configure_nerve.zookeeper_lock():
            pass

    assert mock_lock.release.call_count == 1


@contextlib.contextmanager
def setup_mocks_for_main():
    mock_tmp_file = mock.MagicMock()
    mock_file_cmp = mock.Mock()
    mock_copy = mock.Mock()
    mock_env = mock.MagicMock()
    mock_subprocess_check_call = mock.Mock()
    mock_sleep = mock.Mock()

    with contextlib.nested(
            mock.patch('tempfile.NamedTemporaryFile', return_value=mock_tmp_file),
            mock.patch('nerve_tools.configure_nerve.get_fqdn'),
            mock.patch('nerve_tools.configure_nerve.get_services_running_here_for_nerve'),
            mock.patch('nerve_tools.configure_nerve.generate_configuration'),
            mock.patch('nerve_tools.configure_nerve.open', create=True),
            mock.patch('json.dump'),
            mock.patch('os.chmod'),
            mock.patch('filecmp.cmp', mock_file_cmp),
            mock.patch('nerve_tools.configure_nerve.zookeeper_lock'),
            mock.patch('shutil.copy', mock_copy),
            mock.patch('os.environ', mock_env),
            mock.patch('subprocess.check_call', mock_subprocess_check_call),
            mock.patch('time.sleep', mock_sleep)):
        yield (mock_tmp_file, mock_file_cmp, mock_copy, mock_env,
               mock_subprocess_check_call, mock_sleep)


def test_nerve_restarted_when_config_files_differ():
    with setup_mocks_for_main() as (
            mock_tmp_file, mock_file_cmp, mock_copy, mock_env,
            mock_subprocess_check_call, mock_sleep):

        # New and existing nerve configs differ
        mock_file_cmp.return_value = False

        configure_nerve.main()

        mock_copy.assert_called_with(
            mock_tmp_file.__enter__().name,
            '/etc/nerve/nerve.conf.json')
        mock_subprocess_check_call.assert_called_with(
            ['service', 'nerve', 'restart'], env=mock_env.copy.return_value)
        mock_sleep.assert_called_with(1)


def test_nerve_not_restarted_when_configs_files_are_identical():
    with setup_mocks_for_main() as (
            mock_tmp_file, mock_file_cmp, mock_copy, mock_env,
            mock_subprocess_check_call, mock_sleep):

        # New and existing nerve configs are identical
        mock_file_cmp.return_value = True

        configure_nerve.main()

        mock_copy.assert_called_with(
            mock_tmp_file.__enter__().name,
            '/etc/nerve/nerve.conf.json')
        assert not mock_subprocess_check_call.called
        assert not mock_sleep.called
