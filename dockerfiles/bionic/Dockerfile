FROM ubuntu:bionic

RUN apt-get update && apt-get -y install \
    build-essential \
    debhelper \
    dh-virtualenv \
    dpkg-dev \
    gdebi-core \
    host \
    libcurl4-openssl-dev \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libzookeeper-mt-dev \
    protobuf-compiler \
    python-pip \
    python-setuptools \
    python-tox \
    python3-setuptools \
    python3.6-dev \
    wget

# Latest version of internally hosted virtualenv that works with dh-virtualenv 1.0-1. Later
# versions removed (well, 20.x, at least) --no-site-packages flag which dh-virtualenv needs.
RUN pip install -U tox pip virtualenv==16.7.5

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
