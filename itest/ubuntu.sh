#!/bin/bash

tempfile=`mktemp`

function test_configure_nerve() {
  # We expect configure_nerve to fail, even if it works as designed, because
  # nerve is not installed.
  configure_nerve 1>$tempfile 2>&1
  if grep "No such file or directory: '/etc/nerve/nerve.conf.json'" "$tempfile" >/dev/null
  then
    return 0
  else
    echo "Command did not yield expected output"
    cat $tempfile
    return 1
  fi
}

highlight() {
  echo -n "$(tput setaf 3)"
  echo -n "$@"
  echo "$(tput op)"
}

cd /

# The package should install ok
highlight "dpkg -i" /work/dist/*.deb
if ! dpkg -i /work/dist/*.deb; then
  echo "dpkg failed with error code $?"
  exit 1
fi

# It should run with no special path
highlight test_configure_nerve
if ! test_configure_nerve; then
  echo "test_configure_nerve failed with error code $?"
  exit 1
fi

highlight "$0:" 'success!'
