FROM ubuntu:14.04
MAINTAINER John Billings <billings@yelp.com>


# Older versions of dh-virtualenv are buggy and don't.. work
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 88ADA4A042F8DD13 && \
    echo 'deb http://ppa.launchpad.net/dh-virtualenv/daily/ubuntu trusty main\ndeb-src http://ppa.launchpad.net/dh-virtualenv/daily/ubuntu trusty main' >> /etc/apt/sources.list
RUN apt-get update

RUN apt-get -y install \
		dpkg-dev \
		python-tox \
		python-setuptools \
		python-dev \
		debhelper \
		libyaml-dev \
		libcurl4-openssl-dev \
		dh-virtualenv \
		protobuf-compiler

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
