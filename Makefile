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

.PHONY: mypy
mypy:
	cd src && tox -e mypy

.PHONY: clean
clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
	git clean -Xfd

# 1. Bump `version='...'` in `src/setup.py`
# 2. Run `make release`
VERSION = $(shell sed -n "s|.*version='\([^']*\)'.*|\1|p" src/setup.py)
RELEASE = v$(VERSION)
LAST_COMMIT_MSG = $(shell git log -1 --pretty=%B | sed -e 's/\x27/"/g')
.PHONY: release
release:
	dch -v $(VERSION) --distribution xenial --changelog src/debian/changelog '$(LAST_COMMIT_MSG)'
	git ci -am 'Released $(VERSION) via make release'
	git tag $(RELEASE) master
	git show
	@echo 'Now run `git push origin master $(RELEASE)` to release this version'

