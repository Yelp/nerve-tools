from mypy_extensions import TypedDict
from typing import Mapping
from typing import Iterable
from typing import Dict
from typing import Tuple
from typing import Optional


class CheckDict(TypedDict, total=False):
    type: str
    host: str
    port: int
    uri: str
    timeout: float
    open_timeout: float
    rise: int
    fall: int
    headers: Mapping[str, str]
    expect: str


class SubSubConfiguration(TypedDict, total=False):
    port: int
    host: str
    zk_hosts: Iterable[str]
    zk_path: str
    check_interval: float
    checks: Iterable[CheckDict]
    labels: Dict[str, str]
    weight: int


SubConfiguration = Dict[str, SubSubConfiguration]


class NerveConfig(TypedDict):
    instance_id: str
    services: SubConfiguration
    heartbeat_path: str


class ServiceInfo(TypedDict, total=False):
    port: int
    hacheck_ip: str
    service_ip: str
    mode: str
    healthcheck_timeout_s: int
    healthcheck_port: int
    healthcheck_uri: str
    healthcheck_mode: str
    advertise: Iterable[str]
    extra_advertise: Iterable[Tuple[str, str]]
    extra_healthcheck_headers: Mapping[str, str]
    healthcheck_body_expect: str
    paasta_instance: Optional[str]
    deploy_group: Optional[str]
    host: str


class ListenerAddress(TypedDict):
    address: str
    port_value: int


class ListenerConfig(TypedDict):
    name: str
    local_address: Dict[str, ListenerAddress]
