FROM ubuntu:14.04
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update
RUN apt-get -y install zookeeper ant ivy default-jdk git

EXPOSE 2181
ADD thing.sh /thing.sh
CMD /thing.sh
