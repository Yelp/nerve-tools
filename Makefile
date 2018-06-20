all: itest_trusty

DATE := $(shell date +'%Y-%m-%d')
NERVETOOLSVERSION := $(shell sed 's/.*(\(.*\)).*/\1/;q' src/debian/changelog)
bintray.json: bintray.json.in src/debian/changelog
	sed -e 's/@DATE@/$(DATE)/g' -e 's/@NERVETOOLSVERSION@/$(NERVETOOLSVERSION)/g' $< > $@

.PHONY: itest_%
itest_%: package_% bintray.json
	rm -rf dockerfiles/itest/itest_$*
	cp -a dockerfiles/itest/itest dockerfiles/itest/itest_$*
	cp dockerfiles/itest/itest/Dockerfile.$* dockerfiles/itest/itest_$*/Dockerfile
	tox -e itest_$*

.PHONY: package_%
package_%:
	mkdir -p dist
	tox -e package_$*

.PHONY: clean
clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
	git clean -Xfd
