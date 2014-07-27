FIG:=./fig.sh

all: itest_lucid

build_containers:
	$(FIG) build

itest_lucid: build_containers package_lucid
	$(FIG) run itest

package_lucid:
	[ -d dist ] || mkdir dist
	$(FIG) run lucid

clean:
	$(FIG) run lucid chown -R `id -u`:`id -g` /work
	git clean -Xfd
