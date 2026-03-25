import socket


def get_hostname() -> str:
    return socket.gethostname()


def get_host_ip() -> str:
    return socket.gethostbyname(get_hostname())
