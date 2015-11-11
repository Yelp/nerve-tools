FROM ubuntu:14.04
MAINTAINER John Billings <billings@yelp.com>

RUN apt-get update
RUN apt-get install -yq python
# Create a dummy service running on port 1024 and serving up /status
EXPOSE 1024
RUN touch /tmp/status
CMD cd /tmp && python -m SimpleHTTPServer 1024
