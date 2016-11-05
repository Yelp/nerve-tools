FROM docker-dev.yelpcorp.com/lucid_yelp
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update && apt-get -y install \
    dpkg-dev \
    python-tox \
    python-setuptools \
    python-dev \
    debhelper \
    libyaml-dev \
    libcurl4-openssl-dev \
    python2.7 \
    python2.7-dev \
    libffi-dev \
    libssl-dev \
    build-essential \
    dh-virtualenv


ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
