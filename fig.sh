#!/bin/bash

# Wrapper around fig that:
#  * Transparently installs fig if necessary
#  * Always stops and removes any containers that fig knows about
#  * Propagates the return code of the fig command

# Where our virtualenv lives
VENV_LOC=fig_venv

function install_fig {
    if [ -d $VENV_LOC ]; then
        return
    fi

    virtualenv $VENV_LOC

    (
        . $VENV_LOC/bin/activate
        pip install -i http://pypi.yelpcorp.com/simple/ fig==0.5.1-legacy-docker-1
    )
}

function cleanup_containers {
    ret=$?
    fig stop
    fig rm --force
    exit $ret
}

function main {
    install_fig
    . $VENV_LOC/bin/activate
    trap cleanup_containers EXIT
    fig "$@"
}

main "$@"
