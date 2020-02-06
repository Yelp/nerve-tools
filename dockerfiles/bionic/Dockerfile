FROM ubuntu:bionic

RUN apt-get update && apt-get -y install \
    build-essential \
    debhelper \
    dh-virtualenv \
    dpkg-dev \
    gdebi-core \
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
    
RUN pip install -U tox pip virtualenv

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
