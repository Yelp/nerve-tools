import socket


def get_hostname() -> str:
    return socket.gethostname()

def get_ip_address() -> str:
    return socket.gethostbyname(get_hostname())
