FROM ubuntu:14.04

# Need Python 3.6 for nerve-tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa

# Older versions of dh-virtualenv are buggy and don't.. work
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 88ADA4A042F8DD13 && \
    echo 'deb http://ppa.launchpad.net/dh-virtualenv/daily/ubuntu trusty main\ndeb-src http://ppa.launchpad.net/dh-virtualenv/daily/ubuntu trusty main' >> /etc/apt/sources.list
RUN apt-get update

RUN apt-get -y install \
    build-essential \
    curl \
    debhelper \
    # Install for deps even though we install newer version below
    dh-virtualenv \
    dpkg-dev \
    gdebi-core \
    libcurl4-openssl-dev \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libzookeeper-mt-dev \
    protobuf-compiler \
    python3.6-dev \
    wget

# Uninstall so that pip can install non-conflicting versions below
RUN apt-get purge -y \
    python-pip \
    python-virtualenv \
    python-six \
    python-six-whl

# Preferred method to install pip when not bundled with python - https://pip.pypa.io/en/stable/installing/
RUN curl https://bootstrap.pypa.io/get-pip.py | python2

RUN pip install -U tox pip virtualenv==16.7.5

ADD location_types.json /nail/etc/services/
ADD location_mapping.json /nail/etc/services/

RUN cd /tmp && \
   wget http://mirrors.kernel.org/ubuntu/pool/universe/d/dh-virtualenv/dh-virtualenv_1.0-1_all.deb && \
   gdebi -n dh-virtualenv*.deb && \
   rm dh-virtualenv_*.deb

WORKDIR /work
