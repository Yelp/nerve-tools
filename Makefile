all: itest_trusty

itest_trusty: package_trusty
	rm -rf dockerfiles/itest/itest_trusty
	cp -a dockerfiles/itest/itest dockerfiles/itest/itest_trusty
	sed -e '1c FROM ubuntu:14.04' dockerfiles/itest/itest/Dockerfile.pre > dockerfiles/itest/itest_trusty/Dockerfile
	tox -e itest_trusty

package_trusty:
	[ -d dist ] || mkdir dist
	tox -e package_trusty

itest_lucid: package_lucid
	rm -rf dockerfiles/itest/itest_lucid
	cp -a dockerfiles/itest/itest dockerfiles/itest/itest_lucid
	sed -e '1c FROM docker-dev.yelpcorp.com/lucid_yelp' dockerfiles/itest/itest/Dockerfile.pre > dockerfiles/itest/itest_lucid/Dockerfile
	tox -e itest_lucid

package_lucid:
	[ -d dist ] || mkdir dist
	tox -e package_lucid

clean:
	tox -e fix_permissions
	git clean -Xfd
