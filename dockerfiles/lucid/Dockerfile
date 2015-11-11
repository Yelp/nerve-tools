FROM docker-dev.yelpcorp.com/lucid_yelp
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update

RUN apt-get -y install dpkg-dev python-tox python-setuptools
RUN apt-get -y install python-dev debhelper libyaml-0-2 libcurl4-openssl-dev
RUN apt-get -y install python2.7
RUN apt-get -y install python2.7-dev

# Make sure we get a package suitable for building this package correctly.
# Per dnephin we need https://github.com/spotify/dh-virtualenv/pull/20
# Which at this time is in this package
RUN apt-get -y install dh-virtualenv=0.6-yelp2

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

WORKDIR /work
