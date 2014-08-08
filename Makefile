all: itest_lucid

itest_lucid: package_lucid
	tox -e itest_lucid

package_lucid:
	[ -d dist ] || mkdir dist
	tox -e package_lucid

clean:
	tox -e fix_permissions
	git clean -Xfd
