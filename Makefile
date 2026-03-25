export PIP_INDEX_URL ?= https://pypi.yelpcorp.com/simple
PIPX_BIN_DIR := .tox/pipx/bin
TOX_BOOTSTRAP_DIR := .tox/bootstrap
TOX := $(TOX_BOOTSTRAP_DIR)/bin/tox
DATE := $(shell date +'%Y-%m-%d')
NERVETOOLSVERSION := $(shell sed 's/.*(\(.*\)).*/\1/;q' debian/changelog)

$(TOX_BOOTSTRAP_DIR)/bin/activate: requirements-bootstrap.txt
	@command -v pipx >/dev/null 2>&1 || { echo "pipx is required to install virtualenv"; exit 1; }
	PIPX_BIN_DIR=$(PIPX_BIN_DIR) pipx install --force virtualenv
	test -d $(TOX_BOOTSTRAP_DIR)/bin/activate || $(PIPX_BIN_DIR)/virtualenv -p python3.12 $(TOX_BOOTSTRAP_DIR)
	$(TOX_BOOTSTRAP_DIR)/bin/python -m pip install -r requirements-bootstrap.txt
	touch $(TOX_BOOTSTRAP_DIR)/bin/activate

.PHONY: itest_%
itest_%: $(TOX_BOOTSTRAP_DIR)/bin/activate package_% debian/changelog
	rm -rf dockerfiles/itest/itest_$*
	cp -a dockerfiles/itest/itest dockerfiles/itest/itest_$*
	cp dockerfiles/itest/itest/Dockerfile.$* dockerfiles/itest/itest_$*/Dockerfile
	$(TOX) -e itest_$*

.PHONY: package_%
package_%: $(TOX_BOOTSTRAP_DIR)/bin/activate
	mkdir -p dist
	$(TOX) -e package_$*

.PHONY: mypy
mypy: $(TOX_BOOTSTRAP_DIR)/bin/activate
	$(TOX) -e mypy

.PHONY: clean
clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
	git clean -Xfd

# 1. Bump `version='...'` in `setup.py`
# 2. Run `make release`
VERSION = $(shell sed -n "s|.*version='\([^']*\)'.*|\1|p" setup.py)
RELEASE = v$(VERSION)
LAST_COMMIT_MSG = $(shell git log -1 --pretty=%B | sed -e 's/\x27/"/g')
.PHONY: release
release:
	dch -v $(VERSION) --distribution jammy --changelog debian/changelog '$(LAST_COMMIT_MSG)'
	git ci -am 'Released $(VERSION) via make release'
	git tag $(RELEASE) master
	git show
	@echo 'Now run `git push origin master $(RELEASE)` to release this version'

.PHONY: test
test: $(TOX_BOOTSTRAP_DIR)/bin/activate
	$(TOX) -e tests,mypy
