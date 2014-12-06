all: itest_lucid itest_trusty

itest_trusty: package_trusty dockerfiles/itest/itest_trusty/Dockerfile
	tox -e itest_trusty

dockerfiles/itest/itest_trusty/Dockerfile: dockerfiles/itest/itest
	cp -a dockerfiles/itest/itest dockerfiles/itest/itest_trusty
	sed -e '1c FROM docker-dev.yelpcorp.com/trusty_yelp' dockerfiles/itest/itest/Dockerfile.pre > dockerfiles/itest/itest_trusty/Dockerfile

package_trusty:
	[ -d dist ] || mkdir dist
	tox -e package_trusty

dockerfiles/itest/itest_lucid/Dockerfile: dockerfiles/itest/itest
	cp -a dockerfiles/itest/itest dockerfiles/itest/itest_lucid
	sed -e '1c FROM docker-dev.yelpcorp.com/lucid_yelp' dockerfiles/itest/itest/Dockerfile.pre > dockerfiles/itest/itest_lucid/Dockerfile

itest_lucid: package_lucid dockerfiles/itest/itest_lucid/Dockerfile
	tox -e itest_lucid

package_lucid:
	[ -d dist ] || mkdir dist
	tox -e package_lucid

clean:
	tox -e fix_permissions
	git clean -Xfd
