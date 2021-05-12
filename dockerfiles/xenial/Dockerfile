FROM ubuntu:xenial

ARG PIP_INDEX_URL=https://pypi.yelpcorp.com/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL

# Need Python 3.7 for nerve-tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

RUN apt-get update && apt-get -y install \
    build-essential \
    curl \
    debhelper \
    dpkg-dev \
    host \
    libcurl4-openssl-dev \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libzookeeper-mt-dev \
    protobuf-compiler \
    python3.7-dev \
    python3.9-dev \
    libjs-sphinxdoc \
    sphinx-rtd-theme-common \
    wget

RUN wget http://archive.ubuntu.com/ubuntu/pool/universe/d/dh-virtualenv/dh-virtualenv_1.2.2-1build1_all.deb && \
    dpkg --force-all -i dh-virtualenv_1.2.2-1build1_all.deb

# Preferred method to install pip when not bundled with python - https://pip.pypa.io/en/stable/installing/
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
RUN python3.7 get-pip.py
RUN pip install -U tox pip virtualenv setuptools

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
