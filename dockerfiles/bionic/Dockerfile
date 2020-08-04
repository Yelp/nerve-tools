FROM ubuntu:bionic

ARG PIP_INDEX_URL=https://pypi.yelpcorp.com/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL

RUN apt-get update && apt-get -y install \
    build-essential \
    debhelper \
    curl \
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
    python-setuptools \
    python-tox \
    python3-setuptools \
    python3.6-dev \
    wget


# Preferred method to install pip when not bundled with python - https://pip.pypa.io/en/stable/installing/
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
# last internal setuptools with python2 support
RUN python2 get-pip.py setuptools==42.0.2

# Latest version of internally hosted virtualenv that works with dh-virtualenv 1.0-1. Later
# versions removed (well, 20.x, at least) --no-site-packages flag which dh-virtualenv needs.
RUN pip install -U tox pip virtualenv==16.7.5

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
