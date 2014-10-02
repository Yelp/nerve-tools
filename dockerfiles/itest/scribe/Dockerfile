FROM docker-dev.yelpcorp.com/lucid_yelp
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update
RUN apt-get -y install socat

# Create a dummy TCP service running on port 1464
EXPOSE 1464
CMD socat TCP4-LISTEN:1464,fork /dev/null
