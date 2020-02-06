FROM ubuntu:xenial

# Need Python 3.6
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

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
    python-setuptools \
    python-tox \
    python3.6-dev \
    wget
    
RUN easy_install pip
RUN pip install -U tox pip virtualenv

RUN cd /tmp && \
    wget http://mirrors.kernel.org/ubuntu/pool/universe/d/dh-virtualenv/dh-virtualenv_1.0-1_all.deb && \
    gdebi -n dh-virtualenv*.deb && \
    rm dh-virtualenv_*.deb

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
