FROM ubuntu:bionic
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update && apt-get -y install \
    dpkg-dev \
    python-pip \
    python-setuptools \
    python-tox \
    python3.6-dev \
    python3-setuptools \
    libffi-dev \
    libssl-dev \
    debhelper \
    libyaml-dev \
    libcurl4-openssl-dev \
    dh-virtualenv \
    build-essential \
    protobuf-compiler \
    gdebi-core \
    wget

RUN pip install -U tox pip virtualenv

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
