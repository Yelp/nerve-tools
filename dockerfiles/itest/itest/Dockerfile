FROM docker-dev.yelpcorp.com/lucid_yelp
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update

RUN apt-get -y install python-setuptools python-pytest python-pycurl python-kazoo
RUN apt-get -y install socat nerve rbenv rbenv-ruby-1.9.3-p448

ADD nerve.conf /etc/init/nerve.conf
ADD nerve.conf.json /etc/nerve/nerve.conf.json
ADD habitat /nail/etc/habitat
ADD yelpsoa-configs /nail/etc/services
ADD puppet_services.d /etc/nerve/puppet_services.d

ADD zookeeper_topology-my_habitat.yaml /nail/srv/configs/zookeeper_topology-my_habitat.yaml
ADD zookeeper_topology-another_habitat.yaml /nail/srv/configs/zookeeper_topology-another_habitat.yaml
ADD itest.py /itest.py

CMD py.test /itest.py
