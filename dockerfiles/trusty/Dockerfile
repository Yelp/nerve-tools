FROM ubuntu:14.04
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update

RUN apt-get -y install dpkg-dev python-tox python-setuptools
RUN apt-get -y install python-dev debhelper libyaml-0-2 libcurl4-openssl-dev

# Older versions of dh-virtualenv are buggy and don't.. work
RUN curl http://ppa.launchpad.net/dh-virtualenv/daily/ubuntu/pool/main/d/dh-virtualenv/dh-virtualenv_0.10-0~80~ubuntu14.04.1_all.deb --output dh-virtualenv_0.10-0~80~ubuntu14.04.1_all.deb && \
  dpkg -i dh-virtualenv_0.10-0~80~ubuntu14.04.1_all.deb && rm dh-virtualenv_0.10-0~80~ubuntu14.04.1_all.deb

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
