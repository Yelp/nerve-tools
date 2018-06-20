FROM ubuntu:xenial
MAINTAINER John Billings <billings@yelp.com>

# Need Python 3.6
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

RUN apt-get update && apt-get -y install \
    dpkg-dev \
    python-tox \
    python-setuptools \
    python3.6-dev \
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

RUN cd /tmp && \
    wget http://mirrors.kernel.org/ubuntu/pool/universe/d/dh-virtualenv/dh-virtualenv_1.0-1_all.deb && \
    gdebi -n dh-virtualenv*.deb && \
    rm dh-virtualenv_*.deb

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
