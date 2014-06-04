UID:=`id -u`
GID:=`id -g`
DOCKER_RUN:=docker run -t -v  $(CURDIR):/work:rw nerve_tools_lucid_container

all: itest_lucid

itest_lucid: package_lucid
	$(DOCKER_RUN) /work/itest/ubuntu.sh

package_lucid: test_lucid
	$(DOCKER_RUN) /bin/bash -c \
	    "cd src && dpkg-buildpackage -d -uc -us && mv ../*.deb ../dist/"

test_lucid: build_lucid_docker
	$(DOCKER_RUN) bash -c "cd src && tox"

build_lucid_docker:
	[ -d dist ] || mkdir dist
	cd dockerfiles/lucid/ && docker build -t "nerve_tools_lucid_container" .

clean:
	$(DOCKER_RUN) chown -R $(UID):$(GID) /work
	rm -f nerve-tools*.changes
	rm -f nerve-tools*.dsc
	rm -f nerve-tools*.tar.gz
	rm -rf dist
	rm -rf src/build
	rm -f src/debian/files
	rm -rf src/debian/nerve-tools
