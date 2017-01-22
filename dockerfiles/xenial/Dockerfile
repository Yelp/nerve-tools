FROM ubuntu:xenial
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update && apt-get -y install \
    dpkg-dev \
    python-tox \
    python-setuptools \
    python-dev \
    libffi-dev \
    libssl-dev \
    debhelper \
    libyaml-dev \
    libcurl4-openssl-dev \
    dh-virtualenv \
    build-essential \
    protobuf-compiler

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
