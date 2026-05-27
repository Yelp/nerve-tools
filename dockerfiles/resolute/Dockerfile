FROM ubuntu:resolute

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

ARG PIP_INDEX_URL=https://pypi.yelpcorp.com/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL

# Need Python 3.12 for nerve-tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends gnupg2 software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

RUN apt-get update && apt-get -y install \
    build-essential \
    cargo \
    curl \
    debhelper \
    dh-virtualenv \
    dpkg-dev \
    host \
    libcurl4-openssl-dev \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libzookeeper-mt-dev \
    protobuf-compiler \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    rustc \
    wget

ADD requirements-bootstrap.txt /tmp/requirements-bootstrap.txt
RUN python3.12 -m venv /work/venv
RUN /work/venv/bin/pip install -U -r /tmp/requirements-bootstrap.txt
ENV PATH=$PATH:/work/venv/bin

ADD dockerfiles/resolute/location_types.json /nail/etc/services/
ADD dockerfiles/resolute/location_mapping.json /nail/etc/services/

WORKDIR /work
