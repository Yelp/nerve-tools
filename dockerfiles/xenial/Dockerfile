FROM ubuntu:xenial

ARG PIP_INDEX_URL=https://pypi.yelpcorp.com/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL

# Need Python 3.6 for nerve-tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

RUN apt-get update && apt-get -y install \
    build-essential \
    curl \
    debhelper \
    # Install for deps even though we install newer version below
    dh-virtualenv \
    dpkg-dev \
    host \
    libcurl4-openssl-dev \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libzookeeper-mt-dev \
    protobuf-compiler \
    # dh-virtualenv only works with python2 - https://github.com/spotify/dh-virtualenv/issues/122
    python \
    python3.6-dev \
    wget

# Make sure python3 uses python 3.6 and not 3.5.1 which is along for the ride
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.5 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 2

# Preferred method to install pip when not bundled with python - https://pip.pypa.io/en/stable/installing/
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
# last internal setuptools with python2 support
RUN python2 get-pip.py setuptools==42.0.2

# Latest version of internally hosted virtualenv that works with dh-virtualenv 1.0-1. Later
# versions removed (well, 20.x, at least) --no-site-packages flag which dh-virtualenv needs.
RUN pip install -U tox pip virtualenv==16.7.5

RUN cd /tmp && \
    # Newer dh-virtualenv depends on sphinx-rtd-theme-common which is not easily installable
    # for python 2.7 - https://github.com/spotify/dh-virtualenv/issues/230
    wget http://mirrors.kernel.org/ubuntu/pool/universe/d/dh-virtualenv/dh-virtualenv_1.0-1_all.deb && \
    # Don't use gdebi - blows up on python deps!
    dpkg -i dh-virtualenv*.deb && \
    rm dh-virtualenv_*.deb

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
