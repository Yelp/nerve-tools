FROM ubuntu:14.04
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update
RUN apt-get -y install socat

# Create a dummy TCP service running on port 1025
EXPOSE 1025
CMD socat TCP4-LISTEN:1025,fork /dev/null
